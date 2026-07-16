"""Integration tests for the static-queryset-lists tier's example app.

`StaticQuerysetChannel.tasks` binds `Task.objects.filter(status='open')
.order_by('-priority', 'id')` once in `on_connect` -- the entire developer
surface (ADR-0019). Everything below is client-derived: membership,
ordering, and the null/[]/T[] state progression.
"""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase

from static_queryset.models import Task


class StaticQuerysetIntegrationTests(RxIntegrationTestCase):
    app_label = 'static_queryset'
    channel = 'StaticQuerysetChannel'
    url = '/ws/static_queryset/'

    def setUp(self):
        super().setUp()
        Task.objects.all().delete()
        self.low = Task.objects.create(name='Low', status='open', priority=1)
        self.high = Task.objects.create(name='High', status='open', priority=5)
        self.closed = Task.objects.create(name='Closed', status='closed', priority=9)

    def test_snapshot_renders_open_tasks_ordered_by_priority_desc(self):
        self.wait_for('channel.tasks !== null')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['High', 'Low'])

    def test_toggle_status_flips_a_member_out_of_the_list(self):
        self.wait_for('channel.tasks !== null')
        self.eval(f'await channel.toggle_status({self.high.id})')
        self.wait_for('channel.tasks.length === 1')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['Low'])

    def test_bump_priority_resorts_the_list(self):
        self.wait_for('channel.tasks !== null')
        self.eval(f'await channel.bump_priority({self.low.id}, 10)')
        self.wait_for('channel.tasks[0].name === "Low"')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['Low', 'High'])

    def test_delete_removes_the_row(self):
        self.wait_for('channel.tasks !== null')
        self.eval(f'await channel.delete_task({self.low.id})')
        self.wait_for('channel.tasks.length === 1')
        names = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(names, ['High'])

    def test_empty_snapshot_is_empty_array_not_null(self):
        Task.objects.filter(status='open').delete()
        self.wait_for('channel.tasks !== null')
        tasks = self.get_result('channel.tasks')
        self.assertEqual(tasks, [])

    def test_new_row_does_not_appear_until_rebind(self):
        self.wait_for('channel.tasks !== null')
        # add_task creates the row through an action on the *same* live
        # connection -- the static tier still does not deliver it.
        self.eval('await channel.add_task("New", 100)')
        unchanged = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(unchanged, ['High', 'Low'])

        self.eval('await channel.rebind()')
        self.wait_for('channel.tasks.length === 3')
        rebound = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(rebound, ['New', 'High', 'Low'])
