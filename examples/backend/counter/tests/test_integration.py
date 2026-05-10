"""End-to-end integration test for the counter channel.

Boots a real ASGI server (Daphne) via ChannelsLiveServerTestCase and drives
the generated CounterChannel from a Node runner over a live websocket. The
runner imports the generated TS, calls ``increment()``, waits for the diff,
and prints the final counter value as JSON.

All scaffolding (building ``@rxdjango/react``, generating the TS channel,
wiring the workdir's node_modules) lives in
``testing.integration.RxIntegrationTestCase``.
"""

from __future__ import annotations

import json

from testing.integration import RxIntegrationTestCase


RUNNER_TS = r"""
import { CounterChannel } from "./counter/counter.channels.ts";

const wsUrl = process.argv[2];
if (!wsUrl) {
  console.error("usage: runner.ts <ws-url>");
  process.exit(2);
}

async function main() {
  const channel: any = new (CounterChannel as any)(wsUrl);

  // Wait for the initial state push so `counter` reflects the server default.
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    const unsub = channel.rx.subscribe(() => {
      clearTimeout(timer);
      unsub();
      resolve();
    });
  });

  const before = channel.counter;
  await channel.increment();

  // Wait for the diff that bumps `counter` to arrive.
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("increment timeout")), 5000);
    const unsub = channel.rx.subscribe(() => {
      if (channel.counter !== before) {
        clearTimeout(timer);
        unsub();
        resolve();
      }
    });
  });

  process.stdout.write(JSON.stringify({ counter: channel.counter }) + "\n");
  process.exit(0);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
"""


class CounterIntegrationTests(RxIntegrationTestCase):
    """Drives the counter channel from a real Node client over a live websocket."""

    app_label = 'counter'
    channel = 'CounterChannel'
    url = '/ws/counter/'

    def test_increment_action_reflects_in_frontend_counter(self):
        self.setup('const before = channel.counter')
        self.execute('await channel.increment()')
        self.wait_for('channel.counter !== before')
        counter = self.get_state('channel.counter')

        self.assertEqual(counter, 1)
