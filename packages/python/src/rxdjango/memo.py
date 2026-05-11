"""Memoized reactive field.

`@memo('dep1', 'dep2', ...)` decorates a method on a `ContextChannel` and
turns it into a read-only reactive property. The value is computed from the
listed dependencies (other rx fields or memos on the same channel); it is
re-evaluated when any dependency changes value, and only then.

When a memo's recomputed value differs from its cached one, the consumer
emits an `rx` message for the memo, exactly as it would for a plain rx
field. From the frontend's perspective a memo is indistinguishable from a
regular rx field.
"""
from .rx import RxField


class MemoField(RxField):
    """Descriptor produced by `@memo(*deps)`.

    Reads return the cached value (populated at channel-class creation time
    for the initial state, and at runtime whenever a dependency changes).
    Direct assignment is forbidden — memo values are derived.
    """

    has_default = True

    def __init__(self, deps, func):
        self.deps = tuple(deps)
        self.func = func
        self.name = ''
        self.type = None
        self.default = None
        self.allowed = ()

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj, value):
        raise AttributeError(
            f"memo field '{self.name}' is read-only; it is recomputed from its dependencies"
        )


def memo(*deps):
    """Mark a method as a memoized reactive property.

    Usage::

        @memo('selected')
        def fruit(self):
            return self.FRUITS[self.selected]
    """
    if not deps:
        raise TypeError('@memo() requires at least one dependency name')
    for d in deps:
        if not isinstance(d, str):
            raise TypeError(
                f'@memo() dependencies must be field-name strings, got {type(d).__name__}'
            )
        if callable(d):
            raise TypeError(
                '@memo must be called with dependency names: @memo("dep")(method)'
            )

    def decorator(func):
        if not callable(func):
            raise TypeError('@memo decorates a method')
        return MemoField(deps, func)
    return decorator


def recompute_memos(obj, changed):
    """Walk `obj._memo_order` once, recomputing each memo whose deps are in
    `changed`. Updates cached value, mutates `changed` to include memos that
    changed, and enqueues `rx` messages on the bound consumer."""
    consumer = getattr(obj, '_consumer', None)
    for name in obj._memo_order:
        f = obj._rx_fields[name]
        if not any(d in changed for d in f.deps):
            continue
        new_val = f.func(obj)
        old_val = obj.__dict__.get(name, f.default)
        if new_val == old_val:
            continue
        obj.__dict__[name] = new_val
        changed.add(name)
        if consumer is not None:
            consumer.enqueue_rx(name, new_val)
