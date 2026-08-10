"""Kafka producer publisher implementing the Phase 1 publisher interface."""

from __future__ import annotations

import json
import logging
from typing import Any

from kafka import KafkaAdminClient, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError

from analytics.kafka.config import (
    kafka_bootstrap_servers,
    kafka_client_id,
    kafka_topic,
)

logger = logging.getLogger(__name__)

# Keep request latency bounded for this portfolio/dev setup.
_REQUEST_TIMEOUT_MS = 5000
_FLUSH_TIMEOUT_SECONDS = 5.0


def _json_dumps(event: dict[str, Any]) -> bytes:
    return json.dumps(event, default=str, separators=(',', ':')).encode('utf-8')


def message_key_for_event(event: dict[str, Any]) -> bytes | None:
    """
    Use entity_id as the Kafka message key.

    Same-entity events (e.g. updates to one product) share a key so a single
    partition can preserve relative order for that entity. This is not a full
    ordering strategy across the marketplace — just a simple, deterministic key.
    """
    entity_id = event.get('entity_id')
    if entity_id is None:
        return None
    return str(entity_id).encode('utf-8')


class KafkaPublisher:
    """
    Publish analytics event dicts to Kafka as UTF-8 JSON.

    Delivery semantics for this project: best-effort after DB commit.
    Failures are logged; they do not roll back MySQL/SQLite.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        topic: str | None = None,
        client_id: str | None = None,
        producer: KafkaProducer | None = None,
        ensure_topic: bool = True,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers or kafka_bootstrap_servers()
        self.topic = topic or kafka_topic()
        self.client_id = client_id or kafka_client_id()
        self._producer = producer
        self._ensure_topic = ensure_topic
        self._topic_ready = False

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(','),
                client_id=self.client_id,
                acks=1,
                retries=1,
                request_timeout_ms=_REQUEST_TIMEOUT_MS,
                linger_ms=5,
                # Keys/values prepared as bytes by this module.
                key_serializer=None,
                value_serializer=_json_dumps,
            )
        return self._producer

    def ensure_topic_exists(self) -> None:
        """Create thrift_events (or configured topic) if missing."""
        if self._topic_ready or not self._ensure_topic:
            return
        admin = None
        try:
            admin = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers.split(','),
                client_id=f'{self.client_id}-admin',
                request_timeout_ms=_REQUEST_TIMEOUT_MS,
            )
            topic = NewTopic(name=self.topic, num_partitions=1, replication_factor=1)
            admin.create_topics([topic], validate_only=False)
            logger.info('Created Kafka topic %s', self.topic)
        except TopicAlreadyExistsError:
            logger.debug('Kafka topic already exists: %s', self.topic)
        except KafkaError as exc:
            # Auto-create may still succeed on produce; log and continue.
            logger.warning('Could not ensure Kafka topic %s: %s', self.topic, exc)
        finally:
            if admin is not None:
                try:
                    admin.close()
                except Exception:  # noqa: BLE001 - best-effort close
                    pass
            self._topic_ready = True

    def publish(self, event: dict[str, Any]) -> None:
        try:
            self.ensure_topic_exists()
            producer = self._get_producer()
            key = message_key_for_event(event)
            future = producer.send(self.topic, key=key, value=event)
            # Bound wait so Django requests do not hang indefinitely.
            future.get(timeout=_FLUSH_TIMEOUT_SECONDS)
            logger.info(
                'Published analytics event type=%s event_id=%s topic=%s',
                event.get('event_type'),
                event.get('event_id'),
                self.topic,
            )
        except Exception as exc:  # noqa: BLE001 - never break the marketplace
            logger.error(
                'Kafka publish failed after DB commit (event retained in OLTP only): '
                'type=%s event_id=%s error=%s',
                event.get('event_type'),
                event.get('event_id'),
                exc,
                exc_info=True,
            )

    def close(self) -> None:
        if self._producer is not None:
            try:
                self._producer.flush(timeout=_FLUSH_TIMEOUT_SECONDS)
                self._producer.close(timeout=_FLUSH_TIMEOUT_SECONDS)
            except Exception:  # noqa: BLE001
                logger.exception('Error closing Kafka producer')
            finally:
                self._producer = None
