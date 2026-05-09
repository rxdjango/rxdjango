from .consumers import ContextConsumer


class ContextChannelMeta(type):
    def __new__(cls, name, bases, attrs):
        """Create and return a new class instance."""

        # Create the new class as usual.
        new_class = super().__new__(cls, name, bases, attrs)

        if new_class.__module__ == cls.__module__:
            return new_class

        # If this is an abstract class, no functionality to bind
        meta = attrs.get("Meta")
        if meta:
            meta.abstract = getattr(meta, 'abstract', False)
            if meta.abstract:
                return new_class

        new_class._rx_fields = {}

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
        self._consumer = None  # will be set by consumer
