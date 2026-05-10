from .consumers import ContextConsumer
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

        new_class._rx_fields = {
            key: value
            for key, value in attrs.items()
            if isinstance(value, RxField)
        }

        return new_class


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
