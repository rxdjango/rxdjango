from rxdjango import ContextChannel, rx, action, memo


class CarouselMemoChannel(ContextChannel):

    FRUITS = ['banana', 'apple', 'orange']

    selected = rx[int](0)

    @action
    async def rotate(self):
        self.selected = (self.selected + 1) % len(self.FRUITS)

    @memo('selected')
    def fruit(self):
        return self.FRUITS[self.selected]

    @memo('fruit')
    def first_letter(self):
        return self.fruit[0]
