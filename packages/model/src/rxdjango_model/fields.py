from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rxdjango.rx import RxField, _propagate_to_memos


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
        _tracked_serializers.add(self.serializer_class)

    def __set_name__(self, owner, name):
        self.name = name

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
        if value is None:
            return None
        data = self.serializer_class(value, many=self.many).data
        return _plain(data)

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
