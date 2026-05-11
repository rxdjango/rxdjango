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


class MemoTrackingChannelIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'MemoTrackingChannel'
    url = '/ws/testing/memo/'

    def test_memo_not_recomputed_for_unrelated_field(self):
        self.eval('await channel.increment_a()')
        self.wait_for('channel.count_a === 1')
        state = self.get_result(
            '{ count_a: channel.count_a, count_b: channel.count_b }'
        )

        self.assertEqual(state, {'count_a': 1, 'count_b': 0})

    def test_only_dependent_memo_is_recomputed(self):
        self.eval('await channel.increment_a()')
        self.wait_for('channel.double_a === 2')
        self.eval('await channel.increment_b()')
        self.wait_for('channel.double_b === 2')
        state = self.get_result(
            '{ double_a: channel.double_a, double_b: channel.double_b,'
            ' count_a: channel.count_a, count_b: channel.count_b }'
        )

        self.assertEqual(
            state,
            {'double_a': 2, 'double_b': 2, 'count_a': 1, 'count_b': 1},
        )
