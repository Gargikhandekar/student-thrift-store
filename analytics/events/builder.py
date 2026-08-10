"""Build canonical analytics event envelopes from Django model state."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from django.contrib.auth.models import User
from django.utils import timezone

from store.models import Product, Wishlist

from .types import (
    LISTING_CREATED,
    LISTING_DELETED,
    LISTING_TRACKED_FIELDS,
    LISTING_UPDATED,
    SCHEMA_VERSION,
    USER_REGISTERED,
    WISHLIST_ADDED,
    WISHLIST_REMOVED,
)


def _price_str(value: Decimal | str | int | float | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, 'f')
    return format(Decimal(str(value)), 'f')


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.isoformat()


def _has_image(product: Product) -> bool:
    return bool(getattr(product, 'image', None) and product.image.name)


def _image_name(product: Product) -> str | None:
    if not _has_image(product):
        return None
    return product.image.name


def _listing_snapshot(product: Product) -> dict[str, Any]:
    return {
        'title': product.title,
        'description_present': bool(product.description),
        'price': _price_str(product.price),
        'category': product.category,
        'has_image': _has_image(product),
        'image_name': _image_name(product),
    }


def build_envelope(
    *,
    event_type: str,
    user_id: int | None,
    entity_type: str,
    entity_id: int | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        'event_id': str(uuid4()),
        'event_type': event_type,
        'event_time': timezone.now().isoformat(),
        'schema_version': SCHEMA_VERSION,
        'user_id': user_id,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'payload': payload,
    }


def build_user_registered_event(user: User) -> dict[str, Any]:
    return build_envelope(
        event_type=USER_REGISTERED,
        user_id=user.id,
        entity_type='user',
        entity_id=user.id,
        payload={
            'username': user.username,
            'email': user.email or '',
        },
    )


def build_listing_created_event(*, product: Product, actor_id: int) -> dict[str, Any]:
    return build_envelope(
        event_type=LISTING_CREATED,
        user_id=actor_id,
        entity_type='product',
        entity_id=product.id,
        payload={
            'seller_id': product.user_id,
            'title': product.title,
            'price': _price_str(product.price),
            'category': product.category,
            'has_image': _has_image(product),
            'created_at': _iso(product.created_at),
        },
    )


def diff_listing(previous: Product, current: Product) -> list[str]:
    """Return tracked field names that changed between two Product states."""
    changed: list[str] = []
    for field in LISTING_TRACKED_FIELDS:
        if field == 'image':
            if _image_name(previous) != _image_name(current):
                changed.append('image')
            continue
        if field == 'price':
            if _price_str(previous.price) != _price_str(current.price):
                changed.append('price')
            continue
        if getattr(previous, field) != getattr(current, field):
            changed.append(field)
    return changed


def build_listing_updated_event(
    *,
    previous: Product,
    current: Product,
    actor_id: int,
    actor_is_superuser: bool,
) -> dict[str, Any] | None:
    changed_fields = diff_listing(previous, current)
    if not changed_fields:
        return None

    return build_envelope(
        event_type=LISTING_UPDATED,
        user_id=actor_id,
        entity_type='product',
        entity_id=current.id,
        payload={
            'seller_id': current.user_id,
            'actor_is_superuser': actor_is_superuser,
            'changed_fields': changed_fields,
            'previous': _listing_snapshot(previous),
            'current': {
                **_listing_snapshot(current),
                'updated_at': _iso(current.updated_at),
            },
        },
    )


def build_listing_deleted_event(
    *,
    product: Product,
    actor_id: int,
) -> dict[str, Any]:
    return build_envelope(
        event_type=LISTING_DELETED,
        user_id=actor_id,
        entity_type='product',
        entity_id=product.id,
        payload={
            'seller_id': product.user_id,
            'title': product.title,
            'price': _price_str(product.price),
            'category': product.category,
            'has_image': _has_image(product),
            'created_at': _iso(product.created_at),
            'deleted_by_owner': actor_id == product.user_id,
        },
    )


def build_wishlist_added_event(
    *,
    wishlist_item: Wishlist,
    product: Product,
    actor_id: int,
) -> dict[str, Any]:
    return build_envelope(
        event_type=WISHLIST_ADDED,
        user_id=actor_id,
        entity_type='wishlist',
        entity_id=wishlist_item.id,
        payload={
            'product_id': product.id,
            'seller_id': product.user_id,
            'category': product.category,
            'price': _price_str(product.price),
            'added_at': _iso(wishlist_item.added_at),
        },
    )


def build_wishlist_removed_event(
    *,
    wishlist_id: int,
    product: Product,
    actor_id: int,
) -> dict[str, Any]:
    return build_envelope(
        event_type=WISHLIST_REMOVED,
        user_id=actor_id,
        entity_type='wishlist',
        entity_id=wishlist_id,
        payload={
            'product_id': product.id,
            'seller_id': product.user_id,
            'category': product.category,
            'price': _price_str(product.price),
        },
    )


def clone_product_state(product: Product) -> Product:
    """
    Return an unsaved Product carrying tracked field values for before/after diffs.

    Used so we can compare state after serializer.save() without a second DB round-trip
    for the previous values.
    """
    clone = Product(
        id=product.id,
        title=product.title,
        description=product.description,
        price=product.price,
        category=product.category,
        user_id=product.user_id,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )
    # ImageField: preserve name for comparison without copying file bytes.
    if product.image and product.image.name:
        clone.image.name = product.image.name
    return clone
