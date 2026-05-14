"""End-to-end browser test for the counter example."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase


class CounterE2ETests(RxE2ETestCase):
    def test_increment_button_updates_counter_value(self):
        page = self.goto_demo('examples/counter')
        counter = page.locator('dt:has-text("Counter value") + dd')

        expect(counter).to_have_text('0')

        page.get_by_role('button', name='Increment').click()

        expect(counter).to_have_text('1')
