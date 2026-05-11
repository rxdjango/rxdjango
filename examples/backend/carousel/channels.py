from rxdjango import ContextChannel, rx, action


class CarouselChannel(ContextChannel):

    FRUITS = ['banana', 'apple', 'orange']

    selected = rx[int](0)
    fruit = rx[str](FRUITS[selected])
    first_letter = rx[str](fruit[0])

    @action
    async def increment(self):
        self.selected = (self.selected + 1) % len(self.FRUITS)
        self.fruit = self.FRUITS[self.selected]
        self.first_letter = self.fruit[0]
