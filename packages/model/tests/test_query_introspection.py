"""Bind-time queryset introspection (ADR-0019 D3, static-queryset-lists task 2.1/2.2).

Extracting `(column, lookup, value)` conjunctions and the ordering spec from
a `many=True` field's queryset, and rejecting -- loudly, naming the
offending condition -- every shape design D3 does not support.
"""
from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework import serializers

from rxdjango_model.query_introspection import (
    UnsupportedQuerysetError,
    introspect_queryset,
)
from rxdjango_model.state_model import StateModel

from testapp.models import Employee, Task
from testapp.serializers import EmployeeWithTeamSerializer, TaskSerializer

pytestmark = pytest.mark.django_db


class _BareTaskSerializerWithoutName(serializers.ModelSerializer):
    """Leaves out `name` -- exercises the "not a serializer field" rejection
    without a dedicated model."""
    class Meta:
        model = Task
        fields = ['id', 'status', 'priority']


@pytest.fixture
def task_state_model():
    return StateModel(TaskSerializer(many=True))


@pytest.fixture
def employee_state_model():
    return StateModel(EmployeeWithTeamSerializer(many=True))


# -- Accepted shapes --------------------------------------------------------


def test_no_conditions_or_ordering(task_state_model):
    descriptor = introspect_queryset(Task.objects.all(), task_state_model)
    assert descriptor.to_wire() == {'w': [], 's': ['id']}  # Task.Meta.ordering


def test_exact_lookup(task_state_model):
    descriptor = introspect_queryset(
        Task.objects.filter(status='open'), task_state_model,
    )
    assert descriptor.to_wire()['w'] == [['status', 'exact', 'open']]


@pytest.mark.parametrize('lookup,value', [
    ('gt', 1), ('gte', 1), ('lt', 5), ('lte', 5),
])
def test_comparison_lookups(task_state_model, lookup, value):
    descriptor = introspect_queryset(
        Task.objects.filter(**{f'priority__{lookup}': value}), task_state_model,
    )
    assert descriptor.to_wire()['w'] == [['priority', lookup, value]]


def test_in_lookup(task_state_model):
    descriptor = introspect_queryset(
        Task.objects.filter(status__in=['open', 'closed']), task_state_model,
    )
    assert descriptor.to_wire()['w'] == [['status', 'in', ['open', 'closed']]]


def test_isnull_lookup(employee_state_model):
    descriptor = introspect_queryset(
        Employee.objects.filter(team__isnull=True), employee_state_model,
    )
    assert descriptor.to_wire()['w'] == [['team', 'isnull', True]]


def test_conjunction_of_conditions(task_state_model):
    descriptor = introspect_queryset(
        Task.objects.filter(status='open', priority__gte=3), task_state_model,
    )
    assert sorted(descriptor.to_wire()['w']) == sorted([
        ['status', 'exact', 'open'],
        ['priority', 'gte', 3],
    ])


def test_datetime_value_serializes_exactly_as_drf_renders_the_field(task_state_model):
    now = timezone.now()
    descriptor = introspect_queryset(
        Task.objects.filter(created_at__gte=now), task_state_model,
    )
    expected = TaskSerializer().fields['created_at'].to_representation(now)
    assert descriptor.to_wire()['w'] == [['created_at', 'gte', expected]]
    assert isinstance(expected, str)


def test_datetime_value_under_a_non_utc_offset_matches_drfs_own_rendering(task_state_model):
    """Lookup parity (gap 2): a timezone-aware bind-time value carrying a
    non-UTC offset must still emit through the *same* `to_representation`
    call the live-row serializer uses -- never a bare `.isoformat()`/`repr()`
    that could drift from DRF's own rendering (e.g. a different offset
    format, or a naive/aware inconsistency) and break the client's
    string-vs-instant comparison (design D3)."""
    aware_non_utc = datetime.datetime(
        2026, 7, 16, 12, 30, 0, tzinfo=timezone.get_fixed_timezone(120),
    )
    descriptor = introspect_queryset(
        Task.objects.filter(created_at__gte=aware_non_utc), task_state_model,
    )
    expected = TaskSerializer().fields['created_at'].to_representation(aware_non_utc)
    assert descriptor.to_wire()['w'] == [['created_at', 'gte', expected]]
    assert isinstance(expected, str)


def test_fk_exact_condition_carries_the_raw_pk(employee_state_model):
    descriptor = introspect_queryset(
        Employee.objects.filter(team=7), employee_state_model,
    )
    assert descriptor.to_wire()['w'] == [['team', 'exact', 7]]


def test_ordering_ascending(task_state_model):
    descriptor = introspect_queryset(
        Task.objects.order_by('priority'), task_state_model,
    )
    assert descriptor.to_wire()['s'] == ['priority']


def test_ordering_descending_and_multi_column(task_state_model):
    descriptor = introspect_queryset(
        Task.objects.order_by('-priority', 'id'), task_state_model,
    )
    assert descriptor.to_wire()['s'] == ['-priority', 'id']


def test_ordering_falls_back_to_model_meta_ordering(employee_state_model):
    # Employee.Meta.ordering = ['id']; no explicit order_by().
    descriptor = introspect_queryset(Employee.objects.all(), employee_state_model)
    assert descriptor.to_wire()['s'] == ['id']


def test_empty_queryset_still_introspects(task_state_model):
    descriptor = introspect_queryset(Task.objects.none(), task_state_model)
    assert descriptor.to_wire() == {'w': [], 's': ['id']}


# -- Rejections, named (task 2.1) -------------------------------------------


def test_non_queryset_value_rejected(task_state_model):
    with pytest.raises(TypeError, match='requires a Django queryset'):
        introspect_queryset([1, 2, 3], task_state_model)


def test_or_structure_rejected(task_state_model):
    qs = Task.objects.filter(status='open') | Task.objects.filter(status='closed')
    with pytest.raises(UnsupportedQuerysetError, match='OR'):
        introspect_queryset(qs, task_state_model)


def test_not_structure_rejected(task_state_model):
    with pytest.raises(UnsupportedQuerysetError, match='NOT'):
        introspect_queryset(Task.objects.exclude(status='closed'), task_state_model)


def test_unsupported_lookup_rejected_naming_it(task_state_model):
    with pytest.raises(UnsupportedQuerysetError, match="'contains'"):
        introspect_queryset(
            Task.objects.filter(name__contains='foo'), task_state_model,
        )


def test_joined_column_rejected_naming_the_relation(employee_state_model):
    with pytest.raises(UnsupportedQuerysetError, match="'team__name'"):
        introspect_queryset(
            Employee.objects.filter(team__name='Platform'), employee_state_model,
        )


def test_non_serialized_column_rejected_naming_it():
    # `name` is a real Task column but not on this serializer's fields.
    with pytest.raises(UnsupportedQuerysetError, match="'name'"):
        introspect_queryset(
            Task.objects.filter(name='x'),
            StateModel(_BareTaskSerializerWithoutName(many=True)),
        )


def test_unsupported_ordering_column_rejected_naming_it():
    with pytest.raises(UnsupportedQuerysetError, match="'name'"):
        introspect_queryset(
            Task.objects.order_by('name'),
            StateModel(_BareTaskSerializerWithoutName(many=True)),
        )


def test_joined_ordering_column_rejected(employee_state_model):
    with pytest.raises(UnsupportedQuerysetError, match='team__name'):
        introspect_queryset(
            Employee.objects.order_by('team__name'), employee_state_model,
        )
