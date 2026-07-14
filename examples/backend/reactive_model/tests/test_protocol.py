"""Protocol-level test for the reactive_model channel.

Verifies that the rx update for the ``task`` field arrives as two layered
frames -- one per instance type, parent-before-child (ADR-0016) -- rather
than a single frame carrying both the ``Task`` and ``Project`` layers.
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
        # One frame per layer, parent-before-child: the task frame precedes
        # the project frame it references.
        self.assertEqual(len(rx_frames), 2)
        task_frame, project_frame = [frame['data']['v'] for frame in rx_frames]

        self.assertIsInstance(task_frame, list)
        self.assertEqual(len(task_frame), 1)
        self.assertIsInstance(project_frame, list)
        self.assertEqual(len(project_frame), 1)

        task_layer = task_frame[0]
        project_layer = project_frame[0]
        self.assertEqual(task_layer['_type'], 'reactive_model.serializers.TaskSerializer')
        self.assertEqual(project_layer['_type'], 'reactive_model.serializers.ProjectSerializer')
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
