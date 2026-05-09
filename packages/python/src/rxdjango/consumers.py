from __future__ import annotations

from channels.generic.websocket import AsyncWebsocketConsumer
from .actions import execute_action
from .exceptions import InvalidMessageReceived


class ContextConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:

        super().__init__(*args, **kwargs)

        self.channel = None

    async def connect(self) -> None:
        """Setup the ContextChannel and connection."""
        await self.accept()

        # Intantiate a ContextChannel with received url parameters
        self.channel = self.context_channel_class()
        self.channel._consumer = self

        kwargs = self.scope['url_route']['kwargs']
        await self.channel.on_connect(**kwargs)

        await self.send_ready()

    async def send_ready(self):
        await self.send({
            't': 'ready',
            'protocol': '0.0.0',
        })

    async def receive(self, text_data: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.disconnect()
            raise

        try:
            typ = data['t']
        except KeyError:
            raise InvalidMessageReceived(f'Missing "t" key: {text_data}')

        match typ:
            case 'ac':
                self.receive_action(data)
            case _:
                raise InvalidMessageReceived(f'Type "{typ}" not valid')

    async def disconnect(self, close_code: int | None = None) -> None:
        """Handle WebSocket disconnection."""
        await self.channel.on_disconnect()

    async def relay(self, payload: dict[str, Any]) -> None:
        """Relay a state update payload to the connected client.

        Called by the channel layer when the WebsocketRouter dispatches updates.
        """
        payload = payload['payload']
        await self.send(text_data=json_dumps(payload))

    async def receive_action(self, action: dict[str, Any]) -> None:
        """Execute an @action decorated method via RPC from the frontend.

        Sends back the result or error with the same id.
        """
        call_id = action.get('id')
        method_name = action.get('a')
        params = action.get('p')

        if call_id is None or method_name is None or params is None:
            if call_id is not None:
                response = {
                    't': 'ac',
                    'id': call_id,
                    'e': [400, 'Invalid action message: requires c (callId), a (action), and p (params) fields'],
                }
                await self.send(text_data=json.dumps(response))
            return

        if not isinstance(params, list):
            response = {
                't': 'ac',
                'id': call_id,
                'e': [400, 'p (params) must be an array'],
            }
            await self.send(text_data=json.dumps(response))
            return

        try:
            result = await execute_action(self.channel, method_name, params)
            response = {'t': 'ac', 'id': call_id, 'r': result, 'e': 0}
            await self.send(text_data=json.dumps(response))
        except Exception as e:
            await self.send({
                't': 'ac',
                'id': call_id,
                'e': [
                    getattr(e, 'code', 500),
                    str(e) or type(e).__name__,
                ],
            })
            raise
