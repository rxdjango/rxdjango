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

    def test_increment_action_declared(self):
        cls = self.parse_class()
        member = find_member(cls, 'increment')
        self.assertIsNotNone(member, '`increment` action not found on CounterChannel')
        self.assertEqual(member['kind'], 'method')
        self.assertTrue(member['async'], 'action must be emitted as async')
        self.assertEqual(member['params'], [])

    def test_endpoint_matches_routing_pattern(self):
        cls = self.parse_class()
        member = find_member(cls, 'endpoint')
        self.assertIsNotNone(member, '`endpoint` field must be emitted from URL routing')
        self.assertEqual(member['type'], 'string')
        self.assertIsNotNone(member['initializer'])
        self.assertEqual(member['initializer']['text'], '"/ws/counter/"')

    def test_base_url_uses_socket_url_const(self):
        cls = self.parse_class()
        member = find_member(cls, 'baseURL')
        self.assertIsNotNone(member, '`baseURL` field must be emitted')
        self.assertEqual(member['type'], 'string')
        self.assertIsNotNone(member['initializer'])
        self.assertEqual(member['initializer']['text'], 'SOCKET_URL')
