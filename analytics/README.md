# Analytics platform (Phase 1+)

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

Publisher: logging / in-memory for tests. **No Kafka yet.**

### Layout

```
analytics/
  events/
    types.py
    builder.py
    publisher.py
```

### Run event tests

```bash
USE_SQLITE=1 python manage.py test store.tests_events
```

## Not implemented yet

Kafka, S3, Airflow, dbt, warehouse, Tableau (later phases).
