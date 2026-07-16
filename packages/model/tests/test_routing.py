"""Router surface and registry (routed-list-delivery task 1.1/1.2).

`Router`/`ColumnRouter`/`BroadcastRouter` are plain, DB-free contracts:
`publish(instance)` and `subscribe(channel)` each return an iterable of
opaque group values. Registration (`register_router`, keyed by the
Router's own `key`) and group naming are exercised independently of the
write/consumer paths those pieces plug into later.
"""
from __future__ import annotations

import pytest
from types import SimpleNamespace

from rxdjango import ContextChannel, rx
from rxdjango_model.routing import BroadcastRouter, ColumnRouter, Router
from rxdjango_model.routing_registry import (
    register_router,
    route_group_name,
    route_groups_for_router,
    routers_for,
    routing_registry,
)

from testapp.models import Employee, Task
from testapp.serializers import CompanySerializer, EmployeeWithTeamSerializer, TaskSerializer


# -- Router / ColumnRouter / BroadcastRouter -------------------------------


def test_column_router_publish_reads_the_named_attribute():
    router = ColumnRouter('priority')
    row = SimpleNamespace(priority=5)
    assert list(router.publish(row)) == [5]


def test_column_router_key_is_the_column_name():
    assert ColumnRouter('project_id').key == 'project_id'


def test_column_router_columns_is_the_single_column():
    assert ColumnRouter('project_id').columns == ('project_id',)


def test_column_router_subscribe_extracts_exact_value_from_bound_queryset():
    router = ColumnRouter('priority')
    router.bind_field('tasks')
    channel = SimpleNamespace(tasks=Task.objects.filter(priority=5))
    assert router.subscribe(channel) == [5]


def test_column_router_subscribe_extracts_in_values_from_bound_queryset():
    router = ColumnRouter('priority')
    router.bind_field('tasks')
    channel = SimpleNamespace(tasks=Task.objects.filter(priority__in=[1, 2, 3]))
    assert router.subscribe(channel) == [1, 2, 3]


def test_column_router_subscribe_with_no_matching_condition_is_empty():
    router = ColumnRouter('priority')
    router.bind_field('tasks')
    channel = SimpleNamespace(tasks=Task.objects.all())
    assert router.subscribe(channel) == []


def test_column_router_subscribe_before_bind_field_is_empty():
    router = ColumnRouter('priority')
    channel = SimpleNamespace(tasks=Task.objects.filter(priority=5))
    assert router.subscribe(channel) == []


def test_broadcast_router_is_a_constant_on_both_sides():
    router = BroadcastRouter()
    row = SimpleNamespace(priority=5)
    channel = SimpleNamespace()
    assert list(router.publish(row)) == list(router.subscribe(channel))


def test_custom_router_key_defaults_to_dotted_class_path():
    class MyRouter(Router):
        def publish(self, instance):
            return []

        def subscribe(self, channel):
            return []

    assert MyRouter().key == f'{__name__}.{MyRouter.__qualname__}'


def test_router_base_methods_are_not_implemented():
    router = Router()
    with pytest.raises(NotImplementedError):
        router.publish(None)
    with pytest.raises(NotImplementedError):
        router.subscribe(None)


# -- routing= declaration surface (rx.model) -------------------------------


def test_routing_none_rejected_at_declaration():
    with pytest.raises(TypeError, match='routing=None'):
        rx.model(TaskSerializer(many=True), routing=None)


def test_routing_on_non_list_field_rejected():
    with pytest.raises(TypeError, match='many=True'):
        rx.model(CompanySerializer(), routing='id')


def test_routing_requires_str_router_or_omitted():
    with pytest.raises(TypeError, match='routing='):
        rx.model(TaskSerializer(many=True), routing=123)


def test_column_string_sugar_builds_a_column_router():
    field = rx.model(TaskSerializer(many=True), routing='priority')
    assert isinstance(field.routing, ColumnRouter)
    assert field.routing.column == 'priority'


def test_omitted_routing_is_static():
    field = rx.model(TaskSerializer(many=True))
    assert field.routing is None


def test_router_instance_passes_through():
    router = BroadcastRouter()
    field = rx.model(TaskSerializer(many=True), routing=router)
    assert field.routing is router


def test_column_router_is_bound_to_its_field_name_at_class_creation():
    class Channel(ContextChannel):
        tasks = rx.model(TaskSerializer(many=True), routing='priority')

    assert Channel._rx_fields['tasks'].routing._field_name == 'tasks'


# -- Registration and group naming -----------------------------------------


def test_contribute_to_channel_registers_the_router():
    class Channel(ContextChannel):
        tasks = rx.model(TaskSerializer(many=True), routing='priority')

    routers = routers_for(Task)
    assert 'priority' in routers
    assert isinstance(routers['priority'], ColumnRouter)


def test_two_channels_declaring_the_same_dimension_dedupe():
    class ChannelA(ContextChannel):
        tasks = rx.model(TaskSerializer(many=True), routing='status')

    class ChannelB(ContextChannel):
        other_tasks = rx.model(TaskSerializer(many=True), routing='status')

    router_a = ChannelA._rx_fields['tasks'].routing
    router_b = ChannelB._rx_fields['other_tasks'].routing
    assert router_a is not router_b

    # Same key ('status') -> the registry holds one of the two instances,
    # not both: dedup by key, first registration wins.
    registered = routers_for(Task)['status']
    assert registered in (router_a, router_b)


def test_route_group_name_is_deterministic_and_value_sensitive():
    a = route_group_name('task_board.task', 'project_id', 5)
    b = route_group_name('task_board.task', 'project_id', 5)
    c = route_group_name('task_board.task', 'project_id', 7)
    assert a == b
    assert a != c
    assert a.startswith('rx.route.task_board.task.project_id.')


def test_route_group_name_handles_opaque_tuple_values():
    name = route_group_name('task_board.run', 'membership', ('project', 5))
    assert name.startswith('rx.route.task_board.run.membership.')


def test_route_groups_for_router_filters_none_and_dedupes():
    router = ColumnRouter('project_id')
    groups = route_groups_for_router(router, Task, [5, None, 5])
    assert groups == [route_group_name(Task._meta.label_lower, 'project_id', 5)]


def test_routing_registry_returns_a_copy():
    class Channel(ContextChannel):
        employees = rx.model(EmployeeWithTeamSerializer(many=True), routing='team_id')

    snapshot = routing_registry()
    snapshot[Employee].clear()
    assert 'team_id' in routers_for(Employee)
