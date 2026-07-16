from __future__ import annotations

import json
from collections import deque
from typing import Any

from channels.generic.websocket import AsyncWebsocketConsumer

from .actions import execute_action
from .exceptions import ForbiddenError, InvalidMessageReceived


PROTOCOL_VERSION = '0.2.0'

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
        self._pending_rx: deque[dict[str, Any]] = deque()
        # Sync-deposit/async-drain seam for rx.model fields (ADR-0016 D6):
        # RxModelField.__set__ is a sync descriptor and cannot await the
        # layered walk, so it deposits the field's not-yet-started walk here,
        # keyed by field name. Reassigning the field before drain replaces
        # the entry, superseding the prior walk for free — an undrained async
        # generator's body never runs. `_flush_rx` drains these first.
        self._pending_model_walks: dict[str, Any] = {}
        # Fields cleared (assigned `None`) before their prior walk drained
        # (design D4/ADR-0019): no walk runs for these, so the group leave
        # they imply is recorded here and applied at the next drain instead
        # of computed from a walk's yielded groups.
        self._pending_clears: set[str] = set()
        # Reactive group bookkeeping. A consumer joins the broadcast group of
        # every reactive instance it relays, so committed row changes are
        # pushed back to it; see rxdjango_model.reactive_registry. Model-field
        # groups are joined per layer while draining a walk, immediately
        # before that layer's frame is sent (see `_drain_model_walks`).
        self._joined_groups: set[str] = set()
        # field -> groups relayed by that field's most recently drained walk
        # (design D4, ADR-0019). A (re)bind's fresh walk recomputes this set
        # from scratch; groups only the *previous* walk relayed are left, so
        # a row demoted from a list (or a superseded single-instance field)
        # stops producing frames instead of leaking a joined group forever.
        self._field_groups: dict[str, set[str]] = {}

    async def connect(self) -> None:
        await self.accept()

        self.channel = self.context_channel_class()
        self.channel._consumer = self

        kwargs = self.scope['url_route']['kwargs']
        await self.channel.on_connect(**kwargs)

        await self.send_ready()
        # Relay any state assigned during on_connect (e.g. `self.task = ...`).
        await self._flush_rx()

    async def send_ready(self) -> None:
        await self.send(text_data=json.dumps({
            't': 'ready',
            'protocol': PROTOCOL_VERSION,
        }))

    def enqueue_rx(self, field: str, value: Any, op: str | None = None) -> None:
        """Queue a plain rx update (or a model field's ``v: null`` clear) for
        the client. Model-field layer frames go through
        ``deposit_model_walk`` instead, since those carry per-layer group
        joins that must happen before each frame, not in a batch.

        ``op`` (ADR-0017), when given, is one of ``"i"``/``"s"``/``"d"`` — a
        list delta operation riding the frame's ``o`` slot, with ``value`` as
        the operation's operand (``[index, value]`` for insert/set, a bare
        index for delete). Omitting it (the default) sends a plain
        whole-value frame, exactly as before.
        """
        msg: dict[str, Any] = {'t': 'rx', 'f': field, 'v': value}
        if op is not None:
            msg['o'] = op
        self._pending_rx.append(msg)

    def deposit_model_walk(self, field: str, walk: Any) -> None:
        """Deposit (or clear, via ``walk=None``) a field's pending layered
        walk, keyed by field name (ADR-0016 D6).

        Called synchronously from ``RxModelField.__set__``. Passing ``None``
        drops any undrained walk for the field, so a clear or a reassignment
        supersedes it — no frames from a superseded walk are ever sent. A
        clear also marks the field for a full group leave at the next drain
        (design D4); a fresh walk cancels that mark — its own drain will
        recompute the field's group set from scratch.
        """
        if walk is None:
            self._pending_model_walks.pop(field, None)
            self._pending_clears.add(field)
        else:
            self._pending_model_walks[field] = walk
            self._pending_clears.discard(field)

    async def _join_groups(self, groups: list[str] | None) -> None:
        if self.channel_layer is None or not groups:
            return
        for group in groups:
            if group not in self._joined_groups:
                await self.channel_layer.group_add(group, self.channel_name)
                self._joined_groups.add(group)

    async def _drain_model_walks(self) -> None:
        """Drain every pending model-field walk to completion, one field at a
        time, sending each layer's frame immediately after joining that
        layer's broadcast groups (join-before-snapshot, preserved per layer).

        Popping a field's walk before iterating it means a walk deposited for
        a field already mid-drain (impossible today — a consumer processes
        one message at a time — but harmless either way) would simply start a
        fresh drain rather than racing this one.

        After a walk (or a clear) finishes, ``_leave_stale_groups`` reconciles
        the field's group set against what it held before (design D4,
        ADR-0019): a (re)bind is authoritative, so rows only the *previous*
        walk relayed are left, closing the group off from further broadcasts.
        """
        while self._pending_clears:
            field = self._pending_clears.pop()
            await self._leave_stale_groups(field, frozenset())
        while self._pending_model_walks:
            field = next(iter(self._pending_model_walks))
            walk = self._pending_model_walks.pop(field)
            walk_groups: set[str] = set()
            async for value, groups in walk:
                await self._join_groups(groups)
                walk_groups.update(groups)
                await self.send(text_data=json.dumps({'t': 'rx', 'f': field, 'v': value}))
            await self._leave_stale_groups(field, walk_groups)

    async def _leave_stale_groups(self, field: str, new_groups) -> None:
        """Reconcile ``field``'s joined groups against its just-drained walk.

        Groups the field held before but that this walk did not relay are
        left, unless another field's live group set still needs them (a
        group name is derived from the instance, not the field, so two
        fields can legitimately share one).
        """
        old_groups = self._field_groups.get(field, set())
        if new_groups:
            self._field_groups[field] = set(new_groups)
        else:
            self._field_groups.pop(field, None)

        stale = old_groups - new_groups
        if not stale or self.channel_layer is None:
            return
        still_needed: set[str] = set()
        for other_field, groups in self._field_groups.items():
            if other_field != field:
                still_needed.update(groups)
        for group in stale:
            if group in still_needed:
                continue
            if group in self._joined_groups:
                await self.channel_layer.group_discard(group, self.channel_name)
                self._joined_groups.discard(group)

    async def _flush_rx(self) -> None:
        # Model-field layers first, each preceded by its own group joins
        # (ADR-0016 D6); then plain rx values and model-field `v: null`
        # clears, which need no group handling.
        await self._drain_model_walks()
        # The loop condition re-checks the deque, so messages enqueued while
        # a send was awaited are drained too.
        while self._pending_rx:
            msg = self._pending_rx.popleft()
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
        # Built at channel-class creation by RxModelField.contribute_to_channel.
        field_types = getattr(type(self.channel), '_model_field_types', {})
        field = field_types.get(instance_type)
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
            # With no id the error frame carries `id: null` — uncorrelatable
            # by design, but a misbehaving client is diagnosable rather than
            # silently ignored.
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
