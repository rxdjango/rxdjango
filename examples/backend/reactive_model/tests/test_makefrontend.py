import os
import tempfile

from django.test import TestCase, override_settings
from rxdjango.sdk import make_sdk

from reactive_model.channels import ReactiveModelChannel
from reactive_model.serializers import TaskSerializer, ProjectSerializer


class ReactiveModelMakeFrontendTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_state_model_is_built_for_nested_serializer(self):
        rx_field = ReactiveModelChannel._rx_fields['task']
        state_model = rx_field.state_model
        self.assertIsNotNone(state_model)
        self.assertEqual(
            state_model.instance_type,
            'reactive_model.serializers.TaskSerializer',
        )
        self.assertIn('project', state_model.children)
        self.assertEqual(
            state_model.children['project'].instance_type,
            'reactive_model.serializers.ProjectSerializer',
        )

    def test_frontend_model_describes_relations(self):
        state_model = ReactiveModelChannel._rx_fields['task'].state_model
        self.assertEqual(
            state_model.frontend_model(),
            {
                'reactive_model.serializers.TaskSerializer': {
                    'project': 'reactive_model.serializers.ProjectSerializer',
                },
                'reactive_model.serializers.ProjectSerializer': {},
            },
        )

    def test_generated_channel_emits_model_field_map(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name,
            'reactive_model',
            'reactive_model.channels.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('_modelFields', content)
        self.assertIn('reactive_model.serializers.TaskSerializer', content)
        self.assertIn('reactive_model.serializers.ProjectSerializer', content)
        self.assertIn('"project": "reactive_model.serializers.ProjectSerializer"', content)

    def test_generated_models_file_has_both_interfaces(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name,
            'reactive_model',
            'reactive_model.models.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('export interface Task {', content)
        self.assertIn('export interface Project {', content)
        self.assertIn('project: Project', content)
