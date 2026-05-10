"""
End-to-end integration test for the counter channel.

The test:
  1. Generates the TypeScript channel for the `counter` app via makefrontend.
  2. Boots a real ASGI server (Daphne) via ChannelsLiveServerTestCase, which
     serves the CounterChannel websocket route from backend/urls.py.
  3. Launches `node` against a generated runner script that:
       - imports the generated CounterChannel,
       - opens a websocket to the live server,
       - calls `channel.increment()`,
       - reads back `channel.counter` after the action resolves,
       - prints the final value as JSON on stdout.
  4. Asserts the runner reports `counter == 1`.

Per the project state, the websocket transport and the action RPC plumbing
on `ContextChannel` are not implemented yet, so this test is expected to
fail until that work lands. The shape of the test is what the final
integration surface should look like.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from channels.testing import ChannelsLiveServerTestCase
from django.test import override_settings

from rxdjango.ts.channels import create_app_channels


# Plain-JS port of packages/react/src/ContextChannel.ts. Node refuses to strip
# TypeScript types from files under node_modules, so we ship the shim as JS
# rather than copying the .ts source. This must stay behaviorally in sync
# with the real implementation; if it drifts, see ContextChannel.ts.
REACT_SHIM_JS = r"""
export class ContextChannel {
  constructor() {
    this._version = 0;
    this._listeners = new Set();
    this.rx = {
      subscribe: (listener) => {
        this._listeners.add(listener);
        return () => { this._listeners.delete(listener); };
      },
      getVersion: () => this._version,
      callAction: (action, params) => this._callAction(action, params),
    };
  }
  async _callAction(_action, _params) {
    throw new Error("ContextChannel._callAction not implemented");
  }
  notify() {
    this._version++;
    this._listeners.forEach((listener) => listener());
  }
}
export function useChannel() {
  throw new Error("useChannel is not usable in node integration tests");
}
export const VERSION = "0.1.0-test-shim";
"""

RUNNER_TS = r"""
// Node integration runner. Imports the generated CounterChannel, drives an
// increment action, and prints the resulting counter value.
import { CounterChannel } from "./counter/counter.channels.ts";

const wsUrl = process.argv[2];
if (!wsUrl) {
  console.error("usage: runner.ts <ws-url>");
  process.exit(2);
}

async function main() {
  // The generated channel constructor is expected to accept a websocket URL
  // (or a transport object) — see ContextChannel in @rxdjango/react.
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


class CounterIntegrationTests(ChannelsLiveServerTestCase):
    """Drives the counter channel from a real Node client over a live websocket."""

    serve_static = False

    def setUp(self):
        super().setUp()
        self.workdir = Path(tempfile.mkdtemp(prefix='rxdj-counter-it-'))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

        # Generate the TS channel for the counter app into the workdir.
        with override_settings(RX_FRONTEND_DIR=str(self.workdir)):
            create_app_channels('counter')
        generated = self.workdir / 'counter' / 'counter.channels.ts'
        self.assertTrue(generated.exists(), f'expected generated TS at {generated}')

        # Stand up a fake `@rxdjango/react` package backed by the in-repo
        # source so the generated channel's `import ... from "@rxdjango/react"`
        # resolves without a published build.
        pkg_dir = self.workdir / 'node_modules' / '@rxdjango' / 'react'
        pkg_dir.mkdir(parents=True)
        (pkg_dir / 'index.js').write_text(REACT_SHIM_JS)
        (pkg_dir / 'package.json').write_text(json.dumps({
            'name': '@rxdjango/react',
            'version': '0.0.0-test',
            'type': 'module',
            'main': './index.js',
        }))

        # Write the runner script.
        (self.workdir / 'runner.ts').write_text(RUNNER_TS)

    def test_increment_action_reflects_in_frontend_counter(self):
        ws_url = self.live_server_url.replace('http://', 'ws://') + '/ws/counter/'

        result = subprocess.run(
            [
                'node',
                '--experimental-strip-types',
                '--no-warnings=ExperimentalWarning',
                'runner.ts',
                ws_url,
            ],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )

        # Last non-empty stdout line should be the JSON payload.
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        self.assertTrue(lines, f'no stdout from runner; stderr={result.stderr}')
        payload = json.loads(lines[-1])
        self.assertEqual(payload, {'counter': 1})
