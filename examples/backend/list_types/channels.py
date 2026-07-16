from rxdjango import ContextChannel, rx, action


class ListTypesChannel(ContextChannel):
    """Union element types and an optional list (ADR-0017).

    `mixed` shows `list[int | str]` rendering both element types in one
    array. `optional_numbers` shows the value tier of the field-level
    None-union: `null` (not set) is distinct from `[]` (set, but empty).
    """

    mixed = rx[list[int | str]]([1, 'two', 3])
    optional_numbers = rx[list[int] | None]()

    @action
    async def add_number(self, value: int):
        self.mixed.append(value)

    @action
    async def add_text(self, value: str):
        self.mixed.append(value)

    @action
    async def clear_mixed(self):
        self.mixed.clear()

    @action
    async def set_numbers(self, values: list[int]):
        self.optional_numbers = values

    @action
    async def append_number(self, value: int):
        self.optional_numbers.append(value)

    @action
    async def clear_numbers(self):
        self.optional_numbers = []

    @action
    async def unset_numbers(self):
        self.optional_numbers = None
