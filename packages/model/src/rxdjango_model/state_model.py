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
        data = dict(self.flat_serializer(instance).data)
        data['_type'] = self.instance_type
        return data

    def serialize_delete(self, instance: Model) -> dict[str, Any]:
        return {
            '_type': self.instance_type,
            '_del': instance.pk,
        }

    def serialize_state(self, instance: Any) -> Generator[list[dict[str, Any]], None, None]:
        """Yield each layer of the nested instance as a flat list of dicts.

        Each yielded layer is a list of one or more flat instances of the
        same ``_type``. Callers usually concatenate the layers into a single
        list for transport.
        """
        if self.many:
            queryset = instance.all() if hasattr(instance, 'all') else instance
            instances = list(queryset)
            data = [dict(self.flat_serializer(item).data) for item in instances]
        else:
            instances = [instance]
            data = [dict(self.flat_serializer(instance).data)]

        for serialized in data:
            serialized['_type'] = self.instance_type

        yield data

        for field_name, peer_model in self.children.items():
            for inst in instances:
                try:
                    peer_instance = getattr(inst, field_name)
                except AttributeError:
                    continue
                if peer_instance is None:
                    continue
                for serialized in peer_model.serialize_state(peer_instance):
                    yield serialized

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


def is_model_serializer(field: serializers.BaseSerializer) -> bool:
    try:
        return isinstance(field.child, serializers.ModelSerializer)
    except AttributeError:
        return isinstance(field, serializers.ModelSerializer)
