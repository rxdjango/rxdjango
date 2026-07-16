import os
import tempfile

from django.test import TestCase, override_settings
from rxdjango.sdk import make_sdk

from static_queryset.channels import StaticQuerysetChannel


class StaticQuerysetMakeFrontendTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_state_model_is_built_for_the_many_true_field(self):
        rx_field = StaticQuerysetChannel._rx_fields['tasks']
        state_model = rx_field.state_model
        self.assertIsNotNone(state_model)
        self.assertTrue(rx_field.many)
        self.assertEqual(
            state_model.instance_type,
            'static_queryset.serializers.TaskSerializer',
        )

    def test_generated_channel_declares_an_array_property(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name, 'static_queryset', 'static_queryset.channels.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('tasks: Task[] | null = null;', content)
        self.assertIn("import type { Task } from './static_queryset.models';", content)

    def test_generated_model_fields_marks_the_list_anchor(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name, 'static_queryset', 'static_queryset.channels.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('many?: boolean;', content)
        tasks_at = content.index('"tasks": {')
        model_at = content.index('model: {', tasks_at)
        self.assertLess(tasks_at, content.index('many: true,', tasks_at))
        self.assertLess(content.index('many: true,', tasks_at), model_at)

    def test_generated_models_file_has_no_unloaded_import(self):
        # A flat serializer (no nested relations) needs no `Unloaded` import.
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name, 'static_queryset', 'static_queryset.models.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('export interface Task {', content)
        self.assertIn('status: string;', content)
        self.assertNotIn('Unloaded', content)
