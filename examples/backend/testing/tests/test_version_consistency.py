"""Integration test for client-side version watermarks (ADR-0014).

The ``VersionConsistencyChannel`` relays a mock ``counter`` layer with a
far-newer ``_v`` before fetching the real, older-version row from the database.
The client's ``StateBuilder`` must keep the higher-version layer regardless of
arrival order, so the value the frontend ends up with is the mock's.
"""

from __future__ import annotations

from testing.channels import VersionConsistencyChannel
from testing.integration import RxIntegrationTestCase
from testing.models import VersionedCounter


class VersionConsistencyIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'VersionConsistencyChannel'
    url = '/ws/testing/version/'

    def test_newer_layer_wins_over_stale_db_snapshot(self):
        VersionedCounter.objects.update_or_create(id=1, defaults={'value': 42})

        # `loaded` flips after the real (older-version) snapshot is relayed, so
        # once it is true the stale snapshot has been delivered and reconciled.
        self.wait_for('channel.loaded === true')
        value = self.get_result('channel.counter.value')

        self.assertEqual(value, VersionConsistencyChannel.MOCK_VALUE)
        self.assertNotEqual(value, 42)
