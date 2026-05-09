from rxdjango.testing import FrontendTestCase
from rxdjango.testing.ts_ast import find_member


class MakeFrontendCounterTests(FrontendTestCase):
    app_name = 'counter'
    channel_file = 'counter.channels.ts'
    class_name = 'CounterChannel'

    def test_emits_context_channel_class(self):
        cls = self.parse_class()
        self.assertTrue(cls['exported'], 'CounterChannel must be exported')
        self.assertIn(
            {'kind': 'extends', 'name': 'ContextChannel'},
            cls['heritage'],
            'CounterChannel must extend ContextChannel',
        )

    def test_counter_field_declared_with_default(self):
        cls = self.parse_class()
        member = find_member(cls, 'counter')
        self.assertIsNotNone(member, '`counter` property not found on CounterChannel')
        self.assertEqual(member['kind'], 'property')
        self.assertEqual(member['type'], 'number')
        self.assertIsNotNone(
            member['initializer'],
            '`counter` must have a default value',
        )
        self.assertEqual(member['initializer']['text'], '0')
