_UNSET = object()


class RxField:
    def __class_getitem__(cls, type_):
        def factory(initial=_UNSET):
            return cls(type_, initial)
        return factory

    def __init__(self, type_, initial=_UNSET):
        self.type = type_
        self.has_default = initial is not _UNSET
        self.default = None if initial is _UNSET else initial

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            return obj.__dict__[self.name]
        except KeyError:
            return self.default

    def __set__(self, obj, value):
        obj.__dict__[self.name] = value
        consumer = getattr(obj, '_consumer', None)
        if consumer is not None:
            consumer.enqueue_rx(self.name, value)


rx = RxField
