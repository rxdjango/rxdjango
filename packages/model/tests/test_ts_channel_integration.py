"""Full channel TS rendering with `rx.model` fields, `many=True` included
(static-queryset-lists task 5.1): the generated property type and the
`_modelFields` list-anchor marker.
"""
from rxdjango import ContextChannel, rx
from rxdjango.ts.channels import _render_class

from testapp.serializers import EmployeeWithTeamSerializer, TaskSerializer


class _ListFieldChannel(ContextChannel):
    tasks = rx.model(TaskSerializer(many=True))
    employee = rx.model(EmployeeWithTeamSerializer())


def _rendered():
    return '\n'.join(_render_class(_ListFieldChannel, None))


def test_many_true_field_generates_array_type_initialized_null():
    assert 'tasks: Task[] | null = null;' in _rendered()


def test_single_instance_field_still_generates_plain_null():
    assert 'employee: EmployeeWithTeam | null = null;' in _rendered()


def test_model_fields_marks_the_list_anchor_many_true():
    text = _rendered()
    tasks_at = text.index('"tasks": {')
    employee_at = text.index('"employee": {')
    tasks_block = text[tasks_at:employee_at]
    employee_block = text[employee_at:]

    assert 'many: true,' in tasks_block
    assert 'many: true,' not in employee_block


def test_model_fields_type_annotation_declares_many():
    assert 'many?: boolean;' in _rendered()
