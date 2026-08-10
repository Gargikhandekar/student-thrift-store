# Analytics platform

## Phase 1 — Event contract (implemented)

The marketplace API emits analytics events **after successful DB commits**
using `transaction.on_commit()`.

Events:

- `user_registered`
- `listing_created`
- `listing_updated` (skipped when no tracked fields change)
- `listing_deleted`
- `wishlist_added`
- `wishlist_removed`

### Layout

```
analytics/
  events/          # builders + publisher abstraction
  kafka/           # Phase 2 producer/consumer
```

### Run event tests

```bash
USE_SQLITE=1 python manage.py test store.tests_events analytics.tests_kafka
```

## Phase 2 — Kafka (implemented)

### Why Kafka?

MySQL remains the **transactional source of truth**. Kafka carries a stream of
marketplace events so analytics tooling does not repeatedly poll OLTP.

```
Django view
   ↓
MySQL (commit)
   ↓
transaction.on_commit
   ↓
Kafka Producer  (only if KAFKA_ENABLED=true)
   ↓
topic: thrift_events
   ↓
Kafka Consumer  (inspect / log JSON)
```

### Why one topic?

`thrift_events` holds all six event types. The `event_type` field distinguishes
them. Separate topics would add ops complexity without benefit at this scale.

### Message key

Kafka records use `entity_id` as the message key so events for the same entity
can share a partition and keep relative order for that entity.

### Local Kafka (Docker Compose, KRaft, no ZooKeeper)

Image: `apache/kafka:3.8.1` (pinned).

```bash
docker compose up -d
docker compose ps
```

### Enable publishing from Django

In `.env` (never commit real `.env`):

```
KAFKA_ENABLED=true
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=thrift_events
KAFKA_CLIENT_ID=thrift-store-app
```

Marketplace without Kafka (default):

```
KAFKA_ENABLED=false
```

No broker connection is attempted when disabled.

### Run consumer (inspect events)

```bash
# from repo root, venv active, Kafka up
python -m analytics.kafka.consumer
```

### End-to-end checklist

1. `docker compose up -d`
2. `python -m analytics.kafka.consumer`
3. `KAFKA_ENABLED=true USE_SQLITE=1 python manage.py runserver`
4. Register, create listing, update price, wishlist add/remove, delete listing
5. Confirm consumer prints all six `event_type` values

### Failure behavior

- DB commit succeeds, then Kafka fails → error is **logged**; HTTP still succeeds;
  OLTP data is kept. This is an intentional delivery gap (no outbox yet).
- Producer waits a short bounded timeout; it does not hang forever.
- Delivery is **best-effort**, not exactly-once.

### Topic creation

The producer/consumer ensure `thrift_events` exists via the Admin API
(1 partition, replication factor 1). Broker auto-create remains enabled as a
safety net.

## NOT YET IMPLEMENTED

- S3 raw event storage
- AWS data pipeline beyond future S3 plans
- Airflow
- Data warehouse
- dbt
- Tableau
