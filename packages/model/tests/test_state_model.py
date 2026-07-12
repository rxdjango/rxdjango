"""StateModel introspection and flat-layer serialization."""
import pytest

from rxdjango_model.state_model import StateModel

from testapp.models import Employee
from testapp.serializers import CompanySerializer, EmployeeWithTeamSerializer

pytestmark = pytest.mark.django_db


def flatten(state_model, instance):
    return [entry for layer in state_model.serialize_state(instance) for entry in layer]


def test_tree_shape():
    sm = StateModel(CompanySerializer())
    assert set(sm.children) == {'teams'}
    teams = sm['teams']
    assert teams.many is True
    employees = teams['employees']
    assert employees.many is True
    assert set(employees.children) == {'skills', 'badge'}
    assert employees['skills'].many is True
    assert employees['badge'].many is False


def test_instance_types_are_dotted_serializer_paths():
    sm = StateModel(CompanySerializer())
    assert sm.instance_type == 'testapp.serializers.CompanySerializer'
    assert sm['teams'].instance_type == 'testapp.serializers.TeamSerializer'


def test_frontend_model_maps_relation_fields():
    assert StateModel(CompanySerializer()).frontend_model() == {
        'testapp.serializers.CompanySerializer': {
            'teams': 'testapp.serializers.TeamSerializer',
        },
        'testapp.serializers.TeamSerializer': {
            'employees': 'testapp.serializers.EmployeeSerializer',
        },
        'testapp.serializers.EmployeeSerializer': {
            'skills': 'testapp.serializers.SkillSerializer',
            'badge': 'testapp.serializers.BadgeSerializer',
        },
        'testapp.serializers.SkillSerializer': {},
        'testapp.serializers.BadgeSerializer': {},
    }


def test_serialize_state_flattens_every_layer(prefetched_company):
    flat = flatten(StateModel(CompanySerializer()), prefetched_company)

    assert all('_type' in entry for entry in flat)
    assert {(entry['_type'].rsplit('.', 1)[-1], entry['id']) for entry in flat} == {
        ('CompanySerializer', 1),
        ('TeamSerializer', 1), ('TeamSerializer', 2),
        ('EmployeeSerializer', 1), ('EmployeeSerializer', 2), ('EmployeeSerializer', 3),
        ('SkillSerializer', 1), ('SkillSerializer', 2),
        ('BadgeSerializer', 1), ('BadgeSerializer', 2), ('BadgeSerializer', 3),
    }


def test_relations_are_flattened_to_primary_keys(prefetched_company):
    flat = flatten(StateModel(CompanySerializer()), prefetched_company)
    by_key = {(entry['_type'].rsplit('.', 1)[-1], entry['id']): entry for entry in flat}

    assert by_key[('CompanySerializer', 1)]['teams'] == [1, 2]
    assert by_key[('TeamSerializer', 1)]['employees'] == [1, 2]
    assert by_key[('EmployeeSerializer', 1)]['skills'] == [1, 2]
    assert by_key[('EmployeeSerializer', 1)]['badge'] == 1


def test_forward_fk_serializes_instance_then_child(company_tree):
    alice = Employee.objects.select_related('team').get(id=1)
    flat = flatten(StateModel(EmployeeWithTeamSerializer()), alice)

    assert [entry['_type'].rsplit('.', 1)[-1] for entry in flat] == [
        'EmployeeWithTeamSerializer', 'TeamNameSerializer',
    ]
    assert flat[0]['team'] == 1
    assert flat[1] == {'id': 1, 'name': 'Platform',
                       '_type': 'testapp.serializers.TeamNameSerializer'}


def test_null_forward_fk_yields_no_child_layer(company_tree):
    dave = Employee.objects.select_related('team').get(id=4)
    flat = flatten(StateModel(EmployeeWithTeamSerializer()), dave)

    assert len(flat) == 1
    assert flat[0]['team'] is None


def test_serialize_instance_tags_type(company_tree):
    sm = StateModel(EmployeeWithTeamSerializer())
    alice = Employee.objects.select_related('team').get(id=1)
    data = sm.serialize_instance(alice)
    assert data['_type'] == 'testapp.serializers.EmployeeWithTeamSerializer'
    assert data['name'] == 'Alice'
    assert data['team'] == 1


def test_serialize_delete_shape(company_tree):
    sm = StateModel(EmployeeWithTeamSerializer())
    alice = Employee.objects.get(id=1)
    assert sm.serialize_delete(alice) == {
        '_type': 'testapp.serializers.EmployeeWithTeamSerializer',
        '_del': 1,
    }


def test_prefetched_tree_serializes_with_zero_queries(prefetched_company, django_assert_num_queries):
    sm = StateModel(CompanySerializer())
    with django_assert_num_queries(0):
        flatten(sm, prefetched_company)
