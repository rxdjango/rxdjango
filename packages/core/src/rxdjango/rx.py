"""Reactive field descriptor.

`rx[T](default)` produces an `RxField` descriptor whose *instance* is itself a
subclass of `T` carrying `default` as its value. That lets class-body
expressions like `FRUITS[selected]` or `fruit[0]` evaluate naturally, while
`__get__`/`__set__` still route reads/writes through the instance dict and
notify the channel consumer.

Supported runtime types: `int`, `str`, `float`, `bool`, plus `None`. Unions
containing `None` make the field optional. A default is always required
*unless* `None` is in the union (in which case the implicit default is None).

Note on `bool`: instances of `rx[bool](True)` are *not* the `True` singleton —
`selected is True` will be False. Use equality (`selected == True`) instead.

`rx[list[S]](default)` (ADR-0017) declares a reactive list of scalar elements.
Each connection gets its own `ReactiveList` — a `list` subclass bound to
`(channel_instance, field_name)` — whose mutating methods are intercepted by
explicit enumeration (not `__getattribute__` magic): each validates any
introduced element, applies the mutation locally, then enqueues the
corresponding delta operation on the `o` slot (or a whole-value replace for
bulk mutators). Reassignment (`self.items = [...]`) always enqueues a
whole-value replace, exactly like scalar fields.
"""
import types as _types
import typing as _typing


_UNSET = object()
_NoneType = type(None)
_SUPPORTED = (int, str, float, bool)
# bool is in _SUPPORTED for type-checking but is excluded here because
# CPython forbids subclassing it (see ADR-0008).
_SUBCLASSABLE = (int, str, float)


class RxField:
    """Marker base class for reactive descriptors. Instances of subclasses are
    collected by `ContextChannelMeta` via `isinstance(value, RxField)`."""

    type = None
    default = None
    has_default = False
    allowed: tuple = ()
    name: str = ''

    def contribute_to_channel(self, channel_cls, field_name):
        """Hook called by ``ContextChannelMeta`` once the channel class is
        built. Subclasses override this to perform compile-time setup that
        depends on the channel class context (e.g. building a ``StateModel``
        from a serializer)."""
        return None

    def __class_getitem__(cls, t):
        list_spec = _parse_list_spec(t)
        if list_spec is not None:
            elem_type, field_optional = list_spec
            return _list_field_factory(t, elem_type, field_optional)

        allowed = _resolve_allowed(t)
        for a in allowed:
            if a is not _NoneType and a not in _SUPPORTED:
                raise TypeError(
                    f'rx[{_fmt_type(t)}]: only int, str, float, bool, '
                    f'and None are supported'
                )

        def factory(initial=_UNSET):
            if initial is _UNSET:
                if _NoneType not in allowed:
                    raise TypeError(
                        f'rx[{_fmt_type(t)}] requires an explicit default; '
                        f'declare it as rx[{_fmt_type(t)} | None] for an optional field'
                    )
                return _PlainRxField(t, allowed, default=None, has_default=False)
            if initial is None:
                if _NoneType not in allowed:
                    raise TypeError(
                        f'rx[{_fmt_type(t)}] default cannot be None; '
                        f'declare it as rx[{_fmt_type(t)} | None] to allow None'
                    )
                return _PlainRxField(t, allowed, default=None, has_default=True)
            if not isinstance(initial, allowed):
                raise TypeError(
                    f'rx[{_fmt_type(t)}] default {initial!r} ({type(initial).__name__}) '
                    f'is not one of allowed types: {_fmt_allowed(allowed)}'
                )
            base = type(initial)
            if base not in _SUBCLASSABLE:
                # bool falls here: cannot be subclassed, so skip the
                # "descriptor is a T" trick (ADR-0008).
                return _PlainRxField(t, allowed, default=initial, has_default=True)
            typed_cls = _make_typed_field(base)
            inst = typed_cls.__new__(typed_cls, initial)
            inst._bind(t, allowed, initial)
            return inst

        return factory


class _PlainRxField(RxField):
    """Descriptor with no value-type affordances. Used when the runtime default
    is None — class-body arithmetic on None wouldn't be meaningful anyway."""

    def __init__(self, t, allowed, default, has_default):
        self.type = t
        self.allowed = allowed
        self.default = default
        self.has_default = has_default

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj, value):
        _validate(value, self.allowed, self.name)
        old = obj.__dict__.get(self.name, self.default)
        obj.__dict__[self.name] = value
        consumer = getattr(obj, '_consumer', None)
        if consumer is not None:
            consumer.enqueue_rx(self.name, value)
        if old != value:
            _propagate_to_memos(obj, self.name)

    def __bool__(self):
        return bool(self.default)

    def __repr__(self):
        return f'rx[{_fmt_type(self.type)}]({self.default!r})'


def _parse_list_spec(t):
    """Return `(elem_type, field_optional)` if `t` denotes a list declaration
    (`list[S]` or `list[S] | None`), else `None` (not a list declaration at
    all, so the caller falls through to the scalar path).

    Raises `TypeError` for shapes that *are* list-shaped but unsupported: a
    bare, unsubscripted `list`, or a field union mixing `list[...]` with
    anything other than `None`.
    """
    origin = _typing.get_origin(t)
    if origin is list:
        args = _typing.get_args(t)
        if not args:
            raise TypeError(
                'rx[list] requires an element type; declare it as '
                'rx[list[T]] for a scalar element type T'
            )
        return args[0], False
    if t is list:
        raise TypeError(
            'rx[list] requires an element type; declare it as '
            'rx[list[T]] for a scalar element type T'
        )
    if origin is _typing.Union or origin is _types.UnionType:
        args = _typing.get_args(t)
        if list in args:
            raise TypeError(
                'rx[list] requires an element type; declare it as '
                'rx[list[T]] for a scalar element type T'
            )
        list_args = [a for a in args if _typing.get_origin(a) is list]
        if not list_args:
            return None
        if len(list_args) > 1:
            raise TypeError(
                f'rx[{_fmt_type(t)}]: a list field union may only combine '
                f'one list[...] member with None'
            )
        others = [a for a in args if a is not list_args[0]]
        if any(a is not _NoneType and a is not None for a in others):
            raise TypeError(
                f'rx[{_fmt_type(t)}]: a list field union may only combine '
                f'list[...] with None'
            )
        field_optional = any(a is _NoneType or a is None for a in others)
        elem_args = _typing.get_args(list_args[0])
        if not elem_args:
            raise TypeError(
                'rx[list] requires an element type; declare it as '
                'rx[list[T]] for a scalar element type T'
            )
        return elem_args[0], field_optional
    return None


def _resolve_list_elem_allowed(elem_type):
    """Resolve and validate the scalar-union allowed tuple for a list's
    element type. Nested containers (another `list[...]`, `dict`, ...) raise
    loudly — element immutability is what keeps every list change an op
    (ADR-0017)."""
    allowed = _resolve_allowed(elem_type)
    for a in allowed:
        if a is not _NoneType and a not in _SUPPORTED:
            raise TypeError(
                f'rx[list[{_fmt_type(elem_type)}]]: list elements must be '
                f'scalar types (int, str, float, bool, optionally None); '
                f'{_fmt_type(a)} is not supported. Nested containers are '
                f'refused: element immutability is what keeps every list '
                f'change an op (ADR-0017).'
            )
    return allowed


def _list_field_factory(t, elem_type, field_optional):
    elem_allowed = _resolve_list_elem_allowed(elem_type)
    elem_label = _fmt_type(elem_type)

    def factory(initial=_UNSET):
        if initial is _UNSET:
            if not field_optional:
                raise TypeError(
                    f'rx[list[{elem_label}]] requires an explicit default; '
                    f'declare it as rx[list[{elem_label}] | None] for an '
                    f'optional field'
                )
            return _PlainListRxField(
                t, elem_type, elem_allowed, field_optional,
                default=None, has_default=False,
            )
        if initial is None:
            if not field_optional:
                raise TypeError(
                    f'rx[list[{elem_label}]] default cannot be None; '
                    f'declare it as rx[list[{elem_label}] | None] to allow '
                    f'None'
                )
            return _PlainListRxField(
                t, elem_type, elem_allowed, field_optional,
                default=None, has_default=True,
            )
        if not isinstance(initial, list):
            raise TypeError(
                f'rx[list[{elem_label}]] default {initial!r} '
                f'({type(initial).__name__}) is not a list'
            )
        for item in initial:
            _validate(item, elem_allowed, 'default')
        typed_cls = _make_typed_list_field()
        inst = typed_cls(list(initial))
        inst._bind(t, elem_type, elem_allowed, field_optional, list(initial))
        return inst

    return factory


class ReactiveList(list):
    """Per-connection reactive list bound to a channel instance and field
    name (ADR-0017 D1). Mutating methods are intercepted by explicit
    enumeration: each validates any introduced element, applies the mutation
    to the underlying `list` storage, then enqueues the corresponding delta
    operation (or a whole-value replace for bulk mutators), per design D2.

    Index normalization happens here, before emission: negative indices
    resolve against the pre-mutation length, and `insert` clamps exactly like
    Python's own `list.insert` does. The wire only ever carries canonical,
    non-negative indices.
    """

    def _bind(self, owner, field_name, elem_allowed):
        self._owner = owner
        self._field_name = field_name
        self._elem_allowed = elem_allowed
        return self

    def _consumer(self):
        return getattr(self._owner, '_consumer', None)

    def _validate_elem(self, value):
        _validate(value, self._elem_allowed, self._field_name)

    def _emit_op(self, op, operand):
        consumer = self._consumer()
        if consumer is not None:
            consumer.enqueue_rx(self._field_name, operand, op=op)

    def _emit_replace(self):
        consumer = self._consumer()
        if consumer is not None:
            consumer.enqueue_rx(self._field_name, list(self))

    def _normalize_index(self, index):
        n = len(self)
        if index < 0:
            index += n
        return index

    def _clamp_insert_index(self, index):
        n = len(self)
        if index < 0:
            index = max(n + index, 0)
        return min(index, n)

    # -- Positional single-element ops (design D2) --------------------

    def append(self, value):
        self._validate_elem(value)
        index = len(self)
        list.append(self, value)
        self._emit_op('i', [index, value])

    def insert(self, index, value):
        self._validate_elem(value)
        norm = self._clamp_insert_index(index)
        list.insert(self, index, value)
        self._emit_op('i', [norm, value])

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            list.__setitem__(self, index, value)
            self._emit_replace()
            return
        self._validate_elem(value)
        norm = self._normalize_index(index)
        list.__setitem__(self, index, value)
        self._emit_op('s', [norm, value])

    def __delitem__(self, index):
        if isinstance(index, slice):
            list.__delitem__(self, index)
            self._emit_replace()
            return
        norm = self._normalize_index(index)
        list.__delitem__(self, index)
        self._emit_op('d', norm)

    def remove(self, value):
        index = list.index(self, value)
        list.remove(self, value)
        self._emit_op('d', index)

    def pop(self, index=-1):
        norm = self._normalize_index(index)
        value = list.pop(self, index)
        self._emit_op('d', norm)
        return value

    def extend(self, values):
        values = list(values)
        for v in values:
            self._validate_elem(v)
        start = len(self)
        list.extend(self, values)
        for offset, v in enumerate(values):
            self._emit_op('i', [start + offset, v])

    def __iadd__(self, values):
        self.extend(values)
        return self

    # -- Bulk mutators: whole-value replace (design D2) ----------------

    def clear(self):
        list.clear(self)
        self._emit_replace()

    def sort(self, *args, **kwargs):
        list.sort(self, *args, **kwargs)
        self._emit_replace()

    def reverse(self):
        list.reverse(self)
        self._emit_replace()

    def __imul__(self, n):
        list.__imul__(self, n)
        self._emit_replace()
        return self


def _init_bound_value(obj, name, elem_allowed, default):
    if default is None:
        return None
    return ReactiveList(list(default))._bind(obj, name, elem_allowed)


def _assign_list(obj, name, elem_allowed, value, field_optional):
    # `self.items += [...]` and `self.items *= n` desugar to
    # `self.items = self.items.__iadd__(/__imul__)(...)`: Python's augmented
    # assignment always re-invokes `__set__` with whatever `__iadd__`/
    # `__imul__` returned. Both already mutated the bound ReactiveList in
    # place and enqueued their op(s)/replace (design D2), so `__set__` seeing
    # the *same* object back is a no-op store, not a fresh reassignment —
    # re-validating and re-emitting here would double-send.
    if value is obj.__dict__.get(name, _UNSET):
        return value
    consumer = getattr(obj, '_consumer', None)
    if value is None:
        if not field_optional:
            raise TypeError(
                f"rx field '{name}': cannot assign None to a non-optional "
                f"list field"
            )
        if consumer is not None:
            consumer.enqueue_rx(name, None)
        return None
    if not isinstance(value, list):
        raise TypeError(
            f"rx field '{name}': cannot assign value of type "
            f"{type(value).__name__} (expected list)"
        )
    for item in value:
        _validate(item, elem_allowed, name)
    bound = ReactiveList(list(value))._bind(obj, name, elem_allowed)
    if consumer is not None:
        consumer.enqueue_rx(name, list(bound))
    return bound


class _PlainListRxField(RxField):
    """List-field descriptor used when the field's default is `None` (an
    optional list field with no concrete default yet). Mirrors
    `_PlainRxField`: no "descriptor is a list" affordance, since `None`
    cannot be a list."""

    def __init__(self, t, elem_type, elem_allowed, field_optional, default, has_default):
        self.type = t
        self.elem_type = elem_type
        self.elem_allowed = elem_allowed
        self.field_optional = field_optional
        self.allowed = (list, _NoneType)
        self.default = default
        self.has_default = has_default

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.name not in obj.__dict__:
            obj.__dict__[self.name] = _init_bound_value(
                obj, self.name, self.elem_allowed, self.default,
            )
        return obj.__dict__[self.name]

    def __set__(self, obj, value):
        old = obj.__dict__.get(self.name, self.default)
        new = _assign_list(
            obj, self.name, self.elem_allowed, value, self.field_optional,
        )
        obj.__dict__[self.name] = new
        if old != new:
            _propagate_to_memos(obj, self.name)

    def __bool__(self):
        return bool(self.default)

    def __repr__(self):
        return f'rx[list[{_fmt_type(self.elem_type)}] | None]({self.default!r})'


_typed_list_field_cache = None


def _make_typed_list_field():
    global _typed_list_field_cache
    if _typed_list_field_cache is not None:
        return _typed_list_field_cache

    class _TypedListRxField(list, RxField):
        # Descriptor-is-a-T trick (ADR-0004/ADR-0017 D1): the class-body
        # value is itself a real list carrying the default, so it behaves
        # naturally wherever a plain list would (len(), iteration, ...).

        def _bind(self, t, elem_type, elem_allowed, field_optional, initial):
            self.type = t
            self.elem_type = elem_type
            self.elem_allowed = elem_allowed
            self.field_optional = field_optional
            self.allowed = (list, _NoneType) if field_optional else (list,)
            self.default = initial
            self.has_default = True

        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            if self.name not in obj.__dict__:
                obj.__dict__[self.name] = _init_bound_value(
                    obj, self.name, self.elem_allowed, self.default,
                )
            return obj.__dict__[self.name]

        def __set__(self, obj, value):
            old = obj.__dict__.get(self.name, self.default)
            new = _assign_list(
                obj, self.name, self.elem_allowed, value, self.field_optional,
            )
            obj.__dict__[self.name] = new
            if old != new:
                _propagate_to_memos(obj, self.name)

        def __repr__(self):
            return f'rx[list[{_fmt_type(self.elem_type)}]]({list(self)!r})'

    _TypedListRxField.__name__ = 'rx[list]'
    _TypedListRxField.__qualname__ = _TypedListRxField.__name__
    _typed_list_field_cache = _TypedListRxField
    return _TypedListRxField


def _propagate_to_memos(obj, changed_name):
    memo_order = getattr(type(obj), '_memo_order', None)
    if not memo_order:
        return
    from .memo import recompute_memos
    recompute_memos(obj, {changed_name})


_typed_field_cache: dict = {}


def _make_typed_field(base):
    cached = _typed_field_cache.get(base)
    if cached is not None:
        return cached

    class _TypedRxField(base, RxField):
        # Inherits operator/method semantics from `base` so class-body
        # expressions like FRUITS[selected] or fruit[0] work transparently.

        def _bind(self, t, allowed, initial):
            self.type = t
            self.allowed = allowed
            self.default = initial
            self.has_default = True

        def __set_name__(self, owner, name):
            self.name = name

        def __get__(self, obj, objtype=None):
            if obj is None:
                return self
            return obj.__dict__.get(self.name, self.default)

        def __set__(self, obj, value):
            _validate(value, self.allowed, self.name)
            old = obj.__dict__.get(self.name, self.default)
            obj.__dict__[self.name] = value
            consumer = getattr(obj, '_consumer', None)
            if consumer is not None:
                consumer.enqueue_rx(self.name, value)
            if old != value:
                _propagate_to_memos(obj, self.name)

    _TypedRxField.__name__ = f'rx[{base.__name__}]'
    _TypedRxField.__qualname__ = _TypedRxField.__name__
    _typed_field_cache[base] = _TypedRxField
    return _TypedRxField


def _validate(value, allowed, name):
    if not isinstance(value, allowed):
        raise TypeError(
            f"rx field '{name}': cannot assign value of type "
            f"{type(value).__name__} (allowed: {_fmt_allowed(allowed)})"
        )


def _resolve_allowed(t):
    origin = _typing.get_origin(t)
    if origin is _typing.Union or origin is _types.UnionType:
        out = []
        for a in _typing.get_args(t):
            if a is None:
                a = _NoneType
            out.append(a)
        return tuple(out)
    if t is None:
        return (_NoneType,)
    return (t,)


def _fmt_type(t):
    origin = _typing.get_origin(t)
    if origin is _typing.Union or origin is _types.UnionType:
        return ' | '.join(_fmt_type(a) for a in _typing.get_args(t))
    if origin is list:
        args = _typing.get_args(t)
        inner = _fmt_type(args[0]) if args else ''
        return f'list[{inner}]'
    if t is list:
        return 'list'
    if t is None or t is _NoneType:
        return 'None'
    return getattr(t, '__name__', repr(t))


def _fmt_allowed(allowed):
    return ', '.join('None' if a is _NoneType else a.__name__ for a in allowed)


rx = RxField
