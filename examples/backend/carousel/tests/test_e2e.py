"""End-to-end browser test for the carousel example."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase


class CarouselE2ETests(RxE2ETestCase):
    def test_next_button_rotates_visible_fields(self):
        page = self.goto_demo('examples/carousel')

        expect(self.field('Selected')).to_have_text('0')
        expect(self.field('Fruit')).to_have_text('banana')
        expect(self.field('First letter')).to_have_text('b')

        page.get_by_role('button', name='Next').click()

        expect(self.field('Selected')).to_have_text('1')
        expect(self.field('Fruit')).to_have_text('apple')
        expect(self.field('First letter')).to_have_text('a')
