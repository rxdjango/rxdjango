"""RxModelField behavior on a ContextChannel."""
import pytest
from asgiref.sync import async_to_sync
from rest_framework import serializers

from rxdjango import ContextChannel, rx
from rxdjango_model.fields import RxModelField, tracked_serializers

from testapp.models import Employee, Task
from testapp.serializers import CompanySerializer, EmployeeWithTeamSerializer, TaskSerializer


class Channel(ContextChannel):
    company = rx.model(CompanySerializer())


class ListChannel(ContextChannel):
    tasks = rx.model(TaskSerializer(many=True))
    employees = rx.model(EmployeeWithTeamSerializer(many=True))


def _drain(walk):
    async def _collect():
        return [layer async for layer, groups in walk]
    return async_to_sync(_collect)()


def test_rx_model_installed_on_rx():
    assert rx.model is not None
    assert isinstance(rx.model(EmployeeWithTeamSerializer()), RxModelField)


def test_state_model_built_at_class_creation():
    field = Channel._rx_fields['company']
    assert field.state_model is not None
    assert field.state_model.instance_type == 'testapp.serializers.CompanySerializer'


def test_serializer_class_is_tracked():
    assert CompanySerializer in tracked_serializers()


def test_rx_model_requires_serializer_instance():
    with pytest.raises(TypeError, match='requires a DRF serializer instance'):
        rx.model(CompanySerializer)


def test_default_is_none():
    assert Channel().company is None


# transaction=True: draining the walk queries off the event loop via
# database_sync_to_async, on a thread that can't share a savepoint-based
# django_db transaction with the test's own connection.
@pytest.mark.django_db(transaction=True)
def test_assignment_deposits_a_drainable_walk(prefetched_company, fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.company = prefetched_company

    assert ch.company is prefetched_company
    # __set__ is sync and cannot run the walk itself (design D6): assignment
    # only deposits the not-yet-started generator, so nothing is enqueued yet.
    assert fake_consumer.messages == []
    walk = fake_consumer.walks['company']

    async def _drain():
        return [layer async for layer, groups in walk]

    layers = async_to_sync(_drain)()

    # Company (anchor), then teams, employees, skills, badges: one layer per
    # instance type, parent-before-child.
    assert len(layers) == 5
    anchor = layers[0]
    assert isinstance(anchor, list)
    assert anchor[0]['_type'] == 'testapp.serializers.CompanySerializer'
    assert all(type(entry) is dict for payload in layers for entry in payload)


@pytest.mark.django_db
def test_assigning_none_enqueues_none(prefetched_company, fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.company = prefetched_company
    ch.company = None
    assert fake_consumer.messages[-1] == ('company', None)
    assert ch.company is None
    # Clearing supersedes the undrained walk from the prior assignment.
    assert 'company' not in fake_consumer.walks


@pytest.mark.django_db
def test_reassignment_supersedes_the_pending_walk(prefetched_company, fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.company = prefetched_company
    first_walk = fake_consumer.walks['company']
    ch.company = prefetched_company
    second_walk = fake_consumer.walks['company']
    assert second_walk is not first_walk


# -- Queryset assignment on list fields (static-queryset-lists, task 1.2) --


@pytest.mark.django_db(transaction=True)
def test_queryset_assignment_snapshots_in_one_anchor_frame(company_tree, fake_consumer):
    """The anchor layer of a `many=True` field is the queryset's full row
    set delivered in a single frame (model-state: 'Queryset snapshot anchors
    in one frame')."""
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.employees = Employee.objects.filter(team__isnull=False).order_by('id')

    layers = _drain(fake_consumer.walks['employees'])
    anchor = layers[0]

    assert {entry['name'] for entry in anchor} == {'Alice', 'Bob', 'Carol'}
    assert all(
        entry['_type'] == 'testapp.serializers.EmployeeWithTeamSerializer'
        for entry in anchor
    )
    # Child layer (team) follows as an ordinary merge frame.
    assert len(layers) == 2


@pytest.mark.django_db(transaction=True)
def test_empty_queryset_sends_empty_anchor_layer(fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.employees = Employee.objects.none()

    layers = _drain(fake_consumer.walks['employees'])

    assert layers == [[]]


@pytest.mark.django_db(transaction=True)
def test_list_field_reassignment_supersedes_the_pending_walk(company_tree, fake_consumer):
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.employees = Employee.objects.all()
    first_walk = fake_consumer.walks['employees']
    ch.employees = Employee.objects.filter(team__isnull=False)
    second_walk = fake_consumer.walks['employees']

    assert second_walk is not first_walk


@pytest.mark.django_db(transaction=True)
def test_reactive_list_field_snapshot_carries_no_group_for_empty_queryset(fake_consumer):
    """A reactive model's `many=True` field still yields the (empty) groups
    list per layer even when the anchor set is empty."""
    ch = ListChannel()
    ch._consumer = fake_consumer
    ch.tasks = Task.objects.none()

    async def _collect():
        return [(layer, groups) async for layer, groups in fake_consumer.walks['tasks']]
    pairs = async_to_sync(_collect)()

    assert pairs == [([], [])]


@pytest.mark.django_db
def test_assignment_without_consumer_skips_serialization(prefetched_company, monkeypatch):
    """With nobody to deliver to, assignment must not pay the serialization
    cost (it is the dominant per-save runtime burden)."""
    ch = Channel()
    calls = []
    field = Channel._rx_fields['company']
    monkeypatch.setattr(field, '_walk_layers', lambda value: calls.append(value))

    ch.company = prefetched_company

    assert ch.company is prefetched_company
    assert calls == []
