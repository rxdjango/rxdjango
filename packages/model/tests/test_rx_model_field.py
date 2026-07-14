"""RxModelField behavior on a ContextChannel."""
import pytest
from asgiref.sync import async_to_sync
from rest_framework import serializers

from rxdjango import ContextChannel, rx
from rxdjango_model.fields import RxModelField, tracked_serializers

from testapp.serializers import CompanySerializer, EmployeeWithTeamSerializer


class Channel(ContextChannel):
    company = rx.model(CompanySerializer())


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
