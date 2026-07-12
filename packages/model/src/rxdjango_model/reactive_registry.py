"""Registry mapping reactive Django models to their channel state layers.

Populated at channel-class creation time (``RxModelField.contribute_to_channel``,
driven by ``ContextChannelMeta``): for every ``StateModel`` layer whose Django
model is a ``ReactiveModel`` subclass, the layer is registered here keyed by
model class. The write path on ``ReactiveModel`` consults this registry to know
which serializer shapes — and therefore which broadcast groups — a row change
must reach.

A broadcast group is named ``rx.<serializer dotted path>.<instance id>``. The
serializer dotted path is the layer's ``instance_type``; a consumer that relayed
an instance of that type subscribes to exactly this group, so a row change is
delivered only to clients that hold it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

if TYPE_CHECKING:  # pragma: no cover
    from django.db.models import Model

    from .state_model import StateModel


# model class -> { instance_type: StateModel layer }
_registry: dict[type, dict[str, "StateModel"]] = {}

GROUP_PREFIX = "rx."


def group_name(instance_type: str, instance_id: Any) -> str:
    """Build the channel-layer group name for one reactive instance."""
    return f"{GROUP_PREFIX}{instance_type}.{instance_id}"


def register_layer(state_model: "StateModel") -> None:
    """Register one ``StateModel`` layer for its reactive Django model.

    Idempotent: re-registering the same ``instance_type`` for a model (two
    channels using the same serializer) keeps a single entry, so a row change
    broadcasts to each group exactly once.
    """
    _registry.setdefault(state_model.model, {})[state_model.instance_type] = state_model


def layers_for(model: type) -> dict[str, "StateModel"]:
    return _registry.get(model, {})


def reactive_registry() -> dict[type, dict[str, "StateModel"]]:
    """Return a copy of the registry (for inspection / tests)."""
    return {model: dict(layers) for model, layers in _registry.items()}


def broadcast_instance(instance: "Model") -> None:
    """Broadcast a created/updated reactive instance to every subscribed client.

    Called from ``transaction.on_commit`` so the serialized snapshot reflects
    committed state. Each registered layer renders its own flat instance — the
    same ``_type``-tagged shape the client ``StateBuilder`` reconciles by ``_v``.
    """
    layers = _registry.get(type(instance))
    if not layers:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    for instance_type, state_model in layers.items():
        payload = state_model.serialize_instance(instance)
        async_to_sync(channel_layer.group_send)(
            group_name(instance_type, instance.pk),
            {"type": "rx.broadcast", "payload": payload},
        )


def broadcast_delete(model: type, pk: Any, version: int) -> None:
    """Broadcast a versioned delete event for a reactive instance.

    The event carries ``version`` (the deleted row's final ``_v + 1``) so a
    client can discard a stale snapshot of the row and keep it deleted.
    """
    layers = _registry.get(model)
    if not layers:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    for instance_type in layers:
        payload = {"_type": instance_type, "_del": pk, "_v": version}
        async_to_sync(channel_layer.group_send)(
            group_name(instance_type, pk),
            {"type": "rx.broadcast", "payload": payload},
        )
