import inspect
import os
import tempfile

from django.test import TestCase, override_settings

from rxdjango.testing.ts_ast import find_class, parse_ts_file
from rxdjango.ts.channels import create_app_channels


class FrontendTestCase(TestCase):
    """Base test case that generates an app's TS channels and exposes the parsed class."""

    app_name: str = ''
    channel_file: str = ''
    class_name: str = ''

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def parse_class(self):
        with override_settings(RX_FRONTEND_DIR=self.tmpdir.name):
            create_app_channels(self.app_name)
        ts_path = os.path.join(self.tmpdir.name, self.app_name, self.channel_file)
        self.assertTrue(
            os.path.exists(ts_path),
            f'expected generated file at {ts_path}',
        )
        # Resolve node_modules relative to the subclass's file so the tempdir
        # generation can typecheck against the example frontend's typescript.
        subclass_dir = os.path.dirname(inspect.getfile(self.__class__))
        examples_frontend = os.path.abspath(
            os.path.join(subclass_dir, '..', '..', '..', 'frontend')
        )
        node_modules = os.path.join(examples_frontend, 'node_modules')
        parsed = parse_ts_file(ts_path, node_modules_dir=node_modules)
        self.assertEqual(parsed['parseErrors'], [], 'TypeScript parse errors')
        cls = find_class(parsed, self.class_name)
        self.assertIsNotNone(cls, f'{self.class_name} class not found')
        return cls
