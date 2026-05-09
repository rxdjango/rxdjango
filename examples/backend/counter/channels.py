from rxdjango import ContextChannel, rx, action


class RuntimeChannel(ContextChannel):

    counter = rx[int](0)

    @action
    async def increment(self):
        self.counter += 1
