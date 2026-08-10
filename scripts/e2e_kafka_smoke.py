#!/usr/bin/env python
"""
Phase 2 Kafka end-to-end smoke (requires a running broker).

Usage:
  docker compose up -d
  KAFKA_ENABLED=true USE_SQLITE=1 python scripts/e2e_kafka_smoke.py

This script publishes via KafkaPublisher and reads once from thrift_events.
"""

from __future__ import annotations

import json
import os
import sys
import time

# Ensure repo root is importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thrift_store.settings')
os.environ.setdefault('USE_SQLITE', '1')
os.environ['KAFKA_ENABLED'] = 'true'

import django

django.setup()

from kafka import KafkaConsumer

from analytics.events.builder import (
    build_listing_created_event,
    build_listing_deleted_event,
    build_listing_updated_event,
    build_user_registered_event,
    build_wishlist_added_event,
    build_wishlist_removed_event,
    clone_product_state,
)
from analytics.kafka.config import kafka_bootstrap_servers, kafka_topic
from analytics.kafka.producer import KafkaPublisher
from django.contrib.auth.models import User
from store.models import Product, Wishlist


def main() -> int:
    publisher = KafkaPublisher()
    publisher.ensure_topic_exists()

    user = User.objects.create_user(
        username=f'kafka_smoke_{int(time.time())}',
        email='kafka@uni.edu',
        password='pass12345',
    )
    events = [build_user_registered_event(user)]

    product = Product.objects.create(
        title='Kafka Smoke Item',
        description='temp',
        price='100.00',
        category='Misc',
        user=user,
    )
    events.append(build_listing_created_event(product=product, actor_id=user.id))

    previous = clone_product_state(product)
    product.price = '90.00'
    product.save()
    updated = build_listing_updated_event(
        previous=previous,
        current=product,
        actor_id=user.id,
        actor_is_superuser=False,
    )
    assert updated is not None
    events.append(updated)

    wish = Wishlist.objects.create(user=user, product=product)
    events.append(
        build_wishlist_added_event(wishlist_item=wish, product=product, actor_id=user.id)
    )
    events.append(
        build_wishlist_removed_event(
            wishlist_id=wish.id,
            product=product,
            actor_id=user.id,
        )
    )
    wish.delete()
    events.append(build_listing_deleted_event(product=product, actor_id=user.id))
    product.delete()

    for event in events:
        publisher.publish(event)
    publisher.close()

    consumer = KafkaConsumer(
        kafka_topic(),
        bootstrap_servers=kafka_bootstrap_servers().split(','),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        consumer_timeout_ms=15000,
        group_id=f'e2e-smoke-{int(time.time())}',
        value_deserializer=lambda raw: json.loads(raw.decode('utf-8')),
    )

    seen = set()
    expected = {e['event_type'] for e in events}
    for message in consumer:
        event = message.value
        if event.get('event_id') in {e['event_id'] for e in events}:
            seen.add(event['event_type'])
            print(json.dumps(event, indent=2))
        if expected <= seen:
            break
    consumer.close()

    User.objects.filter(id=user.id).delete()

    missing = expected - seen
    if missing:
        print('MISSING EVENT TYPES:', sorted(missing), file=sys.stderr)
        return 1
    print('E2E OK — received:', sorted(seen))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
