"""
Inspect thrift_events by consuming and logging JSON payloads.

Phase 2 verification only — does not write to S3 or transform data.

Usage (from repo root, with Kafka running and KAFKA_ENABLED optional):

    python -m analytics.kafka.consumer
"""

from __future__ import annotations

import json
import logging
import signal
import sys

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from analytics.kafka.config import (
    kafka_bootstrap_servers,
    kafka_client_id,
    kafka_consumer_group,
    kafka_topic,
)
from analytics.kafka.producer import KafkaPublisher

logger = logging.getLogger(__name__)


def build_consumer(
    *,
    bootstrap_servers: str | None = None,
    topic: str | None = None,
    group_id: str | None = None,
    client_id: str | None = None,
) -> KafkaConsumer:
    servers = bootstrap_servers or kafka_bootstrap_servers()
    topic_name = topic or kafka_topic()
    return KafkaConsumer(
        topic_name,
        bootstrap_servers=servers.split(','),
        client_id=client_id or f'{kafka_client_id()}-consumer',
        group_id=group_id or kafka_consumer_group(),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        value_deserializer=lambda raw: json.loads(raw.decode('utf-8')),
        key_deserializer=lambda raw: raw.decode('utf-8') if raw else None,
    )


def run_consumer() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )

    topic = kafka_topic()
    bootstrap = kafka_bootstrap_servers()
    logger.info('Ensuring topic exists: %s @ %s', topic, bootstrap)
    publisher = KafkaPublisher(bootstrap_servers=bootstrap, topic=topic)
    try:
        publisher.ensure_topic_exists()
    finally:
        publisher.close()

    logger.info('Starting consumer on topic=%s bootstrap=%s', topic, bootstrap)
    try:
        consumer = build_consumer()
    except KafkaError as exc:
        logger.error(
            'Failed to start Kafka consumer at %s: %s. '
            'Start local Kafka with: docker compose up -d',
            bootstrap,
            exc,
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.error(
            'Failed to start Kafka consumer at %s: %s. '
            'Start local Kafka with: docker compose up -d',
            bootstrap,
            exc,
        )
        return 1
    stop = False

    def _handle_stop(signum, frame):  # noqa: ANN001, ARG001
        nonlocal stop
        stop = True
        logger.info('Shutdown signal received; stopping consumer...')

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    try:
        while not stop:
            records = consumer.poll(timeout_ms=1000)
            for _tp, messages in records.items():
                for message in messages:
                    event = message.value
                    print(
                        json.dumps(
                            {
                                'partition': message.partition,
                                'offset': message.offset,
                                'key': message.key,
                                'event': event,
                            },
                            indent=2,
                            default=str,
                        ),
                        flush=True,
                    )
    finally:
        consumer.close()
        logger.info('Consumer closed')
    return 0


def main() -> None:
    sys.exit(run_consumer())


if __name__ == '__main__':
    main()
