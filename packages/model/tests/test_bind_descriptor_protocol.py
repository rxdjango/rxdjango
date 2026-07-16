"""Wire-level test for the bind descriptor (static-queryset-lists task 2.2).

The `q` slot rides the snapshot anchor frame of a `many=True` field
(ADR-0019 D1, `wire-protocol`): conditions and ordering travel with the
anchor's `v` in one frame, atomically: no separate descriptor frame, and no
`q` on any later merge frame for the same field.

Drives a bare `ContextConsumer` directly (as `test_list_rebind_integration.py`
does) rather than the full ASGI/`WebsocketCommunicator` loop: that loop plus
real `database_sync_to_async` ORM work inside an async test reliably leaks
into later, unmarked tests' database-access guard (see that module's
docstring) -- calling `consumer._flush_rx()` exercises the exact same frame
assembly with none of that instability.
"""
from __future__ import annotations

import json

import pytest
from asgiref.sync import async_to_sync

from rxdjango import ContextChannel, rx
from rxdjango.consumers import ContextConsumer

from testapp.models import Employee, Task
from testapp.serializers import EmployeeWithTeamSerializer, TaskSerializer

pytestmark = pytest.mark.django_db(transaction=True)


class TasksChannel(ContextChannel):
    tasks = rx.model(TaskSerializer(many=True))


class EmployeesChannel(ContextChannel):
    employees = rx.model(EmployeeWithTeamSerializer(many=True))


def _wire_up(channel):
    consumer = ContextConsumer()
    consumer.channel_layer = None
    sent: list[dict] = []

    async def fake_send(text_data=None, **kwargs):
        sent.append(json.loads(text_data))
    consumer.send = fake_send

    channel._consumer = consumer
    return consumer, sent


def _drain(consumer):
    async_to_sync(consumer._flush_rx)()


def test_snapshot_frame_carries_conditions_and_ordering():
    Task.objects.create(name='A', status='open', priority=1)
    Task.objects.create(name='B', status='open', priority=5)
    Task.objects.create(name='C', status='closed', priority=9)

    channel = TasksChannel()
    consumer, sent = _wire_up(channel)

    channel.tasks = Task.objects.filter(status='open').order_by('-priority', 'id')
    _drain(consumer)

    frame = sent[0]
    assert frame['f'] == 'tasks'
    assert frame['q'] == {'w': [['status', 'exact', 'open']], 's': ['-priority', 'id']}
    assert 'o' not in frame
    assert len(frame['v']) == 2
    # Descending priority: B (5) before A (1).
    assert [row['name'] for row in frame['v']] == ['B', 'A']


def test_empty_snapshot_still_carries_the_descriptor():
    channel = TasksChannel()
    consumer, sent = _wire_up(channel)

    channel.tasks = Task.objects.filter(status='archived').order_by('-priority', 'id')
    _drain(consumer)

    frame = sent[0]
    assert frame['v'] == []
    assert frame['q'] == {'w': [['status', 'exact', 'archived']], 's': ['-priority', 'id']}


def _create_employee_with_team():
    from testapp.models import Company, Team

    company = Company.objects.create(name='ACME')
    team = Team.objects.create(name='Platform', company=company)
    return Employee.objects.create(name='Bob', team=team)


def test_child_layer_frame_carries_no_descriptor():
    _create_employee_with_team()

    channel = EmployeesChannel()
    consumer, sent = _wire_up(channel)

    channel.employees = Employee.objects.order_by('id')
    _drain(consumer)

    anchor_frame, child_frame = sent
    assert anchor_frame['f'] == 'employees'
    assert 'q' in anchor_frame
    assert child_frame['f'] == 'employees'
    assert 'q' not in child_frame
