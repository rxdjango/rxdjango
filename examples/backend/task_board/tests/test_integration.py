"""Integration tests for the routed-list-delivery example app
(routed-list-delivery tasks 5.1/5.3): `TaskBoardChannel.tasks` declares
`routing='project_id'`, so a task's creation and any dimension move
deliver live -- no rebind, unlike `static_list`.
"""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase

from task_board.models import Project, Task


class TaskBoardIntegrationTests(RxIntegrationTestCase):
    app_label = 'task_board'
    channel = 'TaskBoardChannel'
    url = '/ws/task_board/'

    def setUp(self):
        super().setUp()
        Task.objects.all().delete()
        Project.objects.all().delete()
        self.p1 = Project.objects.create(id=101, name='P1')
        self.p2 = Project.objects.create(id=102, name='P2')
        self.low = Task.objects.create(name='Low', status='open', priority=1, project_id=101)
        self.high = Task.objects.create(name='High', status='open', priority=5, project_id=101)
        self.other = Task.objects.create(name='Other', status='open', priority=9, project_id=102)

    def _select(self, project_id):
        self.eval(f'await channel.select_project({project_id})')
        self.wait_for('channel.tasks !== null')

    def test_snapshot_renders_only_the_selected_projects_open_tasks(self):
        self._select(101)
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['High', 'Low'])

    def test_creation_appears_live_with_no_rebind(self):
        self._select(101)
        self.eval('await channel.add_task("New", 100)')
        self.wait_for('channel.tasks.length === 3')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['New', 'High', 'Low'])

    def test_dimension_move_removes_the_row_live(self):
        self._select(101)
        self.eval(f'await channel.move_task({self.high.id}, 102)')
        self.wait_for('channel.tasks.length === 1')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['Low'])

    def test_residual_flip_still_toggles_membership(self):
        self._select(101)
        self.eval(f'await channel.toggle_status({self.high.id})')
        self.wait_for('channel.tasks.length === 1')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['Low'])
