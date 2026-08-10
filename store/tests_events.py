from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from analytics.events import (
    ALL_EVENT_TYPES,
    RecordingPublisher,
    build_listing_created_event,
    build_listing_updated_event,
    build_user_registered_event,
    clone_product_state,
    set_publisher,
)
from analytics.events.types import (
    LISTING_CREATED,
    LISTING_DELETED,
    LISTING_UPDATED,
    USER_REGISTERED,
    WISHLIST_ADDED,
    WISHLIST_REMOVED,
)
from store.models import Product


class EventBuilderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='seller',
            email='seller@uni.edu',
            password='pass12345',
        )

    def test_user_registered_envelope(self):
        event = build_user_registered_event(self.user)
        self.assertEqual(event['event_type'], USER_REGISTERED)
        self.assertEqual(event['entity_type'], 'user')
        self.assertEqual(event['entity_id'], self.user.id)
        self.assertEqual(event['payload']['username'], 'seller')
        self.assertIn('event_id', event)
        self.assertNotIn('password', event['payload'])

    def test_listing_created_omits_description_and_stringifies_price(self):
        product = Product.objects.create(
            title='Lamp',
            description='Bright LED desk lamp for studying',
            price=Decimal('400.50'),
            category='Education',
            user=self.user,
        )
        event = build_listing_created_event(product=product, actor_id=self.user.id)
        self.assertEqual(event['event_type'], LISTING_CREATED)
        self.assertEqual(event['payload']['price'], '400.50')
        self.assertNotIn('description', event['payload'])
        self.assertEqual(event['payload']['category'], 'Education')

    def test_listing_updated_skipped_when_unchanged(self):
        product = Product.objects.create(
            title='Lamp',
            description='Bright',
            price=Decimal('400.00'),
            category='Education',
            user=self.user,
        )
        previous = clone_product_state(product)
        event = build_listing_updated_event(
            previous=previous,
            current=product,
            actor_id=self.user.id,
            actor_is_superuser=False,
        )
        self.assertIsNone(event)

    def test_listing_updated_includes_price_diff(self):
        product = Product.objects.create(
            title='Lamp',
            description='Bright',
            price=Decimal('400.00'),
            category='Education',
            user=self.user,
        )
        previous = clone_product_state(product)
        product.price = Decimal('350.00')
        product.save()
        event = build_listing_updated_event(
            previous=previous,
            current=product,
            actor_id=self.user.id,
            actor_is_superuser=False,
        )
        self.assertIsNotNone(event)
        self.assertEqual(event['event_type'], LISTING_UPDATED)
        self.assertEqual(event['payload']['changed_fields'], ['price'])
        self.assertEqual(event['payload']['previous']['price'], '400.00')
        self.assertEqual(event['payload']['current']['price'], '350.00')


class EventInstrumentationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.recorder = RecordingPublisher()
        set_publisher(self.recorder)
        self.seller = User.objects.create_user(username='seller_a', password='pass12345')
        self.buyer = User.objects.create_user(username='buyer_b', password='pass12345')

    def tearDown(self):
        set_publisher(None)

    def _product_payload(self, **overrides):
        data = {
            'title': 'Desk Lamp',
            'description': 'Bright study lamp',
            'price': '250.00',
            'category': 'Furniture',
        }
        data.update(overrides)
        return data

    def test_register_emits_user_registered(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/register/',
                {'username': 'newbie', 'email': 'n@uni.edu', 'password': 'pass12345'},
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        events = self.recorder.of_type(USER_REGISTERED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['payload']['username'], 'newbie')
        self.assertTrue(events[0]['event_id'])

    def test_failed_register_emits_nothing(self):
        User.objects.create_user(username='newbie', password='pass12345')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/register/',
                {'username': 'newbie', 'email': 'n@uni.edu', 'password': 'pass12345'},
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.recorder.events, [])

    def test_create_listing_emits_listing_created(self):
        self.client.force_authenticate(user=self.seller)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/products/',
                self._product_payload(),
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        events = self.recorder.of_type(LISTING_CREATED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['payload']['price'], '250.00')
        self.assertEqual(events[0]['payload']['seller_id'], self.seller.id)
        self.assertNotIn('description', events[0]['payload'])
        self.assertIn(events[0]['event_type'], ALL_EVENT_TYPES)

    def test_update_listing_emits_listing_updated_with_changes(self):
        product = Product.objects.create(
            title='Desk Lamp',
            description='Bright study lamp',
            price=Decimal('250.00'),
            category='Furniture',
            user=self.seller,
        )
        self.client.force_authenticate(user=self.seller)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                f'/api/update/{product.id}/',
                self._product_payload(price='200.00', title='Desk Lamp'),
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        events = self.recorder.of_type(LISTING_UPDATED)
        self.assertEqual(len(events), 1)
        self.assertIn('price', events[0]['payload']['changed_fields'])
        self.assertEqual(events[0]['payload']['previous']['price'], '250.00')
        self.assertEqual(events[0]['payload']['current']['price'], '200.00')

    def test_update_listing_skips_event_when_unchanged(self):
        product = Product.objects.create(
            title='Desk Lamp',
            description='Bright study lamp',
            price=Decimal('250.00'),
            category='Furniture',
            user=self.seller,
        )
        self.client.force_authenticate(user=self.seller)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.put(
                f'/api/update/{product.id}/',
                self._product_payload(),
                format='json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.recorder.of_type(LISTING_UPDATED), [])

    def test_delete_listing_emits_listing_deleted_with_snapshot(self):
        product = Product.objects.create(
            title='Desk Lamp',
            description='Bright study lamp',
            price=Decimal('250.00'),
            category='Furniture',
            user=self.seller,
        )
        product_id = product.id
        self.client.force_authenticate(user=self.seller)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f'/api/delete/{product_id}/')
        self.assertEqual(response.status_code, 200)
        events = self.recorder.of_type(LISTING_DELETED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['entity_id'], product_id)
        self.assertEqual(events[0]['payload']['price'], '250.00')
        self.assertEqual(events[0]['payload']['category'], 'Furniture')
        self.assertTrue(events[0]['payload']['deleted_by_owner'])

    def test_wishlist_toggle_emits_add_then_remove(self):
        product = Product.objects.create(
            title='Monitor',
            description='24 inch',
            price=Decimal('8000.00'),
            category='Electronics',
            user=self.seller,
        )
        self.client.force_authenticate(user=self.buyer)
        with self.captureOnCommitCallbacks(execute=True):
            add = self.client.post(
                '/api/wishlist/',
                {'product_id': product.id},
                format='json',
            )
        self.assertEqual(add.status_code, 200)
        self.assertEqual(add.data['status'], 'added')
        self.assertEqual(len(self.recorder.of_type(WISHLIST_ADDED)), 1)
        self.assertEqual(
            self.recorder.of_type(WISHLIST_ADDED)[0]['payload']['price'],
            '8000.00',
        )

        with self.captureOnCommitCallbacks(execute=True):
            remove = self.client.post(
                '/api/wishlist/',
                {'product_id': product.id},
                format='json',
            )
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(remove.data['status'], 'removed')
        self.assertEqual(len(self.recorder.of_type(WISHLIST_REMOVED)), 1)

    def test_invalid_product_create_emits_nothing(self):
        self.client.force_authenticate(user=self.seller)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/api/products/',
                self._product_payload(category='NotReal', price='-1'),
                format='json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.recorder.events, [])

    def test_on_commit_not_called_when_transaction_would_not_publish_invalid(self):
        """Ensure schedule path is used (mocked) only after successful create."""
        self.client.force_authenticate(user=self.seller)
        with patch('store.views.schedule_event_publish') as mocked:
            self.client.post(
                '/api/products/',
                self._product_payload(category='NotReal'),
                format='json',
            )
            mocked.assert_not_called()
