"""ContextConsumer wire protocol, tested in-process via WebsocketCommunicator."""
import asyncio

import pytest
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.urls import re_path

from rxdjango import ContextChannel, action, rx
from rxdjango.consumers import PROTOCOL_VERSION


class EchoChannel(ContextChannel):
    counter = rx[int](0)
    label = rx[str]('')

    async def on_connect(self, **kwargs):
        self.kwargs = kwargs

    @action
    async def ping(self):
        return 'pong'

    @action
    async def bump(self, by: int):
        self.counter = self.counter + by
        self.label = f'bumped {by}'
        return self.counter

    @action
    async def route_kwargs(self):
        return self.kwargs


def make_communicator(path='/ws/echo/'):
    app = URLRouter([
        re_path(r'^ws/echo/$', EchoChannel.as_asgi()),
        re_path(r'^ws/room/(?P<room>\w+)/$', EchoChannel.as_asgi()),
    ])
    return WebsocketCommunicator(app, path)


async def connect(path='/ws/echo/'):
    comm = make_communicator(path)
    connected, _ = await comm.connect()
    assert connected
    ready = await comm.receive_json_from(timeout=1)
    return comm, ready


async def test_ready_frame_sent_on_connect():
    comm, ready = await connect()
    assert ready == {'t': 'ready', 'protocol': PROTOCOL_VERSION}
    await comm.disconnect()


async def test_action_round_trip():
    comm, _ = await connect()
    await comm.send_json_to({'t': 'ac', 'id': '1', 'a': 'ping', 'p': []})
    assert await comm.receive_json_from(timeout=1) == {
        't': 'ac', 'id': '1', 'r': 'pong', 'e': 0,
    }
    await comm.disconnect()


async def test_rx_frames_flushed_after_action_in_order():
    comm, _ = await connect()
    await comm.send_json_to({'t': 'ac', 'id': '1', 'a': 'bump', 'p': [3]})
    assert await comm.receive_json_from(timeout=1) == {
        't': 'ac', 'id': '1', 'r': 3, 'e': 0,
    }
    assert await comm.receive_json_from(timeout=1) == {
        't': 'rx', 'f': 'counter', 'v': 3,
    }
    assert await comm.receive_json_from(timeout=1) == {
        't': 'rx', 'f': 'label', 'v': 'bumped 3',
    }
    await comm.disconnect()


async def test_url_kwargs_reach_on_connect():
    comm, _ = await connect('/ws/room/lobby/')
    await comm.send_json_to({'t': 'ac', 'id': '1', 'a': 'route_kwargs', 'p': []})
    response = await comm.receive_json_from(timeout=1)
    assert response['r'] == {'room': 'lobby'}
    await comm.disconnect()


async def test_action_message_without_params_is_rejected():
    comm, _ = await connect()
    await comm.send_json_to({'t': 'ac', 'id': '9', 'a': 'ping'})
    response = await comm.receive_json_from(timeout=1)
    assert response['id'] == '9'
    assert response['e'][0] == 400
    await comm.disconnect()


async def test_action_params_must_be_a_list():
    comm, _ = await connect()
    await comm.send_json_to({'t': 'ac', 'id': '9', 'a': 'ping', 'p': {}})
    response = await comm.receive_json_from(timeout=1)
    assert response['e'][0] == 400
    await comm.disconnect()


async def test_unknown_action_is_forbidden():
    comm, _ = await connect()
    await comm.send_json_to({'t': 'ac', 'id': '9', 'a': 'missing', 'p': []})
    response = await comm.receive_json_from(timeout=1)
    assert response['e'][0] == 403
    await comm.disconnect()


async def test_flush_drains_messages_enqueued_mid_send():
    from rxdjango.consumers import ContextConsumer
    import json

    consumer = ContextConsumer()
    sent = []

    async def fake_send(text_data=None, **kwargs):
        sent.append(json.loads(text_data))
        if len(sent) == 1:
            consumer.enqueue_rx('late', 99)

    consumer.send = fake_send
    consumer.enqueue_rx('a', 1)
    consumer.enqueue_rx('b', 2)
    await consumer._flush_rx()

    assert [msg['f'] for msg in sent] == ['a', 'b', 'late']
    assert consumer._pending_rx == []
