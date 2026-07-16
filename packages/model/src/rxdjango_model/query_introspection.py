"""Bind-time introspection of a `many=True` field's queryset (ADR-0019 D3).

At assignment (design D2's "bind"), the framework walks the queryset's
compiled `Query` -- `query.where` and `query.order_by` -- to extract the
conjunction of simple conditions and the ordering spec that the client will
later evaluate itself. This is deliberately narrow: an AND-tree of simple
lookups on the anchor serializer's own output fields, using one of the
supported lookups, with JSON-serializable values; ordering columns must be
serializer fields too. Anything else -- OR/NOT structure, a joined (`__`)
column path, an unsupported lookup, a non-serialized column, a value that
doesn't survive JSON round-tripping -- fails loudly here, naming the
offending condition, rather than silently under- or over-delivering later.

Datetime (and date/time) values are rendered through the *same* DRF field
instance the flat serializer uses, so the client compares the identical
ISO-8601 string representation Django emits for live rows (design D3's
lookup-parity contract).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Any

from django.db.models.expressions import Col
from django.db.models.sql.where import NothingNode, WhereNode

if TYPE_CHECKING:  # pragma: no cover
    from .state_model import StateModel


SUPPORTED_LOOKUPS = frozenset({'exact', 'in', 'gt', 'gte', 'lt', 'lte', 'isnull'})


class UnsupportedQuerysetError(TypeError):
    """A `many=True` field's queryset cannot be introspected into a bind
    descriptor: an unsupported condition/ordering shape, named in the
    message (ADR-0019 D3)."""


@dataclass(frozen=True)
class BindDescriptor:
    where: tuple[tuple[str, str, Any], ...] = ()
    order_by: tuple[str, ...] = dataclass_field(default_factory=tuple)

    def to_wire(self) -> dict[str, Any]:
        """Wire shape per `wire-protocol`'s `q` slot: `{"w": [...], "s": [...]}`."""
        return {
            'w': [list(condition) for condition in self.where],
            's': list(self.order_by),
        }


def introspect_queryset(queryset: Any, state_model: 'StateModel') -> BindDescriptor:
    """Build the bind descriptor for a queryset assigned to a list field.

    Raises `UnsupportedQuerysetError` (or `TypeError` if the value isn't a
    real Django queryset) synchronously, before any layer is queried --
    "fails loudly at bind, naming the condition."
    """
    query = getattr(queryset, 'query', None)
    if query is None:
        raise TypeError(
            "rx.model many=True field requires a Django queryset; "
            f"got {type(queryset).__name__}"
        )

    where = tuple(_walk_where(query.where, query, state_model))
    order_by = tuple(_walk_order_by(query, state_model))
    return BindDescriptor(where=where, order_by=order_by)


def _walk_where(node, query, state_model) -> list[tuple[str, str, Any]]:
    if node is None or not node.children:
        return []
    if node.connector != 'AND':
        raise UnsupportedQuerysetError(
            f"queryset condition uses {node.connector}; only an AND-conjunction "
            "of simple conditions is supported for a static list (ADR-0019)"
        )
    if node.negated:
        raise UnsupportedQuerysetError(
            "queryset condition uses NOT (e.g. .exclude()), which is not "
            "supported for a static list (ADR-0019)"
        )

    conditions: list[tuple[str, str, Any]] = []
    for child in node.children:
        if isinstance(child, WhereNode):
            conditions.extend(_walk_where(child, query, state_model))
        elif isinstance(child, NothingNode):
            # `.none()`'s marker node: the anchor is empty regardless (`v:
            # []`), so it contributes no condition of its own.
            continue
        else:
            conditions.append(_condition_from_lookup(child, query, state_model))
    return conditions


def _condition_from_lookup(lookup, query, state_model) -> tuple[str, str, Any]:
    lookup_name = getattr(lookup, 'lookup_name', None)
    if lookup_name not in SUPPORTED_LOOKUPS:
        raise UnsupportedQuerysetError(
            f"unsupported lookup {lookup_name!r}; supported lookups are "
            f"{sorted(SUPPORTED_LOOKUPS)} (ADR-0019)"
        )

    lhs = lookup.lhs
    if not isinstance(lhs, Col):
        raise UnsupportedQuerysetError(
            f"queryset condition {lookup_name!r} is not a plain column "
            "reference (ADR-0019 supports simple lookups only)"
        )

    base_alias = query.get_initial_alias()
    if lhs.alias is not None and lhs.alias != base_alias:
        raise UnsupportedQuerysetError(
            f"queryset condition on {_joined_path(query, lhs)!r} traverses a "
            "relation (joined column); only conditions on the anchor "
            "serializer's own fields are supported for a queryset list "
            "(ADR-0019)"
        )

    column = lhs.target.name
    ts_field = _serializer_field_for(state_model, column)
    if ts_field is None:
        raise UnsupportedQuerysetError(
            f"queryset filters on {column!r}, which is not a field of the "
            "anchor serializer's output (ADR-0019)"
        )

    value = _serialize_value(ts_field, lookup_name, lookup.rhs, column)
    return (column, lookup_name, value)


def _joined_path(query, col) -> str:
    # Rebuild the developer's `a__b__c` spelling from the join chain, so the
    # bind error names the condition as it was written, not its far-side
    # column.
    parts = [col.target.name]
    alias = col.alias
    base_alias = query.get_initial_alias()
    while alias and alias != base_alias:
        join = query.alias_map.get(alias)
        join_field = getattr(join, 'join_field', None)
        if join_field is None:
            break
        parts.insert(0, join_field.name)
        alias = getattr(join, 'parent_alias', None)
    return '__'.join(parts)


def _walk_order_by(query, state_model) -> list[str]:
    entries = query.order_by or tuple(state_model.model._meta.ordering)
    result: list[str] = []
    pk_name = state_model.model._meta.pk.name
    for entry in entries:
        if not isinstance(entry, str):
            raise UnsupportedQuerysetError(
                f"ordering entry {entry!r} is not a plain field reference "
                "(ADR-0019 supports serializer-field ordering only)"
            )
        descending = entry.startswith('-')
        column = entry[1:] if descending else entry
        if '__' in column:
            raise UnsupportedQuerysetError(
                f"ordering column {column!r} traverses a relation; only "
                "serializer-local fields are supported for ordering (ADR-0019)"
            )
        if column == 'pk':
            column = pk_name
        if _serializer_field_for(state_model, column) is None:
            raise UnsupportedQuerysetError(
                f"ordering column {column!r} is not a field of the anchor "
                "serializer's output (ADR-0019)"
            )
        result.append(f'-{column}' if descending else column)
    return result


def _serializer_field_for(state_model, column: str):
    return state_model._flat_instance.fields.get(column)


def _serialize_value(ts_field, lookup_name: str, raw_value: Any, column: str) -> Any:
    if lookup_name == 'isnull':
        if not isinstance(raw_value, bool):
            raise UnsupportedQuerysetError(
                f"isnull condition on {column!r} must have a boolean value"
            )
        return raw_value
    if lookup_name == 'in':
        try:
            items = list(raw_value)
        except TypeError:
            raise UnsupportedQuerysetError(
                f"in condition on {column!r} must have an iterable value"
            ) from None
        return [_serialize_scalar(ts_field, item, column) for item in items]
    return _serialize_scalar(ts_field, raw_value, column)


def _serialize_scalar(ts_field, value: Any, column: str) -> Any:
    # Related-field lookups (FK exact/in/isnull) are already prepared to raw
    # pks by Django's query construction (verified empirically: `.filter(fk=
    # instance)` and `.filter(fk=5)` both yield an int `.rhs`), so a related
    # field's own `to_representation` -- which expects a model instance, not
    # a pk -- must not run; the raw value already *is* the wire value.
    from rest_framework import relations
    if isinstance(ts_field, relations.RelatedField):
        rendered = value
    else:
        try:
            rendered = ts_field.to_representation(value)
        except Exception as exc:
            raise UnsupportedQuerysetError(
                f"condition value {value!r} on {column!r} could not be "
                f"serialized: {exc}"
            ) from exc

    if not _is_json_safe(rendered):
        raise UnsupportedQuerysetError(
            f"condition value {rendered!r} on {column!r} is not "
            "JSON-serializable (ADR-0019)"
        )
    return rendered


def _is_json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True
