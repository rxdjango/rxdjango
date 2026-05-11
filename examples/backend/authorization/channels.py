from rxdjango import ContextChannel, rx, action


class AuthorizationChannel(ContextChannel):

    authorized: bool = False
    counter = rx[int](0)

    @action
    async def authorize(self, password: str):
        if password == 'password':
            self.authorized = True
            return True
        return False

    @action(requires='authorized')
    async def increment(self):
        self.counter += 1
