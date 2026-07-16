"""End-to-end browser test for the streaming_list example: items arrive on
their own, without any page reload or user interaction."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase


class StreamingListE2ETests(RxE2ETestCase):
    def test_items_arrive_one_at_a_time_without_reload(self):
        page = self.goto_demo('examples/streaming_list')
        items = page.locator('li')

        expect(items).to_have_count(0)

        # Ticks arrive on their own — no click, no reload — so just wait
        # until at least two have landed. (Exact intermediate counts like
        # "1" aren't reliably observable: assertion polling can land between
        # ticks and skip straight past a given count.)
        page.wait_for_function(
            'document.querySelectorAll("li").length >= 2', timeout=5000,
        )
        self.assertGreaterEqual(items.count(), 2)

        page.get_by_role('button', name='Pause').click()
        page.get_by_role('button', name='Reset').click()
        expect(items).to_have_count(0)
