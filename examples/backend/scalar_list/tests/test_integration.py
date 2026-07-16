"""End-to-end integration test for the scalar_list channel.

Drives ScalarListChannel from a real generated TS client over a live
websocket, exercising every CRUD action.
"""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase


class ScalarListIntegrationTests(RxIntegrationTestCase):

    app_label = 'scalar_list'
    channel = 'ScalarListChannel'
    url = '/ws/scalar_list/'

    def test_append_adds_to_the_end(self):
        self.eval("await channel.append('date')")
        self.wait_for('channel.items.length === 4')
        items = self.get_result('channel.items')
        self.assertEqual(items, ['apple', 'banana', 'cherry', 'date'])

    def test_insert_and_set_and_remove_and_pop(self):
        self.eval("await channel.insert(0, 'aardvark')")
        self.wait_for("channel.items[0] === 'aardvark'")
        self.eval("await channel.set_at(1, 'AAPPLE')")
        self.wait_for("channel.items[1] === 'AAPPLE'")
        self.eval('await channel.remove_at(2)')
        self.wait_for('channel.items.length === 3')
        self.eval('await channel.pop()')
        self.wait_for('channel.items.length === 2')
        items = self.get_result('channel.items')
        self.assertEqual(items, ['aardvark', 'AAPPLE'])

    def test_replace_all_resets_the_list(self):
        self.eval('await channel.replace_all()')
        self.wait_for("channel.items[0] === 'reset'")
        items = self.get_result('channel.items')
        self.assertEqual(items, ['reset', 'from', 'scratch'])
