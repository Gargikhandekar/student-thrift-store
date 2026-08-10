from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import PRODUCT_CATEGORIES, Product, Wishlist


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_successful_registration(self):
        response = self.client.post(
            '/api/register/',
            {'username': 'student1', 'email': 's1@uni.edu', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'student1')
        self.assertTrue(User.objects.filter(username='student1').exists())

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username='student1', password='pass12345')
        response = self.client.post(
            '/api/register/',
            {'username': 'student1', 'email': 'other@uni.edu', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    def test_registration_requires_username_and_password(self):
        response = self.client.post(
            '/api/register/',
            {'username': '', 'email': 'a@b.com', 'password': ''},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_successful_login_and_logout(self):
        User.objects.create_user(username='student1', password='pass12345')
        login_response = self.client.post(
            '/api/login/',
            {'username': 'student1', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.data['username'], 'student1')

        logout_response = self.client.post('/api/logout/')
        self.assertEqual(logout_response.status_code, 200)

        profile = self.client.get('/api/profile/')
        self.assertEqual(profile.status_code, 403)


class ProductAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller_a = User.objects.create_user(username='seller_a', password='pass12345')
        self.seller_b = User.objects.create_user(username='seller_b', password='pass12345')
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@uni.edu',
            password='adminpass',
        )
        self.product = Product.objects.create(
            title='Used Laptop',
            description='Lightly used campus laptop',
            price=Decimal('1500.00'),
            category='Electronics',
            user=self.seller_a,
        )

    def _product_payload(self, **overrides):
        data = {
            'title': 'Desk Lamp',
            'description': 'Bright study lamp',
            'price': '250.00',
            'category': 'Furniture',
        }
        data.update(overrides)
        return data

    def test_authenticated_user_can_create_listing(self):
        self.client.force_authenticate(user=self.seller_a)
        response = self.client.post('/api/products/', self._product_payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['seller_username'], 'seller_a')
        self.assertEqual(Product.objects.get(id=response.data['id']).user, self.seller_a)

    def test_unauthenticated_user_cannot_create_listing(self):
        response = self.client.post('/api/products/', self._product_payload(), format='json')
        self.assertEqual(response.status_code, 403)

    def test_user_can_retrieve_listings(self):
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    def test_owner_can_update_listing_and_keeps_ownership(self):
        self.client.force_authenticate(user=self.seller_a)
        response = self.client.put(
            f'/api/update/{self.product.id}/',
            self._product_payload(title='Updated Laptop', price='1400.00', category='Electronics'),
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Updated Laptop')
        self.assertEqual(self.product.user_id, self.seller_a.id)

    def test_other_user_cannot_update_listing(self):
        self.client.force_authenticate(user=self.seller_b)
        response = self.client.put(
            f'/api/update/{self.product.id}/',
            self._product_payload(title='Hijacked', category='Electronics'),
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_without_taking_ownership(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.put(
            f'/api/update/{self.product.id}/',
            self._product_payload(title='Admin Edited', price='1600.00', category='Electronics'),
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Admin Edited')
        self.assertEqual(self.product.user_id, self.seller_a.id)

    def test_owner_can_delete_listing(self):
        self.client.force_authenticate(user=self.seller_a)
        response = self.client.delete(f'/api/delete/{self.product.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_other_user_cannot_delete_listing(self):
        self.client.force_authenticate(user=self.seller_b)
        response = self.client.delete(f'/api/delete/{self.product.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(id=self.product.id).exists())

    def test_nonexistent_product_returns_404_on_update_and_delete(self):
        self.client.force_authenticate(user=self.seller_a)
        update = self.client.put(
            '/api/update/99999/',
            self._product_payload(category='Electronics'),
            format='json',
        )
        delete = self.client.delete('/api/delete/99999/')
        self.assertEqual(update.status_code, 404)
        self.assertEqual(delete.status_code, 404)

    def test_invalid_product_data_rejected(self):
        self.client.force_authenticate(user=self.seller_a)
        response = self.client.post(
            '/api/products/',
            self._product_payload(price='-10.00', category='NotARealCategory'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)


class SearchFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        owner = User.objects.create_user(username='owner', password='pass12345')
        Product.objects.create(
            title='Calculus Textbook',
            description='Math book for first year',
            price=Decimal('500.00'),
            category='Books',
            user=owner,
        )
        Product.objects.create(
            title='Noise Cancelling Headphones',
            description='Wireless campus headphones',
            price=Decimal('2500.00'),
            category='Electronics',
            user=owner,
        )

    def test_search_works(self):
        response = self.client.get('/api/products/', {'search': 'calculus'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertIn('Calculus', response.data[0]['title'])

    def test_category_filtering_works(self):
        response = self.client.get('/api/products/', {'category': 'Electronics'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['category'], 'Electronics')

    def test_price_filtering_works(self):
        response = self.client.get('/api/products/', {'min_price': '1000', 'max_price': '3000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Noise Cancelling Headphones')


class WishlistAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='buyer', password='pass12345')
        seller = User.objects.create_user(username='seller', password='pass12345')
        self.product = Product.objects.create(
            title='Monitor',
            description='24 inch monitor',
            price=Decimal('8000.00'),
            category='Electronics',
            user=seller,
        )

    def test_add_and_toggle_remove_wishlist(self):
        self.client.force_authenticate(user=self.user)
        add = self.client.post('/api/wishlist/', {'product_id': self.product.id}, format='json')
        self.assertEqual(add.status_code, 200)
        self.assertEqual(add.data['status'], 'added')
        self.assertEqual(Wishlist.objects.filter(user=self.user, product=self.product).count(), 1)

        remove = self.client.post('/api/wishlist/', {'product_id': self.product.id}, format='json')
        self.assertEqual(remove.status_code, 200)
        self.assertEqual(remove.data['status'], 'removed')
        self.assertEqual(Wishlist.objects.filter(user=self.user, product=self.product).count(), 0)

    def test_duplicate_wishlist_entries_prevented(self):
        self.client.force_authenticate(user=self.user)
        Wishlist.objects.create(user=self.user, product=self.product)
        # Toggle removes rather than creating a second row.
        response = self.client.post('/api/wishlist/', {'product_id': self.product.id}, format='json')
        self.assertEqual(response.data['status'], 'removed')
        self.assertEqual(Wishlist.objects.filter(user=self.user, product=self.product).count(), 0)

    def test_nonexistent_product_wishlist_returns_404(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/wishlist/', {'product_id': 99999}, format='json')
        self.assertEqual(response.status_code, 404)


class ProductModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='pass12345')

    def test_price_stored_as_decimal(self):
        product = Product.objects.create(
            title='Chair',
            description='Study chair',
            price=Decimal('2500.50'),
            category='Furniture',
            user=self.user,
        )
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal('2500.50'))
        self.assertIsInstance(product.price, Decimal)

    def test_timestamps_set_on_create_and_update(self):
        product = Product.objects.create(
            title='Chair',
            description='Study chair',
            price=Decimal('100.00'),
            category='Furniture',
            user=self.user,
        )
        self.assertIsNotNone(product.created_at)
        self.assertIsNotNone(product.updated_at)
        created_at = product.created_at
        updated_at = product.updated_at

        product.title = 'Updated Chair'
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.created_at, created_at)
        self.assertGreaterEqual(product.updated_at, updated_at)

    def test_ownership_relation(self):
        product = Product.objects.create(
            title='Chair',
            description='Study chair',
            price=Decimal('100.00'),
            category='Furniture',
            user=self.user,
        )
        self.assertEqual(product.user, self.user)
        self.assertIn(product, self.user.product_set.all())

    def test_canonical_categories_defined(self):
        self.assertIn('Electronics', PRODUCT_CATEGORIES)
        self.assertIn('Fashion', PRODUCT_CATEGORIES)
        self.assertNotIn('Clothing', PRODUCT_CATEGORIES)
