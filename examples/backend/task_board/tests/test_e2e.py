"""End-to-end browser tests for the routed-list-delivery example
(routed-list-delivery task 5.2): a created row appears live at its ordered
position, a dimension move removes the row, and a residual flip still
toggles membership -- all through the same connected browser page, no
rebind action anywhere in this example.
"""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase

from task_board.models import Project, Task


class TaskBoardE2ETests(RxE2ETestCase):
    def setUp(self):
        # Seed before Playwright's sync_api attaches to this thread's event
        # loop (see reactive_model/static_queryset's e2e tests): afterwards
        # Django blocks ORM calls as SynchronousOnlyOperation.
        #
        # The demo hardcodes its two boards to project_id 1 and 2. `Task`
        # tests: `TransactionTestCase` flushes every table between tests
        # (needed so the live-server subprocess sees committed rows), which
        # also clears the migration-seeded `Project` rows -- harmless before
        # `project` was a real `ForeignKey`, but a referential-integrity
        # requirement now, so both boards' Project rows are re-seeded here
        # too, not just Task.
        Project.objects.get_or_create(id=1, defaults={'name': 'Website Redesign'})
        Project.objects.get_or_create(id=2, defaults={'name': 'Mobile App'})
        Task.objects.all().delete()
        self.low = Task.objects.create(id=501, name='Low task', status='open', priority=1, project_id=1)
        self.high = Task.objects.create(id=502, name='High task', status='open', priority=5, project_id=1)
        super().setUp()

    def test_snapshot_renders_the_connected_projects_open_tasks(self):
        page = self.goto_demo('examples/task_board')

        board = page.get_by_test_id('board-1')
        expect(board.get_by_test_id(f'task-{self.high.id}')).to_be_visible()
        expect(board.get_by_test_id(f'task-{self.low.id}')).to_be_visible()

    def test_created_row_appears_live_at_its_ordered_position(self):
        page = self.goto_demo('examples/task_board')
        board = page.get_by_test_id('board-1')

        board.locator('input#task-board-new-task-name-1').fill('Top priority')
        board.locator('input#task-board-new-task-priority-1').fill('100')
        board.get_by_role('button', name='Add task').click()

        rows = board.locator('[data-testid^="task-"]')
        expect(rows.first).to_contain_text('Top priority')

    def test_dimension_move_removes_the_row_from_this_board_live(self):
        page = self.goto_demo('examples/task_board')
        board1 = page.get_by_test_id('board-1')

        board1.get_by_test_id(f'task-{self.high.id}').get_by_role(
            'button', name='Move to Project 2',
        ).click()

        expect(board1.get_by_test_id(f'task-{self.high.id}')).to_have_count(0)

        board2 = page.get_by_test_id('board-2')
        expect(board2.get_by_test_id(f'task-{self.high.id}')).to_be_visible()

    def test_residual_flip_still_toggles_membership(self):
        page = self.goto_demo('examples/task_board')
        board = page.get_by_test_id('board-1')

        board.get_by_test_id(f'task-{self.low.id}').get_by_role(
            'button', name='Close',
        ).click()

        expect(board.get_by_test_id(f'task-{self.low.id}')).to_have_count(0)
