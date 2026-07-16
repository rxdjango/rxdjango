"""Integration test for the streaming_list channel: background-timer
appends to rx[list[int]] with no client action driving them (ADR-0017)."""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase


class StreamingListIntegrationTests(RxIntegrationTestCase):

    app_label = 'streaming_list'
    channel = 'StreamingListChannel'
    url = '/ws/streaming_list/'

    def test_items_arrive_on_their_own_without_any_action(self):
        # No `eval` of an action call precedes this — the growth is entirely
        # server-driven.
        self.wait_for('channel.items.length >= 2', timeout=5000)
        items = self.get_result('channel.items')
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(items, list(range(1, len(items) + 1)))

    def test_pause_stops_growth_and_resume_continues_it(self):
        self.eval('await channel.pause()')
        self.wait_for('channel.ticking === false')
        self.eval(
            'const lenAfterPause = channel.items.length;'
            ' await new Promise((r) => setTimeout(r, 700));'
            ' const lenStillPaused = channel.items.length;'
        )
        self.eval('await channel.resume()')
        self.wait_for('channel.items.length > lenStillPaused', timeout=5000)
        result = self.get_result('lenStillPaused === lenAfterPause')
        self.assertTrue(result)

    def test_reset_clears_the_list(self):
        self.wait_for('channel.items.length >= 1', timeout=5000)
        self.eval('await channel.reset()')
        self.wait_for('channel.items.length === 0')
        items = self.get_result('channel.items')
        self.assertEqual(items, [])
