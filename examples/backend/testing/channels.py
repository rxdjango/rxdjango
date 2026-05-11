from rxdjango import ContextChannel, rx, action, memo


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


class MemoTrackingChannel(ContextChannel):

    field_a = rx[int](0)
    field_b = rx[int](0)

    count_a = rx[int](0)
    count_b = rx[int](0)

    @action
    async def increment_a(self):
        self.field_a = self.field_a + 1

    @action
    async def increment_b(self):
        self.field_b = self.field_b + 1

    @memo('field_a')
    def double_a(self):
        self.count_a = self.count_a + 1
        return self.field_a * 2

    @memo('field_b')
    def double_b(self):
        self.count_b = self.count_b + 1
        return self.field_b * 2
