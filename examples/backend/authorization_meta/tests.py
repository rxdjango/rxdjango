"""Integration tests for the authorization_meta channel.

Same coverage as the authorization app, but using Meta.action_requires to
gate every action by default with @action(anonymous=True) opting out.
"""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase
from testing.integration import RxIntegrationTestCase


class AuthorizationMetaE2ETests(RxE2ETestCase):
    def test_authorize_then_increment_updates_counter_value(self):
        page = self.goto_demo('examples/authorization_meta')

        expect(self.field('Counter value')).to_have_text('0')

        page.get_by_role('button', name='Authorize').click()
        page.get_by_role('button', name='Increment').click()

        expect(self.field('Counter value')).to_have_text('1')


class AuthorizationMetaIntegrationTests(RxIntegrationTestCase):
    app_label = 'authorization_meta'
    channel = 'AuthorizationMetaChannel'
    url = '/ws/authorization_meta/'

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
