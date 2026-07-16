"""Protocol-level test for the routed-list-delivery example channel
(routed-list-delivery task 4.1): the `q` bind descriptor of a `routing=`
field carries `l: true` on the wire, and a live-creation merge frame still
carries no `q`/`o` -- it is an ordinary merge frame, tagged only by field
name.
"""

from __future__ import annotations

from testing.integration import RxProtocolTestCase

from task_board.models import Project, Task


class TaskBoardProtocolTests(RxProtocolTestCase):
    app_label = 'task_board'
    channel = 'TaskBoardChannel'
    url = '/ws/task_board/'

    def setUp(self):
        super().setUp()
        Task.objects.all().delete()
        Project.objects.all().delete()
        Project.objects.create(id=301, name='P1')
        self.low = Task.objects.create(name='Low', status='open', priority=1, project_id=301)

    def _rx_frames_for(self, field):
        return [
            entry['data'] for entry in self.last_trace
            if entry['from'] == 'server'
            and isinstance(entry['data'], dict)
            and entry['data'].get('t') == 'rx'
            and entry['data'].get('f') == field
        ]

    def test_snapshot_anchor_frame_carries_the_live_marker(self):
        self.eval('await channel.select_project(301)')
        self.wait_for('channel.tasks !== null')
        self.get_trace()

        frames = self._rx_frames_for('tasks')
        self.assertEqual(len(frames), 1)
        anchor = frames[0]

        self.assertEqual(
            anchor['q']['w'],
            [['project', 'exact', 301], ['status', 'exact', 'open']],
        )
        self.assertTrue(anchor['q']['l'])
        self.assertNotIn('o', anchor)

    def test_live_creation_frame_carries_no_descriptor(self):
        self.eval('await channel.select_project(301)')
        self.wait_for('channel.tasks !== null')
        self.eval('await channel.add_task("New", 5)')
        self.wait_for('channel.tasks.length === 2')
        self.get_trace()

        frames = self._rx_frames_for('tasks')
        creation_frame = [f for f in frames if f['v'] and f['v'][0].get('name') == 'New'][-1]

        self.assertNotIn('q', creation_frame)
        self.assertNotIn('o', creation_frame)
