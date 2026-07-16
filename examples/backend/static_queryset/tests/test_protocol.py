"""Protocol-level test for the static-queryset-lists example channel.

Verifies the `q` bind descriptor's exact wire shape on the snapshot anchor
frame (ADR-0019 D1, `wire-protocol`), and that an ordinary residual-flip
update carries no `q` and no `o` (model fields never use the list-delta
slot -- that is exclusive to `rx[list[S]]` scalar fields, ADR-0017).
"""

from __future__ import annotations

from testing.integration import RxProtocolTestCase

from static_queryset.models import Task


class StaticQuerysetProtocolTests(RxProtocolTestCase):
    app_label = 'static_queryset'
    channel = 'StaticQuerysetChannel'
    url = '/ws/static_queryset/'

    def setUp(self):
        super().setUp()
        Task.objects.all().delete()
        self.low = Task.objects.create(name='Low', status='open', priority=1)
        self.high = Task.objects.create(name='High', status='open', priority=5)

    def _rx_frames_for(self, field):
        return [
            entry['data'] for entry in self.last_trace
            if entry['from'] == 'server'
            and isinstance(entry['data'], dict)
            and entry['data'].get('t') == 'rx'
            and entry['data'].get('f') == field
        ]

    def test_snapshot_anchor_frame_carries_the_bind_descriptor(self):
        self.wait_for('channel.tasks !== null')
        self.get_trace()

        frames = self._rx_frames_for('tasks')
        self.assertEqual(len(frames), 1)
        anchor = frames[0]

        self.assertEqual(anchor['q'], {
            'w': [['status', 'exact', 'open']],
            's': ['-priority', 'id'],
        })
        self.assertNotIn('o', anchor)
        self.assertEqual(len(anchor['v']), 2)

    def test_residual_flip_frame_carries_no_descriptor(self):
        self.wait_for('channel.tasks !== null')
        self.eval(f'await channel.toggle_status({self.high.id})')
        self.wait_for('channel.tasks.length === 1')
        self.get_trace()

        frames = self._rx_frames_for('tasks')
        update_frame = frames[-1]

        self.assertNotIn('q', update_frame)
        self.assertNotIn('o', update_frame)
        self.assertEqual(update_frame['v'][0]['status'], 'closed')

    def test_rebind_emits_a_fresh_descriptor(self):
        self.wait_for('channel.tasks !== null')
        self.eval('await channel.rebind()')
        self.wait_for('channel.tasks.length === 2')
        self.get_trace()

        frames = self._rx_frames_for('tasks')
        rebind_frame = [f for f in frames if 'q' in f][-1]

        self.assertEqual(rebind_frame['q'], {
            'w': [['status', 'exact', 'open']],
            's': ['-priority', 'id'],
        })
