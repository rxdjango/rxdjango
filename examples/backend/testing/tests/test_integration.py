"""End-to-end integration tests for the TestingChannel."""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase


class TestingChannelIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'TestingChannel'
    url = '/ws/testing/'

    def test_optionals_act_as_primitives_when_set(self):
        self.eval('await channel.check_optionals_act_as_primitives_when_set()')
        self.wait_for("channel.str_with_default !== 'hello'")
        str_with_default = self.get_result('channel.str_with_default')

        self.assertEqual(str_with_default, 'ew')
