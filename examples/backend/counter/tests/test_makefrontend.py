import os
import re
import tempfile

from django.test import TestCase, override_settings

from rxdjango.ts.channels import create_app_channels


class MakeFrontendCounterTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _generated_ts(self):
        with override_settings(RX_FRONTEND_DIR=self.tmpdir.name):
            create_app_channels('counter')
        ts_path = os.path.join(self.tmpdir.name, 'counter', 'counter.channels.ts')
        self.assertTrue(
            os.path.exists(ts_path),
            f'expected generated file at {ts_path}',
        )
        with open(ts_path) as fh:
            return fh.read()

    def test_emits_context_channel_class(self):
        ts = self._generated_ts()
        self.assertRegex(
            ts,
            r'export\s+class\s+CounterChannel\s+extends\s+ContextChannel\s*\{',
        )

    def test_counter_field_declared_with_default(self):
        ts = self._generated_ts()
        self.assertRegex(ts, r'\bcounter\s*:\s*number\s*=\s*0\b')
