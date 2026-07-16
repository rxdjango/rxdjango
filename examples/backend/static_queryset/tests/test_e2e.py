"""End-to-end browser tests for the static-queryset-lists example
(static-queryset-lists task 6.2): snapshot render, a live update to a
member, a residual flip out and back in, delete, an ordering change, and
the empty-vs-loading distinction.
"""

from __future__ import annotations

import threading

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase

from static_queryset.models import Task


def _reopen(task_id: int) -> None:
    # Run on a fresh thread: once Playwright's sync API is attached, Django
    # treats any ORM call on *this* thread as an async context and raises
    # SynchronousOnlyOperation (see setUp's docstring note) -- a thread with
    # no event loop of its own sidesteps that check.
    task = Task.objects.get(id=task_id)
    task.status = 'open'
    task.save()


class StaticQuerysetE2ETests(RxE2ETestCase):
    def setUp(self):
        # Seed before Playwright's sync_api attaches to this thread's event
        # loop (see reactive_model's e2e test): afterwards Django blocks ORM
        # calls as SynchronousOnlyOperation. Migration-seeded rows do not
        # survive the per-test flush, so this recreates them explicitly.
        Task.objects.all().delete()
        self.low = Task.objects.create(id=101, name='Low task', status='open', priority=1)
        self.high = Task.objects.create(id=102, name='High task', status='open', priority=5)
        self.closed = Task.objects.create(id=103, name='Closed task', status='closed', priority=9)
        super().setUp()

    def test_snapshot_renders_open_tasks_only(self):
        page = self.goto_demo('examples/static_queryset')

        expect(page.get_by_test_id(f'task-{self.high.id}')).to_be_visible()
        expect(page.get_by_test_id(f'task-{self.low.id}')).to_be_visible()
        expect(page.get_by_test_id(f'task-{self.closed.id}')).to_have_count(0)

    def test_live_update_to_a_member_changes_its_priority(self):
        page = self.goto_demo('examples/static_queryset')
        row = page.get_by_test_id(f'task-{self.low.id}')

        expect(row).to_contain_text('priority 1')
        row.get_by_role('button', name='+1 priority').click()
        expect(row).to_contain_text('priority 2')

    def test_residual_flip_out_and_back_in(self):
        page = self.goto_demo('examples/static_queryset')
        row = page.get_by_test_id(f'task-{self.low.id}')

        row.get_by_role('button', name='Close').click()
        expect(page.get_by_test_id(f'task-{self.low.id}')).to_have_count(0)

        # Flipped back to open from outside the UI entirely (a background
        # process, say) -- the client must pick this up with no reload.
        thread = threading.Thread(target=_reopen, args=(self.low.id,))
        thread.start()
        thread.join()

        expect(page.get_by_test_id(f'task-{self.low.id}')).to_be_visible()

    def test_delete_removes_the_row(self):
        page = self.goto_demo('examples/static_queryset')
        row = page.get_by_test_id(f'task-{self.high.id}')

        row.get_by_role('button', name='Delete').click()

        expect(page.get_by_test_id(f'task-{self.high.id}')).to_have_count(0)

    def test_ordering_change_resorts(self):
        page = self.goto_demo('examples/static_queryset')
        rows = page.locator('[data-testid^="task-"]')

        expect(rows.first).to_contain_text('High task')

        low_row = page.get_by_test_id(f'task-{self.low.id}')
        for _ in range(5):
            low_row.get_by_role('button', name='+1 priority').click()

        expect(rows.first).to_contain_text('Low task')

    def test_empty_list_renders_empty_state_not_loading(self):
        page = self.goto_demo('examples/static_queryset')

        page.get_by_test_id(f'task-{self.high.id}').get_by_role(
            'button', name='Close',
        ).click()
        page.get_by_test_id(f'task-{self.low.id}').get_by_role(
            'button', name='Close',
        ).click()

        expect(page.get_by_test_id('empty-state')).to_be_visible()
        expect(page.get_by_text('Connecting...')).to_have_count(0)
