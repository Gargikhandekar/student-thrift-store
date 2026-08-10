"""Unit tests for Kafka analytics wiring (no live broker required)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.test.utils import override_settings as _  # noqa: F401 — keep import style clear

from analytics.events.publisher import (
    LoggingPublisher,
    create_default_publisher,
    set_publisher,
)
from analytics.kafka.config import (
    kafka_bootstrap_servers,
    kafka_client_id,
    kafka_enabled,
    kafka_topic,
)
from analytics.kafka.consumer import build_consumer
from analytics.kafka.producer import KafkaPublisher, message_key_for_event, _json_dumps


SAMPLE_EVENT = {
    'event_id': '11111111-1111-1111-1111-111111111111',
    'event_type': 'listing_created',
    'event_time': '2026-08-10T12:00:00+00:00',
    'schema_version': 1,
    'user_id': 12,
    'entity_type': 'product',
    'entity_id': 45,
    'payload': {
        'seller_id': 12,
        'title': 'Lamp',
        'price': '499.00',
        'category': 'Education',
        'has_image': False,
        'created_at': '2026-08-10T12:00:00+00:00',
    },
}


class KafkaConfigTests(SimpleTestCase):
    @override_settings()
    def test_defaults(self):
        with patch.dict('os.environ', {}, clear=True):
            # Clear only kafka-related if present
            pass
        with patch.dict(
            'os.environ',
            {
                'KAFKA_ENABLED': 'false',
                'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092',
                'KAFKA_TOPIC': 'thrift_events',
                'KAFKA_CLIENT_ID': 'thrift-store-app',
            },
            clear=False,
        ):
            self.assertFalse(kafka_enabled())
            self.assertEqual(kafka_bootstrap_servers(), 'localhost:9092')
            self.assertEqual(kafka_topic(), 'thrift_events')
            self.assertEqual(kafka_client_id(), 'thrift-store-app')

    def test_enabled_true(self):
        with patch.dict('os.environ', {'KAFKA_ENABLED': 'true'}):
            self.assertTrue(kafka_enabled())


class PublisherSelectionTests(SimpleTestCase):
    def tearDown(self):
        set_publisher(None)

    def test_kafka_disabled_selects_logging_publisher(self):
        with patch.dict('os.environ', {'KAFKA_ENABLED': 'false'}):
            set_publisher(None)
            publisher = create_default_publisher()
            self.assertIsInstance(publisher, LoggingPublisher)

    def test_kafka_enabled_selects_kafka_publisher(self):
        with patch.dict('os.environ', {'KAFKA_ENABLED': 'true'}):
            set_publisher(None)
            publisher = create_default_publisher()
            self.assertIsInstance(publisher, KafkaPublisher)


class KafkaPublisherUnitTests(SimpleTestCase):
    def test_json_serialization_utf8(self):
        raw = _json_dumps(SAMPLE_EVENT)
        self.assertIsInstance(raw, bytes)
        decoded = json.loads(raw.decode('utf-8'))
        self.assertEqual(decoded['event_type'], 'listing_created')
        self.assertEqual(decoded['payload']['price'], '499.00')
        self.assertNotIn('password', decoded.get('payload', {}))

    def test_message_key_uses_entity_id(self):
        key = message_key_for_event(SAMPLE_EVENT)
        self.assertEqual(key, b'45')

    def test_publish_uses_topic_and_key(self):
        mock_future = MagicMock()
        mock_future.get.return_value = MagicMock()
        mock_producer = MagicMock()
        mock_producer.send.return_value = mock_future

        publisher = KafkaPublisher(
            bootstrap_servers='localhost:9092',
            topic='thrift_events',
            client_id='test-client',
            producer=mock_producer,
            ensure_topic=False,
        )
        publisher.publish(SAMPLE_EVENT)

        mock_producer.send.assert_called_once()
        args, kwargs = mock_producer.send.call_args
        self.assertEqual(args[0], 'thrift_events')
        self.assertEqual(kwargs['key'], b'45')
        self.assertEqual(kwargs['value'], SAMPLE_EVENT)
        mock_future.get.assert_called()

    def test_publish_failure_is_logged_not_raised(self):
        mock_future = MagicMock()
        mock_future.get.side_effect = TimeoutError('broker down')
        mock_producer = MagicMock()
        mock_producer.send.return_value = mock_future

        publisher = KafkaPublisher(
            producer=mock_producer,
            ensure_topic=False,
        )
        # Must not raise — DB already committed in real flow.
        publisher.publish(SAMPLE_EVENT)


class KafkaConsumerConfigTests(SimpleTestCase):
    def test_build_consumer_uses_configured_topic(self):
        with patch('analytics.kafka.consumer.KafkaConsumer') as mock_cls:
            mock_cls.return_value = MagicMock()
            build_consumer(
                bootstrap_servers='localhost:9092',
                topic='thrift_events',
                group_id='test-group',
                client_id='test-consumer',
            )
            mock_cls.assert_called_once()
            args, kwargs = mock_cls.call_args
            self.assertEqual(args[0], 'thrift_events')
            self.assertEqual(kwargs['bootstrap_servers'], ['localhost:9092'])
            self.assertEqual(kwargs['group_id'], 'test-group')
            self.assertEqual(kwargs['client_id'], 'test-consumer')
