import os
import tempfile

from django.test import TestCase, override_settings
from rxdjango.sdk import make_sdk

from nested_model.channels import NestedModelChannel
from nested_model.serializers import UserSerializer, CompanySerializer


class NestedModelMakeFrontendTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_state_model_is_built_for_nested_serializer(self):
        rx_field = NestedModelChannel._rx_fields['user']
        state_model = rx_field.state_model
        self.assertIsNotNone(state_model)
        self.assertEqual(
            state_model.instance_type,
            'nested_model.serializers.UserSerializer',
        )
        self.assertIn('company', state_model.children)
        self.assertEqual(
            state_model.children['company'].instance_type,
            'nested_model.serializers.CompanySerializer',
        )

    def test_frontend_model_describes_relations(self):
        state_model = NestedModelChannel._rx_fields['user'].state_model
        self.assertEqual(
            state_model.frontend_model(),
            {
                'nested_model.serializers.UserSerializer': {
                    'company': 'nested_model.serializers.CompanySerializer',
                },
                'nested_model.serializers.CompanySerializer': {},
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
            'nested_model',
            'nested_model.channels.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('_modelFields', content)
        self.assertIn('nested_model.serializers.UserSerializer', content)
        self.assertIn('nested_model.serializers.CompanySerializer', content)
        self.assertIn('"company": "nested_model.serializers.CompanySerializer"', content)

    def test_generated_models_file_has_both_interfaces(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name,
            'nested_model',
            'nested_model.models.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()

        self.assertIn('export interface User {', content)
        self.assertIn('export interface Company {', content)
        self.assertIn('company: Company', content)
