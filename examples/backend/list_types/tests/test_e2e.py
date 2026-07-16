"""End-to-end browser test for the list_types example."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase


class ListTypesE2ETests(RxE2ETestCase):
    def test_mixed_list_renders_both_types_and_null_differs_from_empty(self):
        page = self.goto_demo('examples/list_types')

        mixed_items = page.locator('li')
        expect(mixed_items).to_have_count(3)
        expect(mixed_items.nth(0)).to_contain_text('number')
        expect(mixed_items.nth(0)).to_contain_text('1')
        expect(mixed_items.nth(1)).to_contain_text('string')
        expect(mixed_items.nth(1)).to_contain_text('two')

        page.get_by_role('button', name='Add text').click()
        expect(mixed_items).to_have_count(4)
        expect(mixed_items.nth(3)).to_contain_text('word')

        optional_field = self.field('Optional numbers (list[int] | None)')
        expect(optional_field).to_have_text('null (not set)')

        page.get_by_role('button', name='Set numbers').click()
        expect(optional_field).to_have_text('1, 2, 3')

        page.get_by_role('button', name='Clear (empty list)').click()
        expect(optional_field).to_have_text('empty list')

        page.get_by_role('button', name='Unset (null)').click()
        expect(optional_field).to_have_text('null (not set)')
