"""StateModel introspection and flat-layer serialization."""
import pytest
from asgiref.sync import async_to_sync

from rxdjango_model.state_model import StateModel

from testapp.models import Employee
from testapp.serializers import CompanySerializer, EmployeeWithTeamSerializer

# transaction=True: serialize_state's layer queries run off the event loop
# via database_sync_to_async, on a thread that can't share a savepoint-based
# django_db transaction with the test's own connection.
pytestmark = pytest.mark.django_db(transaction=True)


def flatten(state_model, instance):
    async def _collect():
        return [
            entry
            async for _node, layer in state_model.serialize_state(instance)
            for entry in layer
        ]
    return async_to_sync(_collect)()


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


def test_many_true_declaration_compiles_with_same_shape_as_single_instance():
    """`rx.model(S(many=True))` must compile at class creation exactly like
    `rx.model(S())` -- the ListSerializer wrapper unwrapped once, in
    StateModel.__init__ (design D6) -- not crash in `_disassemble_nested`
    (a bare ListSerializer has no `.fields`)."""
    single = StateModel(CompanySerializer())
    listed = StateModel(CompanySerializer(many=True))

    assert listed.many is True
    assert listed.instance_type == single.instance_type
    assert set(listed.children) == set(single.children)
    assert listed.frontend_model() == single.frontend_model()


def test_many_true_declaration_of_a_leaf_serializer_compiles():
    single = StateModel(EmployeeWithTeamSerializer())
    listed = StateModel(EmployeeWithTeamSerializer(many=True))

    assert listed.many is True
    assert listed.instance_type == single.instance_type
    assert listed['team'].instance_type == single['team'].instance_type


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


def test_walk_issues_one_query_per_type_regardless_of_row_count(
    prefetched_company, django_assert_num_queries,
):
    """O(edges), not O(rows) (ADR-0016): every query is batched via
    `pk__in`/`IN (...)`, so the count is fixed by the serializer tree's
    edges, never by row counts.

    Company (anchor; teams/employees/skills/badges already prefetched by the
    caller, 0 queries here) -> Team pk__in (1) -> [prefetch Team.employees,
    needed so the Team layer's own dict carries its employees' pks without a
    DRF per-row query] (1) -> Employee pk__in (1) -> [prefetch
    Employee.skills, Employee.badge, same reason] (2) -> Skill pk__in (1) ->
    Badge pk__in (1) = 7 queries total, independent of row counts (see
    `test_query_count_does_not_scale_with_row_count`).
    """
    sm = StateModel(CompanySerializer())
    with django_assert_num_queries(7):
        flatten(sm, prefetched_company)


def test_query_count_does_not_scale_with_row_count(company_tree, django_assert_num_queries):
    """Doubling the fixture's rows must not change the query count."""
    from testapp.models import Company, Employee, Team

    extra_team = Team.objects.create(id=3, name='Ops', company=company_tree)
    for i in range(5, 15):
        Employee.objects.create(id=i, name=f'Employee {i}', team=extra_team)

    prefetched = Company.objects.prefetch_related(
        'teams__employees__skills',
        'teams__employees__badge',
    ).get(id=company_tree.id)

    sm = StateModel(CompanySerializer())
    with django_assert_num_queries(7):
        flatten(sm, prefetched)


def test_shared_child_fetched_once(prefetched_company):
    """Two employees (Alice, Bob) share team #1 (Platform) as a fan-in edge;
    the team layer must carry that shared pk once, not once per referrer."""
    flat = flatten(StateModel(CompanySerializer()), prefetched_company)
    team_ids = [
        entry['id'] for entry in flat
        if entry['_type'].endswith('TeamSerializer')
    ]
    assert sorted(team_ids) == [1, 2]


def test_serialize_does_not_instantiate_serializers(prefetched_company, monkeypatch):
    """All DRF field binding happens at class-creation time.

    Instantiating a DRF serializer deep-copies every declared field, so a
    per-save instantiation puts the compile-time burden back on the save
    path (~25x slower). Serialization must reuse pre-built instances.
    """
    sm = StateModel(CompanySerializer())

    instantiations = []
    for nodes in sm.index.values():
        for node in nodes:
            orig_init = node.flat_serializer.__init__

            def counting_init(self, *args, _orig=orig_init, **kwargs):
                instantiations.append(type(self).__name__)
                _orig(self, *args, **kwargs)

            monkeypatch.setattr(node.flat_serializer, '__init__', counting_init)

    flatten(sm, prefetched_company)
    sm.serialize_instance(prefetched_company)

    assert instantiations == []
