from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Iterator

from channels.db import database_sync_to_async
from rest_framework import serializers
from django.db.models import Model
from django.db.models.fields import related_descriptors


@dataclass(frozen=True)
class LayerEdge:
    """One relation field on an already-flushed layer that feeds pks into
    another layer's ``pk__in`` set (design D1)."""

    source_type: str
    field_name: str


@dataclass(frozen=True)
class LayerPlanEntry:
    """One instance type's slot in the compiled breadth-first layer plan.

    ``node`` is the representative ``StateModel`` for this type (per the
    existing ``index[type][0]`` convention also used by ``frontend_model``) —
    its ``model``/flat serializer are shared by every occurrence of the type
    in the tree, so a single entry and a single query cover them all.
    """

    type_key: str
    model: type
    node: 'StateModel'
    edges: tuple[LayerEdge, ...]
    rank: int


class StateModel:
    """Compile-time introspection of a nested ``ModelSerializer``.

    Walks the serializer tree once and produces, for every node:

    * a *flat* serializer (nested serializer fields replaced with
      ``PrimaryKeyRelatedField``) used to render each layer over the wire,
    * the relation map between layers used by the frontend ``StateBuilder``
      to rebuild the nested structure from those flat layers.
    """

    def __init__(
        self,
        state_serializer: serializers.ModelSerializer,
        many: bool = False,
        origin: 'StateModel | None' = None,
        needs_prefetch: bool = False,
    ) -> None:
        # Unwrap a `many=True` serializer's `ListSerializer` wrapper once,
        # here, so every caller -- the root field build in
        # `RxModelField.contribute_to_channel` included -- gets the same
        # compiled tree a single-instance declaration would (design D6). A
        # bare `ListSerializer` has no `.fields`; disassembling it without
        # unwrapping is exactly the class-creation crash this fixes.
        if isinstance(state_serializer, serializers.ListSerializer):
            state_serializer = state_serializer.child
            many = True
        self.nested_serializer = state_serializer
        self.many = many
        self.origin = origin
        # True when this node is reached from its parent via a reverse FK,
        # M2M, or reverse O2O descriptor. DRF auto-generates a
        # PrimaryKeyRelatedField for those on the *parent's* flat serializer,
        # and populating it issues one query per parent row unless the
        # parent's queryset prefetches this field name -- a forward FK/O2O
        # needs no such thing, since its pk lives on the row's own `<f>_id`
        # column. See `_prefetch_field_names`.
        self.needs_prefetch = needs_prefetch
        # Set True for layers backed by a ReactiveModel (see
        # RxModelField.contribute_to_channel). A reactive layer means each of
        # its instances carries a broadcast group the consumer must join.
        self.reactive = False

        if origin is None:
            self.index = defaultdict(list)
        else:
            self.index = origin.index

        try:
            meta = state_serializer.Meta
        except AttributeError:
            meta = state_serializer.child.Meta

        self.model = meta.model

        self.instance_type = '.'.join([
            self.nested_serializer.__module__,
            self.nested_serializer.__class__.__name__,
        ])

        self.index[self.instance_type].append(self)

        self.flat_serializer, fields = self._disassemble_nested()
        # One bound instance is reused for every serialization: DRF
        # re-deepcopies all declared fields on each instantiation, so
        # creating a serializer per save is ~25x slower than calling
        # to_representation() on this shared, already-bound instance.
        self._flat_instance = self.flat_serializer()
        self._flat_instance.fields  # bind fields now, not on first save

        self.children: dict[str, StateModel] = {}
        for field_name, serializer in fields.items():
            node = self._build_child(field_name, serializer)
            if node is not None:
                self.children[field_name] = node

        # Compiled breadth-first layer plan (ADR-0016 D1), derived once here
        # at class-creation time rather than re-walked per connection
        # (ADR-0015). Only meaningful from a field's root node, but cheap
        # enough to compute uniformly for every node in the tree.
        self.layer_plan: list[LayerPlanEntry] = self._compile_layer_plan()

    def __str__(self) -> str:
        return f'StateModel for {self.instance_type}'

    def __repr__(self) -> str:
        return str(self)

    def __getitem__(self, key: str) -> 'StateModel':
        return self.children[key]

    def models(self) -> Iterator['StateModel']:
        for nodes in self.index.values():
            for model in nodes:
                yield model

    def frontend_model(self) -> dict[str, dict[str, str]]:
        """Map every ``instance_type`` to its relation map.

        The frontend ``StateBuilder`` uses this to know which fields on a
        flat instance hold child instance ids (vs. plain values).
        """
        frontend: dict[str, dict[str, str]] = {}
        for key, nodes in self.index.items():
            node = nodes[0]
            instance_model: dict[str, str] = {}
            frontend[key] = instance_model
            serializer = node.nested_serializer
            for field_name, field in serializer._declared_fields.items():
                if is_model_serializer(field):
                    instance_model[field_name] = node[field_name].instance_type
        return frontend

    def serialize_instance(self, instance: Model) -> dict[str, Any]:
        data = dict(self._flat_instance.to_representation(instance))
        data['_type'] = self.instance_type
        _attach_version(data, instance)
        return data

    def serialize_delete(self, instance: Model, version: int | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            '_type': self.instance_type,
            '_del': instance.pk,
        }
        if version is not None:
            data['_v'] = version
        return data

    async def serialize_state(
        self, instance: Any
    ) -> AsyncGenerator[tuple['StateModel', list[dict[str, Any]]], None]:
        """Yield ``(node, layer)`` pairs for the nested instance, breadth-first.

        Executes the compiled ``layer_plan`` (ADR-0016 D1/D2) as a pk-first
        walk: the anchor is serialized directly from ``instance``; every
        subsequent layer is discovered from the pk (or pk list) references
        the previous layers' serialized dicts already carry, fetched with one
        ``pk__in`` query per instance type, off the event loop
        (``database_sync_to_async``). A type is (re-)queried whenever new,
        not-yet-fetched pks for it are discovered — whether that happens at
        its plan-shallowest rank or later, from an edge encountered deeper in
        the walk — so query count is O(edges), not O(rows), and no `_type:pk`
        is ever fetched twice.

        Each ``layer`` is a flat list of instances of one ``_type``; ``node``
        is the ``StateModel`` that produced it, so a caller can tell a reactive
        layer from a plain one without re-inspecting the payload.
        """
        entry_by_type = {
            entry.type_key: entry
            for entry in self.layer_plan
            if entry.type_key != self.instance_type
        }
        dependents: dict[str, list[str]] = defaultdict(list)
        for entry in entry_by_type.values():
            for edge in entry.edges:
                dependents[edge.source_type].append(entry.type_key)

        fetched: dict[str, set[Any]] = defaultdict(set)
        layers: dict[str, list[dict[str, Any]]] = defaultdict(list)

        if self.many:
            # A list field's anchor is a bare queryset (ADR-0019): unlike the
            # single-instance case, where the caller already awaited the
            # fetch before assignment, the queryset here is typically
            # unevaluated. Executing it -- and serializing its rows, which
            # may touch needs_prefetch children -- must happen off the event
            # loop, same as every other layer's query (design D2/ADR-0016).
            queryset = instance.all() if hasattr(instance, 'all') else instance
            anchor = await database_sync_to_async(self._fetch_anchor_rows)(queryset)
        else:
            anchor = [self.serialize_instance(instance)]
        layers[self.instance_type] = anchor
        fetched[self.instance_type] = {
            row['id'] for row in anchor if row.get('id') is not None
        }
        yield self, anchor

        queue: deque[str] = deque(dependents.get(self.instance_type, ()))
        queued = set(queue)
        while queue:
            type_key = queue.popleft()
            queued.discard(type_key)
            entry = entry_by_type[type_key]

            pks: set[Any] = set()
            for edge in entry.edges:
                for row in layers.get(edge.source_type, ()):
                    value = row.get(edge.field_name)
                    if value is None:
                        continue
                    if isinstance(value, list):
                        pks.update(value)
                    else:
                        pks.add(value)
            pks -= fetched[type_key]
            if not pks:
                continue

            new_rows = await database_sync_to_async(entry.node._fetch_layer)(pks)
            fetched[type_key].update(
                row['id'] for row in new_rows if row.get('id') is not None
            )
            layers[type_key].extend(new_rows)
            yield entry.node, new_rows

            for dependent in dependents.get(type_key, ()):
                if dependent not in queued:
                    queued.add(dependent)
                    queue.append(dependent)

    def _fetch_layer(self, pks: set[Any]) -> list[dict[str, Any]]:
        """Run this type's ``pk__in`` query and serialize the rows.

        Called via ``database_sync_to_async`` so both the query and the
        serialization happen in the same thread hop (design D2) — lazy
        serializer fields cannot re-enter the ORM on the event loop.

        Prefetches this node's own reverse-relation child fields (see
        ``needs_prefetch``) so serializing this layer's rows costs one extra
        query per such field, not one per row — the walk's own O(edges)
        guarantee would otherwise be undercut from inside a single layer.
        This is not the ``select_related`` folding ADR-0016 forbids: each
        child type is still fetched as its own dedicated layer below.
        """
        queryset = self.model.objects.filter(pk__in=pks)
        prefetch_names = self._prefetch_field_names()
        if prefetch_names:
            queryset = queryset.prefetch_related(*prefetch_names)
        return [self.serialize_instance(row) for row in queryset]

    def _fetch_anchor_rows(self, queryset: Any) -> list[dict[str, Any]]:
        """Evaluate a list field's anchor queryset and serialize its rows.

        Called via ``database_sync_to_async`` (see ``serialize_state``);
        applies the same ``needs_prefetch`` treatment ``_fetch_layer`` gives
        every other layer, so the anchor's own reverse-relation/M2M children
        cost one query per field, not one per row.
        """
        prefetch_names = self._prefetch_field_names()
        if prefetch_names:
            queryset = queryset.prefetch_related(*prefetch_names)
        return [self.serialize_instance(row) for row in queryset]

    def _prefetch_field_names(self) -> list[str]:
        return [name for name, child in self.children.items() if child.needs_prefetch]

    def _compile_layer_plan(self) -> list[LayerPlanEntry]:
        """Derive the ordered breadth-first layer list (design D1).

        A type reachable at multiple depths resolves at its shallowest rank
        (first discovery wins); every edge that can feed it — regardless of
        rank — is still recorded, since the runtime walk fetches late-arriving
        pks for an already-flushed type in the rank where they surface.
        """
        rank_of: dict[str, int] = {self.instance_type: 0}
        order: list[str] = [self.instance_type]
        edges: dict[str, list[LayerEdge]] = defaultdict(list)

        queue: deque['StateModel'] = deque([self])
        while queue:
            node = queue.popleft()
            parent_rank = rank_of[node.instance_type]
            for field_name, child in node.children.items():
                child_type = child.instance_type
                edges[child_type].append(LayerEdge(node.instance_type, field_name))
                if child_type not in rank_of:
                    rank_of[child_type] = parent_rank + 1
                    order.append(child_type)
                    queue.append(child)

        return [
            LayerPlanEntry(
                type_key=type_key,
                model=self.index[type_key][0].model,
                node=self.index[type_key][0],
                edges=tuple(edges[type_key]),
                rank=rank_of[type_key],
            )
            for type_key in order
        ]

    def _disassemble_nested(self) -> tuple[type[serializers.ModelSerializer], dict[str, serializers.BaseSerializer]]:
        serializer_fields: dict[str, serializers.BaseSerializer] = {}
        declared_fields: dict[str, serializers.Field] = {}

        for field_name in self.nested_serializer.fields.keys():
            field = self.nested_serializer._declared_fields.get(field_name)

            if field is None:
                continue

            if is_model_serializer(field):
                serializer_fields[field_name] = field
            else:
                declared_fields[field_name] = field

        FlatSerializer = type(
            self.nested_serializer.__class__.__name__,
            (serializers.ModelSerializer,),
            {
                'Meta': self.nested_serializer.Meta,
                **declared_fields,
            },
        )

        return FlatSerializer, serializer_fields

    def _build_child(self, field_name: str, serializer: serializers.BaseSerializer) -> 'StateModel | None':
        try:
            descriptor = getattr(self.model, field_name)
        except AttributeError:
            return None

        if isinstance(descriptor, related_descriptors.ManyToManyDescriptor):
            return StateModel(serializer.child, many=True, origin=self, needs_prefetch=True)

        if isinstance(descriptor, related_descriptors.ReverseManyToOneDescriptor):
            return StateModel(serializer.child, many=True, origin=self, needs_prefetch=True)

        if isinstance(descriptor, related_descriptors.ForwardManyToOneDescriptor):
            return StateModel(serializer, many=False, origin=self, needs_prefetch=False)

        if isinstance(descriptor, related_descriptors.ReverseOneToOneDescriptor):
            return StateModel(serializer, many=False, origin=self, needs_prefetch=True)

        return None


def _attach_version(data: dict[str, Any], instance: Any) -> None:
    """Copy a ``ReactiveModel`` row's ``_v`` onto its flat layer.

    The version is not a serializer field, so it is welded on here. Layers from
    non-reactive models carry no ``_v``; the client ``StateBuilder`` treats a
    versionless layer as always-apply (such a model emits no events, so there
    is no race to reconcile).
    """
    version = getattr(instance, '_v', None)
    if version is not None:
        data['_v'] = version


def is_model_serializer(field: serializers.BaseSerializer) -> bool:
    try:
        return isinstance(field.child, serializers.ModelSerializer)
    except AttributeError:
        return isinstance(field, serializers.ModelSerializer)
