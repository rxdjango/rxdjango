from __future__ import annotations

import json
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer

from .actions import execute_action
from .exceptions import InvalidMessageReceived


PROTOCOL_VERSION = '0.1.0'


class ContextConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.channel = None
        self._pending_rx: list[dict[str, Any]] = []

    async def connect(self) -> None:
        await self.accept()

        self.channel = self.context_channel_class()
        self.channel._consumer = self

        kwargs = self.scope['url_route']['kwargs']
        await self.channel.on_connect(**kwargs)

        await self.send_ready()

    async def send_ready(self) -> None:
        await self.send(text_data=json.dumps({
            't': 'ready',
            'protocol': PROTOCOL_VERSION,
        }))

    def enqueue_rx(self, field: str, value: Any) -> None:
        self._pending_rx.append({'t': 'rx', 'f': field, 'v': value})

    async def _flush_rx(self) -> None:
        while self._pending_rx:
            msg = self._pending_rx.pop(0)
            await self.send(text_data=json.dumps(msg))

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if text_data is None:
            return
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
                await self.receive_action(data)
            case _:
                raise InvalidMessageReceived(f'Type "{typ}" not valid')

    async def disconnect(self, close_code: int | None = None) -> None:
        if self.channel is not None:
            await self.channel.on_disconnect()

    async def receive_action(self, action: dict[str, Any]) -> None:
        call_id = action.get('id')
        method_name = action.get('a')
        params = action.get('p')

        if call_id is None or method_name is None or params is None:
            if call_id is not None:
                await self.send(text_data=json.dumps({
                    't': 'ac',
                    'id': call_id,
                    'e': [400, 'Invalid action message: requires id, a, and p fields'],
                }))
            return

        if not isinstance(params, list):
            await self.send(text_data=json.dumps({
                't': 'ac',
                'id': call_id,
                'e': [400, 'p (params) must be an array'],
            }))
            return

        try:
            result = await execute_action(self.channel, method_name, params)
        except Exception as e:
            await self.send(text_data=json.dumps({
                't': 'ac',
                'id': call_id,
                'e': [getattr(e, 'code', 500), str(e) or type(e).__name__],
            }))
            raise

        await self.send(text_data=json.dumps({
            't': 'ac',
            'id': call_id,
            'r': result,
            'e': 0,
        }))
        await self._flush_rx()
