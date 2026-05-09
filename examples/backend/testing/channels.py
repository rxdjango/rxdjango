from rxdjango import ContextChannel, rx, action


class TestingChannel(ContextChannel):

    int_with_default = rx[int](1)
    int_optional = rx[int | None]()

    str_with_default = rx[str]('hello')
    str_optional = rx[str | None]()

    @action
    async def do_action(self, count: int, label: str):
        pass

    async def inert(self):
        pass
