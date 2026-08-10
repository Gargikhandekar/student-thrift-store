"""Kafka configuration from environment variables."""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def kafka_enabled() -> bool:
    return _env_bool('KAFKA_ENABLED', default=False)


def kafka_bootstrap_servers() -> str:
    return os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').strip()


def kafka_topic() -> str:
    return os.environ.get('KAFKA_TOPIC', 'thrift_events').strip()


def kafka_client_id() -> str:
    return os.environ.get('KAFKA_CLIENT_ID', 'thrift-store-app').strip()


def kafka_consumer_group() -> str:
    return os.environ.get('KAFKA_CONSUMER_GROUP', 'thrift-store-inspect').strip()
