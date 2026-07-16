from rxdjango.testing import FrontendTestCase
from rxdjango.testing.ts_ast import find_member


class MakeFrontendStreamingListTests(FrontendTestCase):
    app_name = 'streaming_list'
    channel_file = 'streaming_list.channels.ts'
    class_name = 'StreamingListChannel'

    def test_emits_context_channel_class(self):
        cls = self.parse_class()
        self.assertTrue(cls['exported'], 'StreamingListChannel must be exported')
        self.assertIn(
            {'kind': 'extends', 'name': 'ContextChannel'},
            cls['heritage'],
            'StreamingListChannel must extend ContextChannel',
        )

    def test_items_field_starts_empty(self):
        cls = self.parse_class()
        member = find_member(cls, 'items')
        self.assertIsNotNone(member, '`items` property not found')
        self.assertEqual(member['type'], 'number[]')
        self.assertEqual(member['initializer']['text'], '[]')

    def test_pause_and_resume_actions_declared(self):
        cls = self.parse_class()
        self.assertIsNotNone(find_member(cls, 'pause'))
        self.assertIsNotNone(find_member(cls, 'resume'))
        self.assertIsNotNone(find_member(cls, 'reset'))
