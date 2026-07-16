from rxdjango import ContextChannel, rx, action


class ScalarListChannel(ContextChannel):
    """CRUD over a plain `rx[list[str]]` field (ADR-0017).

    Every action below is a single Python list mutator; the descriptor
    intercepts it and pushes the corresponding delta operation to the
    client — no full-list re-send, however many items are in the list.
    """

    items = rx[list[str]](['apple', 'banana', 'cherry'])

    @action
    async def append(self, value: str):
        self.items.append(value)

    @action
    async def insert(self, index: int, value: str):
        self.items.insert(index, value)

    @action
    async def set_at(self, index: int, value: str):
        self.items[index] = value

    @action
    async def remove_at(self, index: int):
        del self.items[index]

    @action
    async def pop(self):
        return self.items.pop()

    @action
    async def replace_all(self):
        self.items = ['reset', 'from', 'scratch']
