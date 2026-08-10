"""Event publishing interface.

Phase 1: log events only. No Kafka broker is required.
Phase 2 will swap in a Kafka-backed publisher behind the same API.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from django.db import transaction

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    def publish(self, event: dict) -> None:
        ...


class LoggingPublisher:
    """Default Phase 1 publisher: write JSON events to application logs."""

    def publish(self, event: dict) -> None:
        logger.info('analytics_event %s', json.dumps(event, default=str))


class RecordingPublisher:
    """In-memory publisher for tests."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()

    def of_type(self, event_type: str) -> list[dict]:
        return [event for event in self.events if event.get('event_type') == event_type]


_publisher: EventPublisher | None = None


def get_publisher() -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = LoggingPublisher()
    return _publisher


def set_publisher(publisher: EventPublisher | None) -> None:
    """Replace the active publisher (used by tests). Pass None to reset."""
    global _publisher
    _publisher = publisher


def publish_event(event: dict) -> None:
    get_publisher().publish(event)


def schedule_event_publish(event: dict | None) -> None:
    """
    Publish after the current DB transaction commits.

    If event is None (e.g. listing_updated with no changes), do nothing.
    """
    if event is None:
        return

    def _publish() -> None:
        publish_event(event)

    transaction.on_commit(_publish)
