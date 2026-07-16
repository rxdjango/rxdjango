import os
import tempfile

from django.test import TestCase, override_settings
from rxdjango.sdk import make_sdk

from task_board.channels import TaskBoardChannel


class TaskBoardMakeFrontendTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_state_model_is_built_for_the_many_true_field(self):
        rx_field = TaskBoardChannel._rx_fields['tasks']
        state_model = rx_field.state_model
        self.assertIsNotNone(state_model)
        self.assertTrue(rx_field.many)
        self.assertEqual(
            state_model.instance_type,
            'task_board.serializers.TaskSerializer',
        )

    def test_field_declares_a_column_router(self):
        from rxdjango_model.routing import ColumnRouter

        rx_field = TaskBoardChannel._rx_fields['tasks']
        self.assertIsInstance(rx_field.routing, ColumnRouter)
        self.assertEqual(rx_field.routing.column, 'project_id')

    def test_generated_channel_declares_an_array_property(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name, 'task_board', 'task_board.channels.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('tasks: Task[] | null = null;', content)
        self.assertIn("import type { Task } from './task_board.models';", content)
        self.assertIn('select_project', content)
