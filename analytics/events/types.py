"""Marketplace analytics event types (Phase 1)."""

USER_REGISTERED = 'user_registered'
LISTING_CREATED = 'listing_created'
LISTING_UPDATED = 'listing_updated'
LISTING_DELETED = 'listing_deleted'
WISHLIST_ADDED = 'wishlist_added'
WISHLIST_REMOVED = 'wishlist_removed'

ALL_EVENT_TYPES = frozenset({
    USER_REGISTERED,
    LISTING_CREATED,
    LISTING_UPDATED,
    LISTING_DELETED,
    WISHLIST_ADDED,
    WISHLIST_REMOVED,
})

SCHEMA_VERSION = 1

# Product fields compared for listing_updated.
LISTING_TRACKED_FIELDS = (
    'title',
    'description',
    'price',
    'category',
    'image',
)
