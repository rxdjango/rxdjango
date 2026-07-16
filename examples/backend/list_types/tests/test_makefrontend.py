from rxdjango.testing import FrontendTestCase
from rxdjango.testing.ts_ast import find_member


class MakeFrontendListTypesTests(FrontendTestCase):
    app_name = 'list_types'
    channel_file = 'list_types.channels.ts'
    class_name = 'ListTypesChannel'

    def test_emits_context_channel_class(self):
        cls = self.parse_class()
        self.assertTrue(cls['exported'], 'ListTypesChannel must be exported')
        self.assertIn(
            {'kind': 'extends', 'name': 'ContextChannel'},
            cls['heritage'],
            'ListTypesChannel must extend ContextChannel',
        )

    def test_mixed_field_is_a_parenthesized_union_array(self):
        cls = self.parse_class()
        member = find_member(cls, 'mixed')
        self.assertIsNotNone(member, '`mixed` property not found')
        self.assertEqual(member['type'], '(number | string)[]')
        self.assertEqual(
            member['initializer']['text'],
            "[1, 'two', 3]",
        )

    def test_optional_numbers_field_is_array_or_null(self):
        cls = self.parse_class()
        member = find_member(cls, 'optional_numbers')
        self.assertIsNotNone(member, '`optional_numbers` property not found')
        self.assertEqual(member['type'], 'number[] | null')
        self.assertEqual(member['initializer']['text'], 'null')
