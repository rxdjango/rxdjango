"""Protocol-level test for the reactive_model channel.

Verifies that the rx update for the ``task`` field carries the flat
``[Task, Project]`` layer pair produced by the backend ``StateModel``.
"""

from __future__ import annotations

from testing.integration import RxProtocolTestCase

from reactive_model.models import Project, Task


class ReactiveModelProtocolTests(RxProtocolTestCase):
    app_label = 'reactive_model'
    channel = 'ReactiveModelChannel'
    url = '/ws/reactive_model/'

    def setUp(self):
        super().setUp()
        # Seed the sample instances the channel resolves by id in on_connect;
        # the migration-seeded rows do not survive the per-test flush.
        project, _ = Project.objects.update_or_create(
            id=1, defaults={'name': 'My Project'},
        )
        Task.objects.update_or_create(
            id=1, defaults={'name': 'First Task', 'project': project},
        )

    def test_initial_push_carries_two_flat_dicts(self):
        self.wait_for('channel.task !== null')
        self.get_trace()

        rx_frames = [
            entry for entry in self.last_trace
            if entry['from'] == 'server'
            and isinstance(entry['data'], dict)
            and entry['data'].get('t') == 'rx'
            and entry['data'].get('f') == 'task'
        ]
        self.assertEqual(len(rx_frames), 1)
        payload = rx_frames[0]['data']['v']

        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 2)

        by_type = {entry['_type']: entry for entry in payload}
        self.assertIn('reactive_model.serializers.TaskSerializer', by_type)
        self.assertIn('reactive_model.serializers.ProjectSerializer', by_type)

        task_layer = by_type['reactive_model.serializers.TaskSerializer']
        project_layer = by_type['reactive_model.serializers.ProjectSerializer']
        self.assertEqual(task_layer['name'], 'First Task')
        self.assertEqual(task_layer['project'], project_layer['id'])
        self.assertEqual(project_layer['name'], 'My Project')

    def test_modify_project_sends_update_frame(self):
        self.wait_for('channel.task !== null')

        self.eval('await channel.modify_project("New Name", 0)')
        self.wait_for('channel.task.project.name !== "My Project"')
        self.get_trace()

        rx_frames = [
            entry for entry in self.last_trace
            if entry['from'] == 'server'
            and isinstance(entry['data'], dict)
            and entry['data'].get('t') == 'rx'
            and entry['data'].get('f') == 'task'
        ]
        update_frame = next(
            (f for f in rx_frames if any(
                isinstance(f['data']['v'], list)
                and any(
                    layer.get('name') == 'New Name'
                    for layer in f['data']['v']
                )
                for _ in [None]
            )),
            None,
        )
        self.assertIsNotNone(update_frame, 'expected an rx frame with updated project name')
