"""Registry of routing dimensions declared per reactive model (ADR-0018 D1).

Populated at channel-class creation time (`RxModelField.contribute_to_channel`,
driven by `ContextChannelMeta`), exactly like `reactive_registry`'s per-layer
registration: a plain module-level dict populated as an import side effect --
"no runtime registry, no shared discovery state" (list-routing). The same
dimension declared by multiple fields or channels dedupes to one entry, keyed
by the Router's own `key`, so a write emits exactly one broadcast per
distinct dimension *value* in use, never per connection, never per field.

The write path (`rxdjango_model.reactive_model.ReactiveModel`) consults this
registry to know which dimensions a model's committed writes must reach.
"""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .reactive_registry import layers_for

if TYPE_CHECKING:  # pragma: no cover
    from django.db.models import Model

    from .routing import Router


# model class -> { router key: Router }
_registry: dict[type, dict[str, 'Router']] = {}

ROUTE_GROUP_PREFIX = 'rx.route.'


def register_router(model: type, router: 'Router') -> None:
    """Register one Router for its model, deduped by `router.key`.

    Idempotent: a second registration under the same key (two channels
    declaring the same dimension) keeps the first entry, so the same
    dimension value always maps to the same group regardless of how many
    fields/channels declare it.
    """
    _registry.setdefault(model, {}).setdefault(router.key, router)


def routers_for(model: type) -> dict[str, 'Router']:
    return _registry.get(model, {})


def routing_registry() -> dict[type, dict[str, 'Router']]:
    """Return a copy of the registry (for inspection / tests)."""
    return {model: dict(routers) for model, routers in _registry.items()}


def route_group_name(model_label: str, key: str, value: Any) -> str:
    """Build the channel-layer group name for one dimension value
    (design D1): `rx.route.<model_label>.<router key>.<hash(value)>`. Values
    are hashed (rather than interpolated directly) so opaque tuples work and
    the group name stays channel-layer-legal regardless of the value's own
    shape."""
    digest = hashlib.sha1(repr(value).encode()).hexdigest()[:16]
    return f'{ROUTE_GROUP_PREFIX}{model_label}.{key}.{digest}'


def _filter_none(values: Any) -> list[Any]:
    return [v for v in values if v is not None]


def route_groups_for_router(router: 'Router', model: type, values: Any) -> list[str]:
    """Group names `values` maps to for one specific `router` on `model`
    (design D1): the groups a field's own `subscribe()` result joins. Scoped
    to a single router -- a model may register more than one dimension, and
    a field's subscribe values only mean anything under its own router's
    key."""
    model_label = model._meta.label_lower
    return list(dict.fromkeys(
        route_group_name(model_label, router.key, value)
        for value in _filter_none(values)
    ))


def routing_pre_image(model: type, pk: Any, using: str | None, update_fields: Any) -> 'Model | Any | None':
    """Read the old input-column values of a routed model's row, gated by
    `update_fields` (task 2.2): `None` when no read is needed -- no routers
    registered, or `update_fields` given and disjoint from every router's
    declared `columns` -- otherwise an object with attribute access to the
    read columns (a full model instance when any registered Router omits
    `columns`, forcing a full-row pre-image; a lightweight namespace over
    just the declared columns otherwise).
    """
    routers = routers_for(model)
    if not routers:
        return None

    needs_full_row = any(router.columns is None for router in routers.values())
    all_columns: set[str] = set()
    for router in routers.values():
        all_columns.update(router.columns or ())

    if update_fields is not None and not needs_full_row:
        if not (set(update_fields) & all_columns):
            return None

    manager = model._base_manager
    if using:
        manager = manager.using(using)
    if needs_full_row:
        return manager.filter(pk=pk).first()
    if not all_columns:
        return None
    row = manager.filter(pk=pk).values(*all_columns).first()
    if row is None:
        return None
    from types import SimpleNamespace
    return SimpleNamespace(**row)


def broadcast_routed_write(instance: 'Model', *, creating: bool, old_pre_image: Any = None) -> None:
    """Broadcast a saved reactive row to its registered dimension groups
    (design D2): a creation announces to `publish(new)`; an update
    announces to `publish(old) ∪ publish(new)`, the old side being the
    stateless leave signal for connections subscribed to the value the row
    just left. Called from `transaction.on_commit`, same as
    `reactive_registry.broadcast_instance`.
    """
    model = type(instance)
    routers = routers_for(model)
    if not routers:
        return
    layers = layers_for(model)
    if not layers:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    model_label = model._meta.label_lower
    groups: set[str] = set()
    for router in routers.values():
        for value in _filter_none(router.publish(instance)):
            groups.add(route_group_name(model_label, router.key, value))
        if not creating and old_pre_image is not None:
            for value in _filter_none(router.publish(old_pre_image)):
                groups.add(route_group_name(model_label, router.key, value))
    if not groups:
        return

    kind = 'create' if creating else 'update'
    for instance_type, state_model in layers.items():
        payload = state_model.serialize_instance(instance)
        for group in groups:
            async_to_sync(channel_layer.group_send)(
                group, {'type': 'rx.route', 'payload': payload, 'kind': kind},
            )


def broadcast_routed_delete(instance: 'Model', pk: Any, version: int) -> None:
    """Broadcast a versioned delete event to a deleted row's dimension
    groups (design D2): the tombstone reaches `publish(row)`, read from
    `instance` before deletion cleared its pk (mirrors
    `reactive_registry.broadcast_delete`'s captured-`pk` convention)."""
    model = type(instance)
    routers = routers_for(model)
    if not routers:
        return
    layers = layers_for(model)
    if not layers:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    model_label = model._meta.label_lower
    groups: set[str] = set()
    for router in routers.values():
        for value in _filter_none(router.publish(instance)):
            groups.add(route_group_name(model_label, router.key, value))
    if not groups:
        return

    for instance_type in layers:
        payload = {'_type': instance_type, '_del': pk, '_v': version}
        for group in groups:
            async_to_sync(channel_layer.group_send)(
                group, {'type': 'rx.route', 'payload': payload, 'kind': 'delete'},
            )
