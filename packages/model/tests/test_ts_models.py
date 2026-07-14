"""TypeScript interface generation from DRF serializers."""
from rest_framework import serializers

from rxdjango_model.fields import RxModelField
from rxdjango_model.ts.models import (
    _render_interface,
    _serializer_field_ts_type,
    interface_name,
    resolve_model_field_ts_type,
)

from testapp.serializers import CompanySerializer, EmployeeWithTeamSerializer


def test_interface_name_strips_serializer_suffix():
    assert interface_name(CompanySerializer) == 'Company'


def test_render_interface():
    assert _render_interface(EmployeeWithTeamSerializer) == [
        'export interface EmployeeWithTeam {',
        '  _loaded: true;',
        '  id: number;',
        '  name: string;',
        '  team: TeamName | Unloaded;',
        '}',
    ]


def test_resolve_model_field_ts_type_single():
    field = RxModelField(CompanySerializer())
    assert resolve_model_field_ts_type(field) == 'Company | null'


def test_resolve_model_field_ts_type_many():
    field = RxModelField(CompanySerializer(many=True))
    assert resolve_model_field_ts_type(field) == 'Company[] | null'


def test_resolve_ignores_plain_rx_fields():
    assert resolve_model_field_ts_type(object()) is None


def test_scalar_field_ts_types():
    assert _serializer_field_ts_type(serializers.IntegerField()) == 'number'
    assert _serializer_field_ts_type(serializers.FloatField()) == 'number'
    assert _serializer_field_ts_type(serializers.BooleanField()) == 'boolean'
    assert _serializer_field_ts_type(serializers.CharField()) == 'string'
    assert _serializer_field_ts_type(serializers.DateTimeField()) == 'string'
    assert _serializer_field_ts_type(serializers.DictField()) == 'Record<string, unknown>'


def test_nullable_field_gets_null_union():
    assert _serializer_field_ts_type(serializers.IntegerField(allow_null=True)) == 'number | null'


def test_list_field_ts_type():
    assert _serializer_field_ts_type(
        serializers.ListField(child=serializers.CharField())
    ) == 'string[]'


def test_relation_field_gets_unloaded_union():
    assert _serializer_field_ts_type(CompanySerializer()) == 'Company | Unloaded'


def test_nullable_relation_field_gets_unloaded_and_null_union():
    assert _serializer_field_ts_type(
        CompanySerializer(allow_null=True)
    ) == 'Company | Unloaded | null'


def test_relation_list_field_wraps_union_in_parens():
    # `Company | Unloaded[]` would parse as `Company | (Unloaded[])`, not
    # `(Company | Unloaded)[]` -- the union must be parenthesized before `[]`.
    assert _serializer_field_ts_type(
        CompanySerializer(many=True)
    ) == '(Company | Unloaded)[]'
