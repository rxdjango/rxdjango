from .consumers import ContextConsumer
from .memo import MemoField
from .rx import RxField


class ContextChannelMeta(type):
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)

        if new_class.__module__ == cls.__module__:
            return new_class

        meta = attrs.get("Meta")
        if meta:
            meta.abstract = getattr(meta, 'abstract', False)
            if meta.abstract:
                return new_class
            new_class._action_requires = getattr(meta, 'action_requires', None)
        else:
            new_class._action_requires = getattr(new_class, '_action_requires', None)

        new_class._rx_fields = {
            key: value
            for key, value in attrs.items()
            if isinstance(value, RxField)
        }

        new_class._memo_order = _topological_memo_order(new_class)
        _initialize_memo_defaults(new_class)

        return new_class


def _topological_memo_order(channel_cls):
    """Return memo field names in dependency order, validating that every
    declared dependency exists on the channel."""
    fields = channel_cls._rx_fields
    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, source: str | None = None):
        if name in visited:
            return
        if name in visiting:
            raise TypeError(
                f"@memo '{source or name}' has a circular dependency through '{name}'"
            )
        f = fields.get(name)
        if f is None:
            raise TypeError(
                f"@memo '{source}' depends on unknown field '{name}'"
            )
        if not isinstance(f, MemoField):
            visited.add(name)
            return
        visiting.add(name)
        for dep in f.deps:
            visit(dep, source=name)
        visiting.discard(name)
        visited.add(name)
        order.append(name)

    for name, f in fields.items():
        if isinstance(f, MemoField):
            visit(name)

    return order


def _initialize_memo_defaults(channel_cls):
    """Compute each memo's initial value using rx defaults, and infer its
    type. Subsequent memos see prior memos via the in-progress instance."""
    if not channel_cls._memo_order:
        return
    inst = channel_cls.__new__(channel_cls)
    for name in channel_cls._memo_order:
        f = channel_cls._rx_fields[name]
        value = f.func(inst)
        f.default = value
        f.has_default = True
        f.type = type(value) if value is not None else type(None)
        inst.__dict__[name] = value


class ContextChannel(metaclass=ContextChannelMeta):

    class Meta:
        abstract = True

    @classmethod
    def as_asgi(cls):
        Consumer = type(
            f'{cls.__name__}Consumer',
            (ContextConsumer,),
            dict(
                context_channel_class=cls,
            ),
        )

        return Consumer.as_asgi()

    def __init__(self) -> None:
        self._consumer = None

    async def on_connect(self, **kwargs) -> None:
        pass

    async def on_disconnect(self) -> None:
        pass
