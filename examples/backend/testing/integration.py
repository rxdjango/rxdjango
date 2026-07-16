"""
Shared scaffolding for Node-driven integration tests.

A test subclass declares which Django app to generate channels for, writes a
Node runner script, and asserts on its stdout. Everything else — building
``@rxdjango/react``, generating the TS channels, wiring up a workdir that
resolves ``@rxdjango/react`` and ``react`` so node can load the generated
module — is handled by ``RxIntegrationTestCase``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from channels.testing import ChannelsLiveServerTestCase
from django.test import override_settings

from rxdjango.ts.channels import create_app_channels


REPO_ROOT = Path(__file__).resolve().parents[3]
REACT_PKG_DIR = REPO_ROOT / 'packages' / 'react'
REACT_DIST_ENTRY = REACT_PKG_DIR / 'dist' / 'index.js'
REACT_SRC_DIR = REACT_PKG_DIR / 'src'

_build_lock = threading.Lock()


class Instruction:
    def render(self) -> str:
        raise NotImplementedError


class EvalInstruction(Instruction):
    def __init__(self, code: str):
        self.code = code

    def render(self) -> str:
        return f'  {self.code};\n'


class WaitInstruction(Instruction):
    def __init__(self, condition: str, timeout: int = 2000):
        self.condition = condition
        self.timeout = timeout

    def render(self) -> str:
        # The condition may itself contain quotes; json.dumps produces a safely
        # escaped JS string literal for the timeout message.
        message = json.dumps(f'wait_for timeout: {self.condition}')
        return (
            '  {\n'
            '    const __start = Date.now();\n'
            f'    while (!({self.condition})) {{\n'
            f'      if (Date.now() - __start > {self.timeout}) '
            f'throw new Error({message});\n'
            '      await new Promise((r) => setTimeout(r, 10));\n'
            '    }\n'
            '  }\n'
        )


def _latest_mtime(root: Path) -> float:
    latest = 0.0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                mtime = (Path(dirpath) / name).stat().st_mtime
            except FileNotFoundError:
                continue
            if mtime > latest:
                latest = mtime
    return latest


def ensure_react_package_built() -> Path:
    """Build ``packages/react`` if its dist is missing or stale.

    Returns the path to the dist directory. Raises a clear error if ``npm``
    is not on PATH or the build fails.
    """
    with _build_lock:
        if REACT_DIST_ENTRY.exists():
            src_mtime = _latest_mtime(REACT_SRC_DIR)
            dist_mtime = REACT_DIST_ENTRY.stat().st_mtime
            if dist_mtime >= src_mtime:
                return REACT_DIST_ENTRY.parent

        npm = shutil.which('npm')
        if npm is None:
            raise RuntimeError(
                'Integration tests need `npm` on PATH to build '
                f'{REACT_PKG_DIR.relative_to(REPO_ROOT)}. Install Node.js or '
                'pre-build the package and re-run.'
            )

        proc = subprocess.run(
            [npm, 'run', 'build'],
            cwd=REACT_PKG_DIR,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                'Failed to build @rxdjango/react for integration tests.\n'
                f'stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}'
            )
        if not REACT_DIST_ENTRY.exists():
            raise RuntimeError(
                f'npm run build succeeded but {REACT_DIST_ENTRY} is missing.'
            )
        return REACT_DIST_ENTRY.parent


# Minimal `react` shim. The bundled @rxdjango/react entry statically imports
# `react` for `useChannel`, but node integration tests never call it. The stub
# is enough to satisfy module resolution.
_REACT_STUB_JS = (
    'export function useState(initial) {\n'
    '  const v = typeof initial === "function" ? initial() : initial;\n'
    '  return [v, () => {}];\n'
    '}\n'
    'export function useSyncExternalStore() {}\n'
)


class RxIntegrationTestCase(ChannelsLiveServerTestCase):
    """Base class for Node-driven RxDjango integration tests.

    Subclasses set ``app_label`` to the Django app whose channels should be
    generated, then in their test method write a runner script with
    ``self.write_runner(...)`` and execute it with ``self.run_node(...)``.
    """

    app_label: str = ''
    serve_static = False

    def setUp(self):
        super().setUp()
        if not self.app_label:
            raise RuntimeError(
                f'{type(self).__name__}.app_label must be set'
            )

        dist_dir = ensure_react_package_built()

        self.workdir = Path(tempfile.mkdtemp(prefix='rxdj-it-'))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

        self.instructions: list[Instruction] = []

        with override_settings(
            RX_FRONTEND_DIR=str(self.workdir),
            RX_WEBSOCKET_URL=json.dumps(
                self.live_server_url.replace('http://', 'ws://')
            ),
        ):
            create_app_channels(self.app_label)

        self._install_fake_package(
            '@rxdjango/react',
            main='./dist/index.js',
            extra={'dist': dist_dir},
        )
        self._install_fake_package(
            'react',
            main='./index.js',
            files={'index.js': _REACT_STUB_JS},
        )

    def _install_fake_package(self, name, *, main, extra=None, files=None):
        pkg_dir = self.workdir / 'node_modules'
        for part in name.split('/'):
            pkg_dir = pkg_dir / part
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / 'package.json').write_text(json.dumps({
            'name': name,
            'version': '0.0.0-test',
            'type': 'module',
            'main': main,
        }))
        for filename, content in (files or {}).items():
            (pkg_dir / filename).write_text(content)
        for linkname, target in (extra or {}).items():
            dest_path = pkg_dir / linkname
            if dest_path.is_symlink() or dest_path.exists():
                if dest_path.is_dir() and not dest_path.is_symlink():
                    shutil.rmtree(dest_path)
                else:
                    dest_path.unlink()
            # Copy rather than symlink so node resolves bare imports (e.g.
            # `react`) starting from this workdir's node_modules instead of
            # the real package location, which intentionally lacks `react`.
            if Path(target).is_dir():
                shutil.copytree(target, dest_path)
            else:
                shutil.copy2(target, dest_path)

    def ws_url(self, route: str) -> str:
        if not route.startswith('/'):
            route = '/' + route
        return self.live_server_url.replace('http://', 'ws://') + route

    def write_runner(self, content: str, name: str = 'runner.ts') -> Path:
        path = self.workdir / name
        path.write_text(content)
        return path

    def run_node(self, script: str, *args: str, timeout: float = 30):
        return subprocess.run(
            [
                'node',
                '--experimental-strip-types',
                '--no-warnings=ExperimentalWarning',
                script,
                *args,
            ],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def eval(self, code: str) -> None:
        self.instructions.append(EvalInstruction(code))

    def wait_for(self, condition: str, timeout: int = 2000) -> None:
        self.instructions.append(WaitInstruction(condition, timeout))

    # Hook for subclasses to inject code before the channel is constructed
    # (e.g. to wrap globalThis.WebSocket). Default: nothing.
    runner_preamble: str = ''

    # Optional extra payload assembled in the runner and emitted alongside the
    # result variable. Subclasses set this to a JS expression; when non-empty,
    # stdout becomes `{"result": <variable>, "<extra_payload_key>": <expr>}`.
    extra_payload_key: str = ''
    extra_payload_expr: str = ''

    def get_result(self, variable: str):
        body = ''.join(instr.render() for instr in self.instructions)

        if self.extra_payload_key:
            output_expr = (
                '{ result: ' + variable
                + ', ' + self.extra_payload_key + ': ' + self.extra_payload_expr
                + ' }'
            )
        else:
            output_expr = variable

        code = (
            f'import {{ {self.channel} }} from '
            f'"./{self.app_label}/{self.app_label}.channels.ts";\n'
            + self.runner_preamble
            + r"""
const wsUrl = process.argv[2];
if (!wsUrl) {
  console.error("usage: runner.ts <ws-url>");
  process.exit(2);
}

async function main() {
  const channel: any = new (""" + self.channel + r""" as any)(wsUrl);

  // Deliberately never unsubscribed: this script uses `channel` for its
  // whole lifetime, and the persistent-socket transport (react-client
  // "Persistent socket with backoff") stops reconnecting once the last
  // subscriber unmounts -- unsubscribing here would arm that the moment the
  // ready wait resolves, so a later server-initiated close would never be
  // retried.
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    channel.rx.subscribe(() => {
      clearTimeout(timer);
      resolve();
    });
  });
""" + body + r"""
  process.stdout.write(JSON.stringify(""" + output_expr + r"""));
  process.exit(0);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
"""
        )

        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))

        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )

        self.instructions = []

        parsed = json.loads(result.stdout)
        if self.extra_payload_key:
            self._last_extra = parsed.get(self.extra_payload_key)
            return parsed['result']
        return parsed


_PROTOCOL_TRACE_PREAMBLE = r"""
const __trace: any[] = [];
const __OriginalWebSocket: any = (globalThis as any).WebSocket;
class __TracingWebSocket extends __OriginalWebSocket {
  constructor(url: string, protocols?: any) {
    super(url, protocols);
    this.addEventListener('message', (ev: any) => {
      let parsed: any;
      try { parsed = JSON.parse(ev.data); } catch { parsed = ev.data; }
      __trace.push({ from: 'server', data: parsed });
    });
    const origSend = super.send.bind(this);
    (this as any).send = (data: any) => {
      let parsed: any;
      try { parsed = JSON.parse(data); } catch { parsed = data; }
      __trace.push({ from: 'client', data: parsed });
      return origSend(data);
    };
  }
}
(globalThis as any).WebSocket = __TracingWebSocket;
"""


class RxProtocolTestCase(RxIntegrationTestCase):
    """Like RxIntegrationTestCase, but captures every websocket frame.

    Each captured frame is `{ from: 'server' | 'client', data: <parsed JSON> }`.
    Retrieve the full trace after running instructions with `get_trace()`, or
    use `get_result()` as usual and read `self.last_trace`.
    """

    runner_preamble = _PROTOCOL_TRACE_PREAMBLE
    extra_payload_key = 'trace'
    extra_payload_expr = '__trace'

    last_trace: list = []

    def get_result(self, variable: str):
        result = super().get_result(variable)
        self.last_trace = self._last_extra or []
        return result

    def get_trace(self) -> list:
        self.get_result('null')
        return self.last_trace
