"""Integration tests for the authorization channel.

Drives the generated AuthorizationChannel from a real Node client over a
live websocket. Covers both the success path (authorize then increment)
and the rejection path (increment without authorization returns 403).
"""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase
from testing.integration import RxIntegrationTestCase


class AuthorizationE2ETests(RxE2ETestCase):
    def test_authorize_then_increment_updates_counter_value(self):
        page = self.goto_demo('examples/authorization')

        expect(self.field('Counter value')).to_have_text('0')

        page.get_by_role('button', name='Authorize').click()
        page.get_by_role('button', name='Increment').click()

        expect(self.field('Counter value')).to_have_text('1')


class AuthorizationIntegrationTests(RxIntegrationTestCase):
    app_label = 'authorization'
    channel = 'AuthorizationChannel'
    url = '/ws/authorization/'

    def test_increment_after_authorize_updates_counter(self):
        self.eval('const before = channel.counter')
        self.eval('await channel.authorize("password")')
        self.eval('await channel.increment()')
        self.wait_for('channel.counter !== before')

        counter = self.get_result('channel.counter')
        self.assertEqual(counter, 1)

    def test_increment_without_authorize_returns_403(self):
        self.eval(
            'let captured = null;\n'
            '  try {\n'
            '    await channel.increment();\n'
            '  } catch (e) {\n'
            '    captured = { code: e.code, message: e.message };\n'
            '  }'
        )

        result = self.get_result('captured')
        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 403)
