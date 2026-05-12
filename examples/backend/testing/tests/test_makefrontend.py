from rxdjango.testing import FrontendTestCase
from rxdjango.testing.ts_ast import find_member


class MakeFrontendTestingTests(FrontendTestCase):
    app_name = 'testing'
    channel_file = 'testing.channels.ts'
    class_name = 'TestingChannel'

    def setUp(self):
        super().setUp()
        self._cls = self.parse_class()

    def test_int_with_default(self):
        m = find_member(self._cls, 'int_with_default')
        self.assertIsNotNone(m)
        self.assertEqual(m['type'], 'number')
        self.assertIsNotNone(m['initializer'], 'expected initializer for int_with_default')
        self.assertEqual(m['initializer']['text'], '1')

    def test_int_optional_initialized_to_null(self):
        m = find_member(self._cls, 'int_optional')
        self.assertIsNotNone(m)
        self.assertEqual(m['type'], 'number | null')
        self.assertIsNotNone(
            m['initializer'],
            'optional field without Python default must be initialized to null',
        )
        self.assertEqual(m['initializer']['text'], 'null')

    def test_str_with_default(self):
        m = find_member(self._cls, 'str_with_default')
        self.assertIsNotNone(m)
        self.assertEqual(m['type'], 'string')
        self.assertIsNotNone(m['initializer'], 'expected initializer for str_with_default')
        self.assertEqual(m['initializer']['text'], "'hello'")

    def test_str_optional_initialized_to_null(self):
        m = find_member(self._cls, 'str_optional')
        self.assertIsNotNone(m)
        self.assertEqual(m['type'], 'string | null')
        self.assertIsNotNone(
            m['initializer'],
            'optional field without Python default must be initialized to null',
        )
        self.assertEqual(m['initializer']['text'], 'null')

    def test_action_method_declared_with_typed_params(self):
        m = find_member(self._cls, 'do_action')
        self.assertIsNotNone(m, 'action method `do_action` not found')
        self.assertEqual(m['kind'], 'method')
        self.assertTrue(m['async'], 'action must be emitted as async')
        self.assertEqual(
            m['params'],
            [
                {'name': 'count', 'type': 'number'},
                {'name': 'label', 'type': 'string'},
            ],
        )

    def test_inert_method_not_emitted(self):
        m = find_member(self._cls, 'inert')
        self.assertIsNone(m, 'non-action method must not be emitted in TS')
