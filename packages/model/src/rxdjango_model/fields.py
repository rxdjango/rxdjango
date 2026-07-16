from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from typing import Any

from rest_framework import serializers
from rxdjango.rx import RxField, _propagate_to_memos

from channels.db import database_sync_to_async

from .query_introspection import introspect_queryset
from .reactive_registry import group_name, register_layer
from .routing import ColumnRouter, Router
from .routing_registry import register_router, route_groups_for_router
from .state_model import StateModel


_tracked_serializers: set[type[serializers.BaseSerializer]] = set()
_NoneType = type(None)
_NO_ROUTING = object()


class RxModelField(RxField):
    default = None
    has_default = True
    type = _NoneType
    allowed = (_NoneType,)

    def __init__(self, serializer: serializers.BaseSerializer, routing: Any = _NO_ROUTING) -> None:
        self.serializer = serializer
        self.serializer_class, self.many = _normalize_serializer(serializer)
        self.name = ''
        self.state_model: StateModel | None = None
        self.routing = _resolve_routing(routing, self.many)
        _tracked_serializers.add(self.serializer_class)

    def __set_name__(self, owner, name):
        self.name = name
        if isinstance(self.routing, ColumnRouter):
            self.routing.bind_field(name)

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

        # Routing registers at channel-class creation, i.e. at import of the
        # channel module (list-routing: "registers when the channel module
        # is imported"). Dedup across fields/channels declaring the same
        # dimension happens inside register_router, keyed by the Router's
        # own `key`.
        if self.routing is not None:
            if isinstance(self.routing, ColumnRouter):
                self.routing.bind_model(self.state_model.model)
            register_router(self.state_model.model, self.routing)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj, value):
        old = obj.__dict__.get(self.name, self.default)
        obj.__dict__[self.name] = value
        consumer = getattr(obj, '_consumer', None)
        if consumer is not None:
            if value is None:
                consumer.deposit_model_walk(self.name, None)
                consumer.enqueue_rx(self.name, None)
            else:
                if self.state_model is None:
                    # Channel class wasn't built through the metaclass (e.g.
                    # raw use in tests). Build lazily.
                    self.state_model = StateModel(self.serializer, many=self.many)
                descriptor = None
                if self.many:
                    # Bind-time introspection (ADR-0019 D3): synchronous, so
                    # an unsupported condition or ordering column fails
                    # loudly right here, before any layer is queried.
                    descriptor = introspect_queryset(value, self.state_model).to_wire()
                    if self.routing is not None:
                        # Live marker (ADR-0018 design D5, wire-protocol):
                        # tells the client this field's membership basis may
                        # grow from qualifying events, not just shrink.
                        descriptor['l'] = True
                consumer.deposit_model_walk(self.name, self._walk_layers(value, obj, descriptor))
        if old != value:
            _propagate_to_memos(obj, self.name)

    async def _walk_layers(
        self, value: Any, channel: Any, descriptor: dict[str, Any] | None = None,
    ) -> AsyncGenerator[tuple[Any, list[str], dict[str, Any] | None], None]:
        """Bridge deposited on the consumer for it to drain (design D6).

        ``__set__`` is a sync descriptor and cannot await the layered walk,
        so it hands the consumer this not-yet-started async generator instead
        of running it. Nothing in an async generator's body executes until it
        is first iterated, so a reassignment that replaces this deposit
        before drain leaves the superseded generator inert — it is garbage
        collected having sent no frames and issued no queries.

        Yields one ``(plain_layer, groups, q)`` triple per layer: the flat,
        JSON-safe instance list, the reactive broadcast groups it implies
        (one per reactive instance in the layer, so the consumer can join
        them immediately before sending that layer's frame), and the bind
        descriptor -- non-``None`` only on the walk's first (anchor) layer of
        a ``many=True`` field (ADR-0019 D1), ``None`` on every other frame.

        For a routed field (ADR-0018 design D3), the first layer's groups
        additionally carry the dimension groups ``self.routing.subscribe(channel)``
        resolves to -- computed off the event loop, since a custom Router's
        ``subscribe`` may query the database. Joining them alongside the
        anchor's own per-instance groups, before that frame is sent, is
        "consumer bind... joins the dimension groups" (list-routing): one
        join-before-send mechanism, reused rather than duplicated.
        """
        first = True
        dimension_groups: list[str] = []
        if self.routing is not None:
            dimension_groups = await database_sync_to_async(self._dimension_groups)(channel)
        async for node, layer in self.state_model.serialize_state(value):
            groups: list[str] = []
            if node.reactive:
                for item in layer:
                    instance_id = item.get('id')
                    if instance_id is not None:
                        groups.append(group_name(node.instance_type, instance_id))
            if first and dimension_groups:
                groups = groups + dimension_groups
            yield _plain(layer), groups, (descriptor if first else None)
            first = False

    def _dimension_groups(self, channel: Any) -> list[str]:
        """``subscribe(channel)`` resolved to this field's dimension groups
        (ADR-0018 design D1/D3), ``None`` values filtered by
        ``route_groups_for_router``, scoped to *this* field's own Router --
        a model may register more than one dimension, and a field's
        subscribed values only mean anything under its own Router's key.
        """
        assert self.routing is not None
        values = self.routing.subscribe(channel)
        return route_groups_for_router(self.routing, self.state_model.model, values)

    def __repr__(self):
        return f'rx.model({self.serializer!r})'


def model(serializer: serializers.BaseSerializer, routing: Any = _NO_ROUTING) -> RxModelField:
    return RxModelField(serializer, routing)


def install_model_field() -> None:
    RxField.model = staticmethod(model)


def tracked_serializers() -> set[type[serializers.BaseSerializer]]:
    return set(_tracked_serializers)


def _resolve_routing(routing: Any, many: bool) -> Router | None:
    """Validate and normalize the `routing=` argument (list-routing:
    "Router declaration on `many=True` fields"). Returns `None` for a
    static field (routing omitted entirely); a column string becomes
    `ColumnRouter` sugar; a `Router` instance passes through unchanged.
    `routing=None` and routing on a single-instance field are declaration-
    time errors.
    """
    if routing is _NO_ROUTING:
        return None
    if routing is None:
        raise TypeError(
            'rx.model(..., routing=None) is invalid; omit routing entirely '
            'for a static list (ADR-0018)'
        )
    if not many:
        raise TypeError(
            'routing= is only valid on a many=True rx.model field (ADR-0018)'
        )
    if isinstance(routing, str):
        return ColumnRouter(routing)
    if isinstance(routing, Router):
        return routing
    raise TypeError(
        'routing= must be a column name (str), a Router instance, or '
        f'omitted; got {type(routing).__name__}'
    )


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
