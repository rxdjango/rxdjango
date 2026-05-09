from rxdjango import ContextChannel, rx


class TestingChannel(ContextChannel):

    int_with_default = rx[int](1)
    int_optional = rx[int | None]()

    str_with_default = rx[str]('hello')
    str_optional = rx[str | None]()
