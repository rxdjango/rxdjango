class RxField:
    def __class_getitem__(cls, type_):
        def factory(initial):
            return cls(type_, initial)
        return factory

    def __init__(self, type_, initial):
        self.type = type_
        self.value = initial

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return self.value

    def __set__(self, obj, value):
        self.value = value


rx = RxField
