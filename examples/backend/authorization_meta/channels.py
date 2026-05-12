from rxdjango import ContextChannel, rx, action


class AuthorizationMetaChannel(ContextChannel):

    authorized = rx[bool](False)
    counter = rx[int](0)

    class Meta:
        action_requires = 'authorized'

    @action(anonymous=True)
    async def authorize(self, password: str):
        if password == 'password':
            self.authorized = True
            return True
        return False

    @action
    async def increment(self):
        self.counter += 1
