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

    @action
    async def check_optionals_act_as_primitives_when_set(self):
        self.str_optional = 'new string'
        self.int_optional = 3
        self.str_with_default = self.str_optional[
            self.int_with_default:self.int_optional
        ]
