"""Router declarations for live (routed) list delivery (ADR-0018).

A `many=True` `rx.model` field's `routing=` argument accepts a **Router**:
one reviewable contract with two methods forming the delivery dimension --

* `publish(instance)` -- the group values a saved row announces to (write
  side);
* `subscribe(channel)` -- the group values a connection listens on (bind
  side).

Both methods return an iterable of opaque values (tuples are fine -- only
the column-string sugar is single-column); `None` is filtered from
whichever side returns it by the framework, never by the Router itself
(list-routing: "`None` is never a group value").

`columns` names the row attributes `publish()` reads, so the write path
(`rxdjango_model.reactive_model.ReactiveModel.save`) knows which columns
justify a narrow pre-image read on update (design D2). Leaving it `None`
(the default) means "can't tell without the full row": every update of a
model registering such a Router pays a full-row pre-image.

`key` identifies the dimension for dedup across fields/channels declaring
it (design D1): the same dimension declared twice collapses to one group
set. The default is the Router class's dotted path, so two instances of the
same custom Router class are treated as the same dimension; override `key`
for a class that legitimately carries more than one.
"""
from __future__ import annotations

from typing import Any, Iterable

from django.core.exceptions import FieldDoesNotExist


class Router:
    """Base class for a `many=True` field's live-delivery dimension."""

    columns: tuple[str, ...] | None = None

    @property
    def key(self) -> str:
        return f'{type(self).__module__}.{type(self).__qualname__}'

    def publish(self, instance: Any) -> Iterable[Any]:
        raise NotImplementedError('Router subclasses must implement publish()')

    def subscribe(self, channel: Any) -> Iterable[Any]:
        raise NotImplementedError('Router subclasses must implement subscribe()')


class ColumnRouter(Router):
    """Sugar for `routing='column_name'`.

    A row announces to its own column value (`publish`); a connection
    subscribes to the value(s) its own bound queryset filters that column to
    -- "connections subscribe to the values their bind resolves"
    (list-routing spec) -- read via `exact`/`in` conditions on the queryset
    assigned to the field this Router is declared on. Field binding happens
    once, mechanically, from `RxModelField.__set_name__`; it is not part of
    the public Router contract.

    `column` may name either a ForeignKey's field (`'project'`) or its
    `_id` attname (`'project_id'`) -- `bind_model` (called once from
    `RxModelField.contribute_to_channel`, mirroring `bind_field`) resolves
    whichever spelling was declared to the model field's canonical attname
    through `model._meta`, so dimension/group identity (`key`, `columns`)
    and `publish`'s attribute read never depend on which spelling a
    particular declaration used, and `subscribe`'s queryset matching
    recognizes a bound queryset's condition regardless of which spelling
    *it* was written with (`.filter(project=obj)`, `.filter(project_id=5)`,
    and `.filter(project__id=5)` all resolve to the same underlying column
    at the Django query-compiler level). A `column` that names neither a
    field nor a column of the bound model is a loud declaration-time error.
    """

    def __init__(self, column: str) -> None:
        self.column = column
        self.columns = (column,)
        self._field_name: str | None = None
        self._model: type | None = None
        self._attname: str | None = None
        self._model_field_name: str | None = None

    def bind_field(self, field_name: str) -> None:
        if self._field_name is None:
            self._field_name = field_name

    def bind_model(self, model: type) -> None:
        if self._model is not None:
            return
        try:
            field = model._meta.get_field(self.column)
        except FieldDoesNotExist:
            field = None
        if field is None or not hasattr(field, 'attname'):
            raise TypeError(
                f"routing={self.column!r} does not name a field or column "
                f"of {model.__name__!r}"
            )
        self._model = model
        self._attname = field.attname
        self._model_field_name = field.name
        self.columns = (field.attname,)

    @property
    def key(self) -> str:
        return self._attname or self.column

    def publish(self, instance: Any) -> Iterable[Any]:
        attr = self._attname or self.column
        return [getattr(instance, attr, None)]

    def subscribe(self, channel: Any) -> Iterable[Any]:
        if self._field_name is None:
            return []
        queryset = getattr(channel, self._field_name, None)
        return _column_equality_values(queryset, self._match_names())

    def _match_names(self) -> frozenset[str]:
        names = {self.column}
        if self._attname:
            names.add(self._attname)
        if self._model_field_name:
            names.add(self._model_field_name)
        return frozenset(names)

    def __repr__(self) -> str:
        return f'ColumnRouter({self.column!r})'


_BROADCAST_VALUE = '*'


class BroadcastRouter(Router):
    """The explicit firehose (ADR-0018 Option F): every row announces to,
    and every connection listens on, the same constant dimension value.
    Deliberately the loudest, most greppable declaration -- there is no
    middle ground between a declared dimension and `routing=BroadcastRouter()`.
    """

    key = 'rxdjango_model.routing.BroadcastRouter'

    def publish(self, instance: Any) -> Iterable[Any]:
        return [_BROADCAST_VALUE]

    def subscribe(self, channel: Any) -> Iterable[Any]:
        return [_BROADCAST_VALUE]

    def __repr__(self) -> str:
        return 'BroadcastRouter()'


def _column_equality_values(queryset: Any, names: Iterable[str]) -> list[Any]:
    """Best-effort extraction of the `exact`/`in` values a queryset filters
    one of `names` (a column's every known spelling -- declared string,
    resolved attname, resolved field name) to. Not a validator
    (query_introspection owns bind validation, unchanged per design D7) --
    conditions this can't make sense of are silently skipped rather than
    raised, since this only shapes which dimension groups a connection
    joins, not correctness."""
    query = getattr(queryset, 'query', None)
    if query is None:
        return []
    names = frozenset(names)
    values: list[Any] = []
    _collect_column_values(query.where, names, values)
    return values


def _collect_column_values(node: Any, names: frozenset[str], values: list[Any]) -> None:
    children = getattr(node, 'children', None)
    if not children:
        return
    for child in children:
        if getattr(child, 'children', None) is not None:
            _collect_column_values(child, names, values)
            continue
        lhs = getattr(child, 'lhs', None)
        target = getattr(lhs, 'target', None)
        if target is None:
            continue
        target_names = {getattr(target, 'name', None), getattr(target, 'attname', None)}
        if not (target_names & names):
            continue
        lookup_name = getattr(child, 'lookup_name', None)
        if lookup_name == 'exact':
            values.append(child.rhs)
        elif lookup_name == 'in':
            values.extend(child.rhs)
