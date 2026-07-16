"""Persistent-socket reconnect, end to end (static-queryset-lists task 6.3).

`ReconnectChannel.force_disconnect` closes the WebSocket server-side, on
purpose, mid-connection. The generated client's `PersistentSocket` notices
the unexpected close and reconnects with backoff on its own -- nothing in
this test drives that from the JS side. `on_connect` reruns on the new
connection and rebinds `tasks` from scratch (ADR-0019 D5: reconnect is a
rebind over a warm index); an action call issued after the drop is queued
(or sent fresh once the new connection is up) and resolving at all is what
proves the client healed and converged rather than staying stuck.
"""

from __future__ import annotations

from testing.integration import RxIntegrationTestCase

from static_queryset.models import Task


class ReconnectIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'ReconnectChannel'
    url = '/ws/testing/reconnect/'

    def setUp(self):
        super().setUp()
        Task.objects.all().delete()
        Task.objects.create(name='Survives a reconnect', status='open', priority=1)

    def test_client_heals_and_converges_after_a_server_side_close(self):
        self.wait_for('channel.tasks !== null')
        before = self.get_result('channel.tasks.map((t) => t.name)')
        self.assertEqual(before, ['Survives a reconnect'])

        # Fire-and-forget: the connection dies before this action's own
        # response can be sent, so its promise is not awaited here.
        self.eval('channel.force_disconnect().catch(() => {})')
        # Give the close event, the backoff timer (default 250ms), and the
        # reconnect handshake time to land, so the next action is sent over
        # the *new* connection rather than racing the old one's teardown.
        self.eval('await new Promise((resolve) => setTimeout(resolve, 1000))')

        # Resolving at all proves the client reconnected -- a permanently
        # dead connection would leave this promise (and the whole script)
        # hanging until the harness's timeout.
        self.eval('const pong = await channel.ping()')
        result = self.get_result(
            '{ pong, tasks: channel.tasks.map((t) => t.name) }',
        )

        self.assertEqual(result['pong'], 'pong')
        # on_connect reran on the new connection and rebound tasks fresh.
        self.assertEqual(result['tasks'], ['Survives a reconnect'])
