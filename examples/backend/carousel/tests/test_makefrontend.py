from rxdjango.testing import FrontendTestCase
from rxdjango.testing.ts_ast import find_member


class MakeFrontendCarouselTests(FrontendTestCase):
    app_name = 'carousel'
    channel_file = 'carousel.channels.ts'
    class_name = 'CarouselChannel'

    def test_fruit_field_declared_with_default(self):
        cls = self.parse_class()
        member = find_member(cls, 'fruit')
        self.assertIsNotNone(member, '`fruit` property not found on CarouselChannel')
        self.assertEqual(member['kind'], 'property')
        self.assertEqual(member['type'], 'string')
        self.assertIsNotNone(
            member['initializer'],
            '`fruit` must have a default value',
        )
        self.assertEqual(member['initializer']['text'], "'banana'")

    def test_fruits_constant_not_emitted(self):
        cls = self.parse_class()
        self.assertIsNone(
            find_member(cls, 'FRUITS'),
            '`FRUITS` is a Python-only helper and must not appear on CarouselChannel',
        )
