from testing.integration import RxIntegrationTestCase

from reactive_model.models import Project, Task


class ReactiveModelIntegrationTests(RxIntegrationTestCase):
    app_label = 'reactive_model'
    channel = 'ReactiveModelChannel'
    url = '/ws/reactive_model/'

    def test_task_and_project_are_pushed_on_connect(self):
        self.wait_for('channel.task !== null')
        result = self.get_result('{ name: channel.task.name, project: channel.task.project.name }')

        self.assertEqual(result['name'], 'First Task')
        self.assertEqual(result['project'], 'My Project')

    def test_modify_project_updates_project_name_reactively(self):
        self.wait_for('channel.task !== null')
        initial = self.get_result('channel.task.project.name')
        self.assertEqual(initial, 'My Project')

        self.eval('await channel.modify_project("Updated Project", 0)')
        self.wait_for('channel.task.project.name !== "My Project"')
        updated = self.get_result('channel.task.project.name')

        self.assertEqual(updated, 'Updated Project')
