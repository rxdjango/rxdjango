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

    def __class_getitem__(cls, t):
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
    if t is None or t is _NoneType:
        return 'None'
    return getattr(t, '__name__', repr(t))


def _fmt_allowed(allowed):
    return ', '.join('None' if a is _NoneType else a.__name__ for a in allowed)


rx = RxField
