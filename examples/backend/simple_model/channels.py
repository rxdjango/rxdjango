from rxdjango import ContextChannel, rx, action
from .models import User
from .serializers import UserSerializer


class SimpleModelChannel(ContextChannel):

    user = rx.model(UserSerializer())

    @action
    async def authorize(self, password: str):
        if password == 'password':
            self.user = await User.objects.aget(id=1)
            return True
        return False
