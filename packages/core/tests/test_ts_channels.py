"""Pure type-mapping helpers used by the TS channel emitter."""
from rxdjango.ts.channels import _ts_literal, _ts_type


def test_scalar_type_mapping():
    assert _ts_type(int) == 'number'
    assert _ts_type(float) == 'number'
    assert _ts_type(str) == 'string'
    assert _ts_type(bool) == 'boolean'
    assert _ts_type(type(None)) == 'null'
    assert _ts_type(dict) == 'any'


def test_union_type_mapping():
    assert _ts_type(int | None) == 'number | null'
    assert _ts_type(str | int) == 'string | number'


def test_union_deduplicates_parts():
    assert _ts_type(int | float) == 'number'


def test_literals():
    assert _ts_literal(None) == 'null'
    assert _ts_literal(True) == 'true'
    assert _ts_literal(False) == 'false'
    assert _ts_literal(3) == '3'
    assert _ts_literal(1.5) == '1.5'
    assert _ts_literal('hi') == "'hi'"


def test_string_literal_escaping():
    assert _ts_literal("it's") == "'it\\'s'"
    assert _ts_literal('a\\b') == "'a\\\\b'"


def test_unsupported_literal_returns_none():
    assert _ts_literal({'a': 1}) is None


# -- rx[list[S]] type mapping (ADR-0017) -----------------------------------


def test_homogeneous_list_type_mapping():
    assert _ts_type(list[int]) == 'number[]'
    assert _ts_type(list[str]) == 'string[]'


def test_union_element_list_is_parenthesized():
    assert _ts_type(list[int | str]) == '(number | string)[]'


def test_nullable_element_list_is_parenthesized():
    assert _ts_type(list[str | None]) == '(string | null)[]'


def test_optional_list_field_puts_null_outside_the_brackets():
    assert _ts_type(list[int] | None) == 'number[] | null'


def test_list_literal_rendering():
    assert _ts_literal([]) == '[]'
    assert _ts_literal([1, 2]) == '[1, 2]'
    assert _ts_literal(['a', 1]) == "['a', 1]"


def test_list_literal_with_null_element():
    assert _ts_literal(['a', None]) == "['a', null]"
