"""Integration tests for the authorization_meta channel.

Same coverage as the authorization app, but using Meta.action_requires to
gate every action by default with @action(anonymous=True) opting out.
"""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase


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
