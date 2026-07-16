"""Protocol-level test for the scalar_list channel — the o-slot wire shape
(ADR-0017) for a plain rx[list[str]] field."""

from __future__ import annotations

from testing.integration import RxProtocolTestCase


class ScalarListProtocolTests(RxProtocolTestCase):

    app_label = 'scalar_list'
    channel = 'ScalarListChannel'
    url = '/ws/scalar_list/'

    def test_append_sends_an_insert_op_frame(self):
        self.eval("await channel.append('date')")
        self.wait_for('channel.items.length === 4')
        trace = self.get_trace()

        server_frames = [entry['data'] for entry in trace if entry['from'] == 'server']
        assert {'t': 'rx', 'f': 'items', 'o': 'i', 'v': [3, 'date']} in server_frames

    def test_replace_all_sends_a_plain_frame_with_no_o_key(self):
        self.eval('await channel.replace_all()')
        self.wait_for("channel.items[0] === 'reset'")
        trace = self.get_trace()

        server_frames = [entry['data'] for entry in trace if entry['from'] == 'server']
        replace_frame = next(f for f in server_frames if f.get('t') == 'rx' and f.get('f') == 'items')
        assert replace_frame == {
            't': 'rx', 'f': 'items', 'v': ['reset', 'from', 'scratch'],
        }
        assert 'o' not in replace_frame
