"""Consumer group management across rebind, end to end (task 1.3).

A `many=True` reactive field's consumer joins per-instance broadcast groups
for the rows it relays, exactly as a single-instance field does (ADR-0016).
On rebind, rows only in the *old* snapshot must be left so a row demoted
from the list stops producing frames -- design D4 (ADR-0019): the server
holds no membership state, only group membership that tracks the most
recently drained walk.

Drives the real `StateModel` / `RxModelField` / `ReactiveModel` /
`reactive_registry` pipeline against a real (in-memory) channel layer, but
below the full ASGI/WebsocketCommunicator dispatch loop: that loop keeps a
background task listening on the channel layer for the consumer's lifetime,
which -- with a real channel layer configured -- outlives `disconnect()`
often enough to leak into later, unmarked tests' database-access guard.
Asserting on the channel layer's own group/channel bookkeeping exercises the
exact mechanism production delivery depends on, without that instability.
"""
from __future__ import annotations

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import override_settings

from rxdjango import ContextChannel, rx
from rxdjango.consumers import ContextConsumer

from testapp.models import Task
from testapp.serializers import TaskSerializer

pytestmark = pytest.mark.django_db(transaction=True)

# Scoped to this module only (see module docstring): most of the core/model
# unit suites run with no CHANNEL_LAYERS configured, and Channels' per-message
# `aclose_old_connections()` needs DB access the moment a channel layer
# exists, tripping pytest-django's guard on tests not marked `django_db`.
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}


class TasksChannel(ContextChannel):
    tasks = rx.model(TaskSerializer(many=True))


def _drain(consumer):
    async_to_sync(consumer._flush_rx)()


def _bind(channel, consumer, ids):
    channel.tasks = Task.objects.filter(id__in=ids).order_by('id')
    _drain(consumer)


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_rebind_leaves_the_broadcast_group_of_a_dropped_row():
    t1 = Task.objects.create(name='Task 1')
    t2 = Task.objects.create(name='Task 2')
    t3 = Task.objects.create(name='Task 3')

    channel_layer = get_channel_layer()
    consumer = ContextConsumer()
    consumer.channel_layer = channel_layer
    consumer.channel_name = 'test-channel'

    async def fake_send(text_data=None, **kwargs):
        pass
    consumer.send = fake_send

    channel = TasksChannel()
    channel._consumer = consumer

    group = 'rx.testapp.serializers.TaskSerializer.{}'.format
    _bind(channel, consumer, [t1.id, t2.id, t3.id])
    assert group(t1.id) in channel_layer.groups
    assert group(t2.id) in channel_layer.groups
    assert group(t3.id) in channel_layer.groups

    # Rebind: t2 drops out of the new snapshot.
    _bind(channel, consumer, [t1.id, t3.id])
    assert group(t1.id) in channel_layer.groups
    assert group(t2.id) not in channel_layer.groups
    assert group(t3.id) in channel_layer.groups

    # Saving the dropped row queues nothing for this consumer's channel: the
    # channel layer itself has nobody left in that group to deliver to.
    t2.name = 'renamed-2'
    t2.save()
    assert 'test-channel' not in channel_layer.channels

    # A still-bound row keeps producing broadcasts.
    t1.name = 'renamed-1'
    t1.save()
    assert 'test-channel' in channel_layer.channels
