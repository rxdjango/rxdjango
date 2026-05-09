from rxdjango import ContextChannel, rx, action


class CounterChannel(ContextChannel):

    counter = rx[int](0)

    @action
    async def increment(self):
        self.counter += 1
