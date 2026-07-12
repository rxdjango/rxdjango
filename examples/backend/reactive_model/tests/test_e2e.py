"""End-to-end browser test for the reactive_model example."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase

from reactive_model.models import Project, Task


class ReactiveModelE2ETests(RxE2ETestCase):
    def setUp(self):
        # Seed the test database before super().setUp() starts Playwright;
        # once Playwright's sync_api event loop is attached to this thread,
        # Django blocks ORM calls as ``SynchronousOnlyOperation``.
        project, _ = Project.objects.update_or_create(
            id=1, defaults={'name': 'My Project'},
        )
        Task.objects.update_or_create(
            id=1, defaults={'name': 'First Task', 'project': project},
        )
        super().setUp()

    def test_task_and_project_render_on_connect(self):
        page = self.goto_demo('examples/reactive_model')

        expect(page.get_by_text('First Task')).to_be_visible()
        expect(page.get_by_text('My Project')).to_be_visible()

    def test_modify_project_updates_project_name(self):
        page = self.goto_demo('examples/reactive_model')

        expect(page.get_by_text('My Project')).to_be_visible()

        page.get_by_label('New project name').fill('Renamed Project')
        page.get_by_label('Delay (seconds)').fill('0')
        page.get_by_role('button', name='Modify').click()

        expect(page.get_by_text('Renamed Project')).to_be_visible()
