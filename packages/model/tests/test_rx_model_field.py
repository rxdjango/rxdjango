"""RxModelField behavior on a ContextChannel."""
import pytest
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


def test_serialize_none_is_none():
    assert Channel._rx_fields['company'].serialize(None) is None


@pytest.mark.django_db
def test_assignment_enqueues_flat_payload(prefetched_company, fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.company = prefetched_company

    assert ch.company is prefetched_company
    assert len(fake_consumer.messages) == 1
    field, payload = fake_consumer.messages[0]
    assert field == 'company'
    assert isinstance(payload, list)
    assert payload[0]['_type'] == 'testapp.serializers.CompanySerializer'
    assert all(type(entry) is dict for entry in payload)


@pytest.mark.django_db
def test_assigning_none_enqueues_none(prefetched_company, fake_consumer):
    ch = Channel()
    ch._consumer = fake_consumer
    ch.company = prefetched_company
    ch.company = None
    assert fake_consumer.messages[-1] == ('company', None)
    assert ch.company is None


@pytest.mark.django_db
def test_assignment_without_consumer_skips_serialization(prefetched_company, monkeypatch):
    """With nobody to deliver to, assignment must not pay the serialization
    cost (it is the dominant per-save runtime burden)."""
    ch = Channel()
    calls = []
    field = Channel._rx_fields['company']
    monkeypatch.setattr(field, 'serialize', lambda value: calls.append(value))

    ch.company = prefetched_company

    assert ch.company is prefetched_company
    assert calls == []
