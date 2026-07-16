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

        self.assertEqual(len(trace), 4)
        self.assertEqual(trace[0], {'from': 'server',
                                    'data': {'protocol': '0.4.0', 't': 'ready'},
                                    })
        self.assertEqual(trace[1], {'from': 'client',
                                    'data': {'a': 'increment', 'id': '1', 'p': [], 't': 'ac'},
                                    })
        self.assertEqual(trace[2], {'from': 'server',
                                    'data': {'e': 0, 'id': '1', 'r': None, 't': 'ac'},
                                    })
        self.assertEqual(trace[3], {'from': 'server',
                                    'data': {'f': 'counter', 't': 'rx', 'v': 1},
                                    })
