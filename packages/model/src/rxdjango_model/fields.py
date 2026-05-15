from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rxdjango.rx import RxField, _propagate_to_memos

from .reactive_registry import register_layer
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

        This hook also populates the reactive index: each ``StateModel`` layer
        backed by a ``ReactiveModel`` is registered so that model's write path
        knows which broadcast groups a row change reaches. ``ContextChannelMeta``
        invokes this for every channel, so the index is complete once all
        channel modules are imported.
        """
        if self.state_model is None:
            self.state_model = StateModel(self.serializer, many=self.many)
        # Imported lazily: ReactiveModel is a Django model and cannot be
        # imported while app modules are still loading.
        from .reactive_model import ReactiveModel
        for layer in self.state_model.models():
            if isinstance(layer.model, type) and issubclass(layer.model, ReactiveModel):
                register_layer(layer)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj, value):
        old = obj.__dict__.get(self.name, self.default)
        obj.__dict__[self.name] = value
        serialized = self.serialize(value)
        consumer = getattr(obj, '_consumer', None)
        if consumer is not None:
            consumer.enqueue_rx(self.name, serialized)
        if old != value:
            _propagate_to_memos(obj, self.name)

    def serialize(self, value: Any) -> Any:
        """Flatten ``value`` into a list of per-layer dicts.

        Each dict carries a ``_type`` marker that lets the frontend
        ``StateBuilder`` rebuild the nested structure.
        """
        if value is None:
            return None
        if self.state_model is None:
            # Channel class wasn't built through the metaclass (e.g. raw
            # use in tests). Build lazily.
            self.state_model = StateModel(self.serializer, many=self.many)
        flat: list[dict[str, Any]] = []
        for layer in self.state_model.serialize_state(value):
            flat.extend(layer)
        return _plain(flat)

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


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value
