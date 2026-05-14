"""Protocol-level test for the counter channel.

Wraps the runner's WebSocket so every frame in/out of the JS client is
captured as parsed JSON. The trace is returned to Python as a flat list of
`{ from: 'server' | 'client', data: ... }` entries and asserted on directly.
"""

from __future__ import annotations

from testing.integration import RxProtocolTestCase


class CounterProtocolTests(RxProtocolTestCase):

    app_label = 'counter'
    channel = 'CounterChannel'
    url = '/ws/counter/'

    def test_increment_protocol_trace(self):
        self.eval('const before = channel.counter')
        self.eval('await channel.increment()')
        self.wait_for('channel.counter !== before')
        trace = self.get_trace()

        self.assertGreater(len(trace), 0, f'expected frames, got {trace!r}')

        for frame in trace:
            self.assertIn(frame['from'], ('server', 'client'))
            self.assertIn('data', frame)

        client_frames = [f for f in trace if f['from'] == 'client']
        server_frames = [f for f in trace if f['from'] == 'server']

        self.assertTrue(
            any('increment' in repr(f['data']) for f in client_frames),
            f'expected an increment action in client frames: {client_frames!r}',
        )

        self.assertTrue(
            len(server_frames) >= 2,
            f'expected initial state + at least one delta from server, got {server_frames!r}',
        )
