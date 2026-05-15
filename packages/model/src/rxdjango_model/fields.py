from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rxdjango.rx import RxField, _propagate_to_memos

from .reactive_registry import group_name, register_layer
from .state_model import StateModel


_tracked_serializers: set[type[serializers.BaseSerializer]] = set()
_NoneType = type(None)


class RxModelField(RxField):
    default = None
    has_default = True
    type = _NoneType
    allowed = (_NoneType,)

    def __init__(self, serializer: serializers.BaseSerializer) -> None:
        self.serializer = serializer
        self.serializer_class, self.many = _normalize_serializer(serializer)
        self.name = ''
        self.state_model: StateModel | None = None
        _tracked_serializers.add(self.serializer_class)

    def __set_name__(self, owner, name):
        self.name = name

    def contribute_to_channel(self, channel_cls, field_name):
        """Build the ``StateModel`` for this field at class-creation time.

        Building eagerly lets us catch serializer-shape errors at import time
        and lets the generated frontend emit a runtime model map without
        re-introspecting at request time.

        This hook does three compile-time jobs, each of which would otherwise
        cost per-connection or per-message work:

        * builds the ``StateModel`` once,
        * extends ``channel_cls._model_field_types``, the ``instance_type`` →
          field-name map the consumer uses to route a group broadcast back to
          the right rx.model field,
        * registers every ``StateModel`` layer backed by a ``ReactiveModel`` so
          that model's write path knows which broadcast groups a row change
          reaches, and marks the layer ``reactive`` so serialization can emit
          its group names directly.

        ``ContextChannelMeta`` invokes this for every channel, so both the
        field-type map and the reactive index are complete once all channel
        modules are imported.
        """
        if self.state_model is None:
            self.state_model = StateModel(self.serializer, many=self.many)

        # Per-class map, never inherited from a base channel.
        field_types = channel_cls.__dict__.get('_model_field_types')
        if field_types is None:
            field_types = {}
            channel_cls._model_field_types = field_types
        for instance_type in self.state_model.index:
            field_types[instance_type] = field_name

        # Imported lazily: ReactiveModel is a Django model and cannot be
        # imported while app modules are still loading.
        from .reactive_model import ReactiveModel
        for layer in self.state_model.models():
            if isinstance(layer.model, type) and issubclass(layer.model, ReactiveModel):
                layer.reactive = True
                register_layer(layer)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj, value):
        old = obj.__dict__.get(self.name, self.default)
        obj.__dict__[self.name] = value
        serialized, groups = self.serialize(value)
        consumer = getattr(obj, '_consumer', None)
        if consumer is not None:
            consumer.enqueue_rx(self.name, serialized, groups)
        if old != value:
            _propagate_to_memos(obj, self.name)

    def serialize(self, value: Any) -> tuple[Any, list[str]]:
        """Flatten ``value`` into a list of per-layer dicts plus its groups.

        Each dict carries a ``_type`` marker that lets the frontend
        ``StateBuilder`` rebuild the nested structure. The second element is
        the broadcast groups the consumer must join — one per reactive
        instance in the payload, collected during the same walk that builds
        the flat list, so no extra pass over the data is needed.
        """
        if value is None:
            return None, []
        if self.state_model is None:
            # Channel class wasn't built through the metaclass (e.g. raw
            # use in tests). Build lazily.
            self.state_model = StateModel(self.serializer, many=self.many)
        flat: list[dict[str, Any]] = []
        groups: list[str] = []
        for node, layer in self.state_model.serialize_state(value):
            flat.extend(layer)
            if node.reactive:
                for item in layer:
                    instance_id = item.get('id')
                    if instance_id is not None:
                        groups.append(group_name(node.instance_type, instance_id))
        return flat, groups

    def __repr__(self):
        return f'rx.model({self.serializer!r})'


def model(serializer: serializers.BaseSerializer) -> RxModelField:
    return RxModelField(serializer)


def install_model_field() -> None:
    RxField.model = staticmethod(model)


def tracked_serializers() -> set[type[serializers.BaseSerializer]]:
    return set(_tracked_serializers)


def _normalize_serializer(serializer: serializers.BaseSerializer):
    if isinstance(serializer, serializers.ListSerializer):
        child = serializer.child
        if not isinstance(child, serializers.BaseSerializer):
            raise TypeError('rx.model(...) list serializers must wrap a DRF serializer')
        return child.__class__, True
    if isinstance(serializer, serializers.BaseSerializer):
        return serializer.__class__, False
    raise TypeError(
        'rx.model(...) requires a DRF serializer instance, '
        f'got {type(serializer).__name__}'
    )
