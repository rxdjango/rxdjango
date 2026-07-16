"""End-to-end browser test for the scalar_list example."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase


class ScalarListE2ETests(RxE2ETestCase):
    def test_mutations_update_the_rendered_list_live_and_preserve_order(self):
        page = self.goto_demo('examples/scalar_list')
        items = page.locator('li')

        expect(items).to_have_count(3)
        expect(items.nth(0)).to_contain_text('apple')
        expect(items.nth(1)).to_contain_text('banana')
        expect(items.nth(2)).to_contain_text('cherry')

        page.get_by_label('New item').fill('date')
        page.get_by_role('button', name='Append').click()
        expect(items).to_have_count(4)
        expect(items.nth(3)).to_contain_text('date')

        page.get_by_role('button', name='Insert at start').click()
        expect(items).to_have_count(5)
        expect(items.nth(0)).to_contain_text('first')

        page.get_by_role('button', name='Pop last').click()
        expect(items).to_have_count(4)
        expect(items.nth(3)).to_contain_text('cherry')

        # Remove the second item ("apple") and confirm order shifts up.
        items.nth(1).get_by_role('button', name='Remove').click()
        expect(items).to_have_count(3)
        expect(items.nth(0)).to_contain_text('first')
        expect(items.nth(1)).to_contain_text('banana')
        expect(items.nth(2)).to_contain_text('cherry')

        page.get_by_role('button', name='Replace all').click()
        expect(items).to_have_count(3)
        expect(items.nth(0)).to_contain_text('reset')
        expect(items.nth(1)).to_contain_text('from')
        expect(items.nth(2)).to_contain_text('scratch')
