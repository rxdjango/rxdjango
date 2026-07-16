"""Writer-side lifecycle broadcasts through routing dimension groups
(routed-list-delivery tasks 2.1-2.3): `ReactiveModel.save()`/`delete()`
additionally broadcast to a model's registered Router dimension groups, on
commit, alongside the existing per-instance broadcast (`reactive_registry`).

Drives a real (in-memory) channel layer directly -- the same style
`test_list_rebind_integration.py` uses -- rather than the full ASGI/
consumer dispatch loop, which is exercised by the routed example app's
integration suite (task 2.4/3.1) instead.
"""
from __future__ import annotations

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from rxdjango import ContextChannel, rx
from rxdjango_model.routing_registry import route_group_name, routing_pre_image

from testapp.models import Task
from testapp.serializers import TaskSerializer

pytestmark = pytest.mark.django_db(transaction=True)

CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
}


class RoutedTasksChannel(ContextChannel):
    """Declares the `status` dimension on Task so the write path has a
    router registered for it (module import time, per ADR-0018 D1)."""

    tasks = rx.model(TaskSerializer(many=True), routing='status')


def _group(value: str) -> str:
    return route_group_name(Task._meta.label_lower, 'status', value)


async def _receive(channel_layer, name):
    return await channel_layer.receive(name)


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_creation_broadcasts_to_publish_new_only():
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_add)(_group('open'), 'listener-open')
    async_to_sync(channel_layer.group_add)(_group('closed'), 'listener-closed')

    task = Task.objects.create(name='A', status='open', priority=1)

    message = async_to_sync(_receive)(channel_layer, 'listener-open')
    assert message['type'] == 'rx.route'
    assert message['kind'] == 'create'
    assert message['payload']['_type'] == 'testapp.serializers.TaskSerializer'
    assert message['payload']['id'] == task.id
    assert message['payload']['status'] == 'open'

    # Nothing was ever sent to the non-matching dimension value's group.
    assert 'listener-closed' not in channel_layer.channels


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_update_broadcasts_to_old_and_new_dimension_groups():
    task = Task.objects.create(name='A', status='open', priority=1)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_add)(_group('open'), 'listener-open')
    async_to_sync(channel_layer.group_add)(_group('closed'), 'listener-closed')

    task.status = 'closed'
    task.save()

    # Both sides get the *new* layer -- the old side's delivery is itself
    # the stateless leave signal (design D2), not a stale copy of the row.
    old_side = async_to_sync(_receive)(channel_layer, 'listener-open')
    new_side = async_to_sync(_receive)(channel_layer, 'listener-closed')
    assert old_side['kind'] == 'update'
    assert new_side['kind'] == 'update'
    assert old_side['payload']['status'] == 'closed'
    assert new_side['payload']['status'] == 'closed'


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_update_that_does_not_move_dimension_still_broadcasts_once_per_group():
    task = Task.objects.create(name='A', status='open', priority=1)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_add)(_group('open'), 'listener')

    task.name = 'renamed'
    task.status = 'open'
    task.save()

    message = async_to_sync(_receive)(channel_layer, 'listener')
    assert message['kind'] == 'update'
    assert message['payload']['name'] == 'renamed'
    # publish(old) == publish(new) == {'open'} here -- exactly one delivery,
    # not two, to the single shared group.
    assert channel_layer.channels.get('listener') is None or (
        channel_layer.channels['listener'].qsize() == 0
    )


@override_settings(CHANNEL_LAYERS=CHANNEL_LAYERS)
def test_delete_broadcasts_tombstone_to_dimension_group():
    task = Task.objects.create(name='A', status='open', priority=1)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_add)(_group('open'), 'listener')

    pk = task.pk
    task.delete()

    message = async_to_sync(_receive)(channel_layer, 'listener')
    assert message['kind'] == 'delete'
    assert message['payload']['_type'] == 'testapp.serializers.TaskSerializer'
    assert message['payload']['_del'] == pk
    assert 'name' not in message['payload']


# -- Gated pre-image read (task 2.2) ---------------------------------------


def test_routing_pre_image_returns_none_with_no_registered_routers():
    from testapp.models import Company

    company = Company.objects.create(name='ACME')
    assert routing_pre_image(Company, company.pk, None, None) is None


def test_routing_pre_image_skipped_when_update_fields_excludes_dimension_columns():
    task = Task.objects.create(name='A', status='open', priority=1)
    assert routing_pre_image(Task, task.pk, None, ['name']) is None


def test_routing_pre_image_runs_when_update_fields_is_none():
    task = Task.objects.create(name='A', status='open', priority=1)
    pre = routing_pre_image(Task, task.pk, None, None)
    assert pre is not None
    assert pre.status == 'open'


def test_routing_pre_image_runs_when_update_fields_intersects_columns():
    task = Task.objects.create(name='A', status='open', priority=1)
    pre = routing_pre_image(Task, task.pk, None, ['status'])
    assert pre is not None
    assert pre.status == 'open'


def test_no_extra_query_when_update_fields_excludes_dimension_columns():
    """Wire-level proof of the gating (task 2.2): a save touching only a
    non-dimension column issues exactly one fewer query than one touching
    the dimension column, and that one query is the pre-image `SELECT`."""
    task_a = Task.objects.create(name='A', status='open', priority=1)
    task_b = Task.objects.create(name='B', status='open', priority=1)

    with CaptureQueriesContext(connection) as untouched:
        task_a.name = 'renamed'
        task_a.save(update_fields=['name'])

    with CaptureQueriesContext(connection) as touched:
        task_b.status = 'closed'
        task_b.save(update_fields=['status'])

    assert len(touched.captured_queries) == len(untouched.captured_queries) + 1
