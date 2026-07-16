"""End-to-end integration test for the list_types channel: union element
types and the optional-list None-vs-empty distinction (ADR-0017)."""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase


class ListTypesIntegrationTests(RxIntegrationTestCase):

    app_label = 'list_types'
    channel = 'ListTypesChannel'
    url = '/ws/list_types/'

    def test_mixed_list_holds_both_element_types(self):
        mixed = self.get_result('channel.mixed')
        self.assertEqual(mixed, [1, 'two', 3])

    def test_adding_text_and_number_to_mixed_list(self):
        self.eval("await channel.add_text('extra')")
        self.wait_for('channel.mixed.length === 4')
        self.eval('await channel.add_number(42)')
        self.wait_for('channel.mixed.length === 5')
        mixed = self.get_result('channel.mixed')
        self.assertEqual(mixed, [1, 'two', 3, 'extra', 42])

    def test_optional_numbers_starts_null(self):
        value = self.get_result('channel.optional_numbers')
        self.assertIsNone(value)

    def test_set_then_clear_then_unset_are_distinct_states(self):
        self.eval('await channel.set_numbers([1, 2, 3])')
        self.wait_for('channel.optional_numbers !== null')
        first = self.get_result('channel.optional_numbers')
        self.assertEqual(first, [1, 2, 3])

        self.eval('await channel.clear_numbers()')
        self.wait_for('channel.optional_numbers !== null && channel.optional_numbers.length === 0')
        second = self.get_result('channel.optional_numbers')
        self.assertEqual(second, [])

        self.eval('await channel.set_numbers([9])')
        self.wait_for('channel.optional_numbers !== null')
        self.eval('await channel.unset_numbers()')
        self.wait_for('channel.optional_numbers === null')
        third = self.get_result('channel.optional_numbers')
        self.assertIsNone(third)

    def test_append_number_mutates_in_place_once_set(self):
        self.eval('await channel.set_numbers([1])')
        self.wait_for('channel.optional_numbers !== null')
        self.eval('await channel.append_number(2)')
        self.wait_for('channel.optional_numbers.length === 2')
        value = self.get_result('channel.optional_numbers')
        self.assertEqual(value, [1, 2])
