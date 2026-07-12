from __future__ import annotations

from collections import defaultdict
from typing import Any, Generator, Iterator

from rest_framework import serializers
from django.db.models import Model
from django.db.models.fields import related_descriptors


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
    ) -> None:
        self.nested_serializer = state_serializer
        self.many = many
        self.origin = origin
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

    def serialize_state(
        self, instance: Any
    ) -> Generator[tuple['StateModel', list[dict[str, Any]]], None, None]:
        """Yield ``(node, layer)`` pairs for the nested instance.

        Each ``layer`` is a flat list of instances of one ``_type``; ``node``
        is the ``StateModel`` that produced it, so a caller can tell a reactive
        layer from a plain one without re-inspecting the payload. Callers
        usually concatenate the layers into a single list for transport.
        """
        if self.many:
            queryset = instance.all() if hasattr(instance, 'all') else instance
            instances = list(queryset)
        else:
            instances = [instance]

        data = [dict(self._flat_instance.to_representation(item)) for item in instances]

        for serialized, inst in zip(data, instances):
            serialized['_type'] = self.instance_type
            _attach_version(serialized, inst)

        yield self, data

        for field_name, peer_model in self.children.items():
            for inst in instances:
                try:
                    peer_instance = getattr(inst, field_name)
                except AttributeError:
                    continue
                if peer_instance is None:
                    continue
                yield from peer_model.serialize_state(peer_instance)

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
            return StateModel(serializer.child, many=True, origin=self)

        if isinstance(descriptor, related_descriptors.ReverseManyToOneDescriptor):
            return StateModel(serializer.child, many=True, origin=self)

        if isinstance(descriptor, related_descriptors.ForwardManyToOneDescriptor):
            return StateModel(serializer, many=False, origin=self)

        if isinstance(descriptor, related_descriptors.ReverseOneToOneDescriptor):
            return StateModel(serializer, many=False, origin=self)

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
