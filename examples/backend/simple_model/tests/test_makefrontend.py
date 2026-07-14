import os
import tempfile

from django.test import TestCase, override_settings
from rxdjango.sdk import make_sdk
from rxdjango.testing.ts_ast import find_member, parse_ts_file
from rxdjango.ts.channels import create_app_channels

from rxdjango_model import tracked_serializers
from rxdjango_model.ts.models import create_app_models
from simple_model.channels import SimpleModelChannel
from simple_model.serializers import UserSerializer


class SimpleModelMakeFrontendTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_generates_model_type_file_for_rx_model_serializer(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            changed = make_sdk(quiet=True)

        ts_path = os.path.join(
            self.tmpdir.name,
            'simple_model',
            'simple_model.models.ts',
        )
        self.assertTrue(
            os.path.exists(ts_path),
            f'expected generated model file at {ts_path}',
        )
        self.assertTrue(changed)
        with open(ts_path) as fh:
            content = fh.read()
        self.assertIn('export interface User {', content)
        self.assertIn('  _loaded: true;', content)
        self.assertIn('  name: string;', content)
        # No relation fields on this serializer, so the shared Unloaded type
        # is never referenced -- codegen must not emit an unused import.
        self.assertNotIn('Unloaded', content)

    def test_rx_model_serializer_is_tracked(self):
        self.assertIn(UserSerializer, tracked_serializers())
        self.assertIn('user', SimpleModelChannel._rx_fields)

    def test_channel_uses_imported_model_type_for_rx_model_field(self):
        with override_settings(
            RX_FRONTEND_DIR=self.tmpdir.name,
            RX_WEBSOCKET_URL="'ws://testserver'",
        ):
            create_app_models('simple_model')
            create_app_channels('simple_model')

        ts_path = os.path.join(
            self.tmpdir.name,
            'simple_model',
            'simple_model.channels.ts',
        )
        with open(ts_path) as fh:
            content = fh.read()
        self.assertIn(
            "import type { User } from './simple_model.models';",
            content,
        )

        node_modules = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..',
                '..',
                '..',
                'frontend',
                'node_modules',
            )
        )
        parsed = parse_ts_file(ts_path, node_modules_dir=node_modules)
        cls = next(
            item for item in parsed['classes']
            if item['name'] == 'SimpleModelChannel'
        )
        member = find_member(cls, 'user')
        self.assertIsNotNone(member)
        self.assertEqual(member['type'], 'User | null')
        self.assertEqual(member['initializer']['text'], 'null')
