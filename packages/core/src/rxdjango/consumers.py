from __future__ import annotations

import json
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer

from .actions import execute_action
from .exceptions import ForbiddenError, InvalidMessageReceived


PROTOCOL_VERSION = '0.1.0'

# Reactive broadcast group prefix. Kept in sync with
# rxdjango_model.reactive_registry.GROUP_PREFIX; core declares its own copy so
# it carries no dependency on the model package.
_GROUP_PREFIX = 'rx.'


def _group_name(instance_type: str, instance_id: Any) -> str:
    return f'{_GROUP_PREFIX}{instance_type}.{instance_id}'


class ContextConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.channel = None
        self._pending_rx: list[dict[str, Any]] = []
        # Reactive group bookkeeping. A consumer joins the broadcast group of
        # every reactive instance it relays, so committed row changes are
        # pushed back to it; see rxdjango_model.reactive_registry.
        self._pending_group_add: set[str] = set()
        self._pending_group_discard: set[str] = set()
        self._joined_groups: set[str] = set()
        # instance_type -> rx.model field name, used to route group broadcasts
        # back to the right field on the client.
        self._model_field_types: dict[str, str] = {}

    async def connect(self) -> None:
        await self.accept()

        self.channel = self.context_channel_class()
        self.channel._consumer = self
        self._build_model_field_index()

        kwargs = self.scope['url_route']['kwargs']
        await self.channel.on_connect(**kwargs)

        await self.send_ready()
        # Relay any state assigned during on_connect (e.g. `self.task = ...`).
        await self._flush_rx()

    def _build_model_field_index(self) -> None:
        """Map every reachable serializer ``instance_type`` to its field name.

        A group broadcast is tagged with the changed instance's ``_type`` only;
        this index lets the consumer name the rx.model field whose nested state
        the layer belongs to.
        """
        rx_fields = getattr(type(self.channel), '_rx_fields', {})
        for field_name, rx_field in rx_fields.items():
            state_model = getattr(rx_field, 'state_model', None)
            if state_model is None:
                continue
            for instance_type in getattr(state_model, 'index', {}):
                self._model_field_types[instance_type] = field_name

    async def send_ready(self) -> None:
        await self.send(text_data=json.dumps({
            't': 'ready',
            'protocol': PROTOCOL_VERSION,
        }))

    def enqueue_rx(self, field: str, value: Any) -> None:
        self._pending_rx.append({'t': 'rx', 'f': field, 'v': value})
        self._scan_groups(value)

    def _scan_groups(self, value: Any) -> None:
        """Record group joins/leaves implied by a relayed rx.model payload.

        Every reactive flat layer (one carrying ``_v``) means a subscription to
        that instance's broadcast group; a ``_del`` layer means leaving it.
        """
        if not isinstance(value, list):
            return
        for item in value:
            if not isinstance(item, dict):
                continue
            instance_type = item.get('_type')
            if instance_type is None:
                continue
            if '_del' in item:
                self._pending_group_discard.add(
                    _group_name(instance_type, item['_del'])
                )
            elif '_v' in item and 'id' in item:
                self._pending_group_add.add(
                    _group_name(instance_type, item['id'])
                )

    async def _apply_group_changes(self) -> None:
        if self.channel_layer is None:
            self._pending_group_add.clear()
            self._pending_group_discard.clear()
            return
        while self._pending_group_add:
            group = self._pending_group_add.pop()
            if group not in self._joined_groups:
                await self.channel_layer.group_add(group, self.channel_name)
                self._joined_groups.add(group)
        while self._pending_group_discard:
            group = self._pending_group_discard.pop()
            if group in self._joined_groups:
                await self.channel_layer.group_discard(group, self.channel_name)
                self._joined_groups.discard(group)

    async def _flush_rx(self) -> None:
        # Join broadcast groups before sending the snapshot so a row change
        # committed during flush is delivered rather than dropped.
        await self._apply_group_changes()
        while self._pending_rx:
            msg = self._pending_rx.pop(0)
            await self.send(text_data=json.dumps(msg))

    async def send_model_layer(self, field: str, layer: dict[str, Any]) -> None:
        """Send a single flat model layer to the client immediately.

        Bypasses the pending queue so callers can place a layer on the wire at
        a precise point — used to relay an event ahead of a slower DB fetch.
        """
        await self.send(text_data=json.dumps({
            't': 'rx', 'f': field, 'v': [layer],
        }))

    async def rx_broadcast(self, message: dict[str, Any]) -> None:
        """Channel-layer handler for a reactive row change.

        Routes the changed flat layer to the rx.model field it belongs to; the
        client ``StateBuilder`` reconciles it against what it already holds by
        comparing ``_v``.
        """
        payload = message['payload']
        instance_type = payload.get('_type')
        field = self._model_field_types.get(instance_type)
        if field is None:
            return
        if '_del' in payload and self.channel_layer is not None:
            group = _group_name(instance_type, payload['_del'])
            if group in self._joined_groups:
                await self.channel_layer.group_discard(group, self.channel_name)
                self._joined_groups.discard(group)
        await self.send_model_layer(field, payload)

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
        if self.channel_layer is not None:
            while self._joined_groups:
                group = self._joined_groups.pop()
                await self.channel_layer.group_discard(group, self.channel_name)
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
        except ForbiddenError as e:
            await self.send(text_data=json.dumps({
                't': 'ac',
                'id': call_id,
                'e': [403, str(e) or 'Forbidden'],
            }))
            return
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
