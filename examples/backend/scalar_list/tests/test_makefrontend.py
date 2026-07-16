from rxdjango.testing import FrontendTestCase
from rxdjango.testing.ts_ast import find_member


class MakeFrontendScalarListTests(FrontendTestCase):
    app_name = 'scalar_list'
    channel_file = 'scalar_list.channels.ts'
    class_name = 'ScalarListChannel'

    def test_emits_context_channel_class(self):
        cls = self.parse_class()
        self.assertTrue(cls['exported'], 'ScalarListChannel must be exported')
        self.assertIn(
            {'kind': 'extends', 'name': 'ContextChannel'},
            cls['heritage'],
            'ScalarListChannel must extend ContextChannel',
        )

    def test_items_field_is_generated_as_a_string_array(self):
        cls = self.parse_class()
        member = find_member(cls, 'items')
        self.assertIsNotNone(member, '`items` property not found on ScalarListChannel')
        self.assertEqual(member['kind'], 'property')
        self.assertEqual(member['type'], 'string[]')
        self.assertIsNotNone(
            member['initializer'],
            '`items` must have a default value',
        )
        self.assertEqual(
            member['initializer']['text'],
            "['apple', 'banana', 'cherry']",
        )

    def test_append_action_declared(self):
        cls = self.parse_class()
        member = find_member(cls, 'append')
        self.assertIsNotNone(member, '`append` action not found on ScalarListChannel')
        self.assertEqual(member['kind'], 'method')
        self.assertTrue(member['async'], 'action must be emitted as async')

    def test_endpoint_matches_routing_pattern(self):
        cls = self.parse_class()
        member = find_member(cls, 'endpoint')
        self.assertIsNotNone(member, '`endpoint` field must be emitted from URL routing')
        self.assertEqual(member['initializer']['text'], '"/ws/scalar_list/"')
