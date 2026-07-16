"""Consumer bind and relay for routed (live) fields (routed-list-delivery
tasks 3.1-3.4).

Drives a real (in-memory) channel layer directly against a bare
`ContextConsumer`, the same style `test_list_rebind_integration.py` and
`test_bind_descriptor_protocol.py` use -- below the full ASGI dispatch loop,
which would otherwise leak a background listener into later tests' DB-access
guard (see those modules' docstrings). Dimension-group delivery is exercised
by manually draining a channel-layer message and invoking the consumer's
handler with it, exactly what the ASGI dispatch loop would do.
"""
from __future__ import annotations

import json

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import override_settings

from rxdjango import ContextChannel, rx
from rxdjango.consumers import ContextConsumer

from testapp.models import Task
from testapp.serializers import TaskSerializer

pytestmark = pytest.mark.django_db(transaction=True)

CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}


class RoutedTasksChannel(ContextChannel):
    tasks = rx.model(TaskSerializer(many=True), routing='status')


def _make_consumer(channel_layer, channel_name):
    consumer = ContextConsumer()
    consumer.channel_layer = channel_layer
    consumer.channel_name = channel_name
    sent: list[dict] = []

    async def fake_send(text_data=None, **kwargs):
        sent.append(json.loads(text_data))
    consumer.send = fake_send

    channel = RoutedTasksChannel()
    channel._consumer = consumer
    consumer.channel = channel
    return channel, consumer, sent


def _bind(channel, consumer, status):
    channel.tasks = Task.objects.filter(status=status).order_by('id')
    async_to_sync(consumer._flush_rx)()


def _dimension_group(value):
    from rxdjango_model.routing_registry import route_group_name
    return route_group_name(Task._meta.label_lower, 'status', value)


async def _pump(channel_layer, consumer):
    """Receive and dispatch every pending channel-layer message addressed
    to `consumer`'s channel, exactly as the ASGI loop would."""
    delivered = []
    while consumer.channel_name in channel_layer.channels:
        message = await channel_layer.receive(consumer.channel_name)
        handler_name = message['type'].replace('.', '_')
        await getattr(consumer, handler_name)(message)
        delivered.append(message)
    return delivered


# -- 3.1: bind joins dimension groups; two-connection isolation ------------


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_bind_of_routed_field_joins_its_dimension_group():
    channel_layer = get_channel_layer()
    channel, consumer, _sent = _make_consumer(channel_layer, 'conn-a')

    _bind(channel, consumer, 'open')

    assert _dimension_group('open') in channel_layer.groups
    assert 'conn-a' in channel_layer.groups[_dimension_group('open')]


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_two_connections_on_different_dimension_values_stay_isolated():
    channel_layer = get_channel_layer()
    channel_a, consumer_a, sent_a = _make_consumer(channel_layer, 'conn-a')
    channel_b, consumer_b, sent_b = _make_consumer(channel_layer, 'conn-b')

    _bind(channel_a, consumer_a, 'open')
    _bind(channel_b, consumer_b, 'closed')

    Task.objects.create(name='New', status='open', priority=1)

    async_to_sync(_pump)(channel_layer, consumer_a)
    async_to_sync(_pump)(channel_layer, consumer_b)

    # Only the connection subscribed to 'open' relays the creation.
    creation_frames_a = [m for m in sent_a if m.get('v') and m['v'][0].get('name') == 'New']
    creation_frames_b = [m for m in sent_b if m.get('v') and m['v'][0].get('name') == 'New']
    assert len(creation_frames_a) == 1
    assert creation_frames_b == []


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_rebind_leaves_the_stale_dimension_group():
    channel_layer = get_channel_layer()
    channel, consumer, _sent = _make_consumer(channel_layer, 'conn-a')

    _bind(channel, consumer, 'open')
    assert 'conn-a' in channel_layer.groups.get(_dimension_group('open'), {})

    _bind(channel, consumer, 'closed')
    assert 'conn-a' not in channel_layer.groups.get(_dimension_group('open'), {})
    assert 'conn-a' in channel_layer.groups.get(_dimension_group('closed'), {})


# -- 3.2: relay + duplicate-delivery convergence ---------------------------


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_dimension_event_relays_as_a_tagged_merge_frame():
    channel_layer = get_channel_layer()
    channel, consumer, sent = _make_consumer(channel_layer, 'conn-a')
    _bind(channel, consumer, 'open')

    Task.objects.create(name='New', status='open', priority=1)
    async_to_sync(_pump)(channel_layer, consumer)

    relayed = [m for m in sent if m.get('v') and m['v'][0].get('name') == 'New']
    assert len(relayed) == 1
    assert relayed[0]['f'] == 'tasks'
    assert 'q' not in relayed[0]


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_duplicate_delivery_through_per_instance_and_dimension_group():
    """A row the connection already holds via its per-instance group (from
    the snapshot) is *also* reachable through the dimension group once
    updated -- both deliveries happen server-side; the client's `_v`
    watermark is what converges them (design D4)."""
    channel_layer = get_channel_layer()
    channel, consumer, sent = _make_consumer(channel_layer, 'conn-a')

    task = Task.objects.create(name='Held', status='open', priority=1)
    _bind(channel, consumer, 'open')
    sent.clear()

    task.name = 'renamed'
    task.save()
    async_to_sync(_pump)(channel_layer, consumer)

    renamed_frames = [m for m in sent if m.get('v') and m['v'][0].get('name') == 'renamed']
    # One via the per-instance group (rx_broadcast), one via the dimension
    # group (rx_route) -- both relayed, nothing deduped server-side.
    assert len(renamed_frames) == 2


# -- 3.3: creation-drop optimization ----------------------------------------


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_creation_failing_residual_is_dropped():
    channel_layer = get_channel_layer()
    channel, consumer, sent = _make_consumer(channel_layer, 'conn-a')
    _bind(channel, consumer, 'open')

    # Same dimension group ('open'), but the residual condition the field
    # itself filters on (also status='open' here) fails for a 'closed' row
    # sharing the group only because both connections subscribe by status --
    # use a channel with an extra residual instead: bind a field whose
    # queryset also filters priority, so a same-status row with the wrong
    # priority exercises the drop.
    channel.tasks = Task.objects.filter(status='open', priority__gte=5).order_by('id')
    async_to_sync(consumer._flush_rx)()
    sent.clear()

    Task.objects.create(name='LowPriority', status='open', priority=1)
    async_to_sync(_pump)(channel_layer, consumer)

    dropped = [m for m in sent if m.get('v') and m['v'][0].get('name') == 'LowPriority']
    assert dropped == []


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_update_failing_residual_is_never_dropped():
    channel_layer = get_channel_layer()
    channel, consumer, sent = _make_consumer(channel_layer, 'conn-a')

    task = Task.objects.create(name='Member', status='open', priority=9)
    channel.tasks = Task.objects.filter(status='open', priority__gte=5).order_by('id')
    async_to_sync(consumer._flush_rx)()
    sent.clear()

    # This update keeps the row in the same dimension group ('open') but
    # fails the residual (priority drops below 5) -- it must still relay:
    # the failing frame *is* the leave signal (list-routing).
    task.priority = 1
    task.save()
    async_to_sync(_pump)(channel_layer, consumer)

    relayed = [m for m in sent if m.get('v') and m['v'][0].get('name') == 'Member']
    assert len(relayed) >= 1
    assert relayed[-1]['v'][0]['priority'] == 1


# -- 3.4: rebind(field) lever -----------------------------------------------


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_rebind_reruns_subscribe_and_resnapshots():
    channel_layer = get_channel_layer()
    channel, consumer, sent = _make_consumer(channel_layer, 'conn-a')

    channel.tasks = Task.objects.filter(status='open').order_by('id')
    async_to_sync(consumer._flush_rx)()
    assert list(channel.tasks) == []

    Task.objects.create(name='Late', status='open', priority=1)
    sent.clear()

    async_to_sync(channel.rebind)('tasks')

    anchor_frames = [m for m in sent if 'q' in m]
    assert len(anchor_frames) == 1
    assert [row['name'] for row in anchor_frames[0]['v']] == ['Late']
    assert 'conn-a' in channel_layer.groups.get(_dimension_group('open'), {})
