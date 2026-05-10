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
    timeout: int = 5000

    def setUp(self):
        super().setUp()
        if not self.app_label:
            raise RuntimeError(
                f'{type(self).__name__}.app_label must be set'
            )

        dist_dir = ensure_react_package_built()

        self.workdir = Path(tempfile.mkdtemp(prefix='rxdj-it-'))
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)

        self.setup_instructions = None
        self.exec_instructions = None
        self.wait_instructions = None

        with override_settings(RX_FRONTEND_DIR=str(self.workdir)):
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

    def setup(self, code):
        if self.setup_instructions is not None:
            raise Exception("Can only setup once per test")
        self.setup_instructions = code

    def execute(self, code):
        if self.exec_instructions is not None:
            raise Exception("Can only execute one instruction per test")
        self.exec_instructions = code

    def wait_for(self, code):
        if self.wait_instructions is not None:
            raise Exception("Can only set one wait instruction per test")
        self.wait_instructions = code

    def get_state(self, variable):
        code = f'import {{ {self.channel} }} from "./{self.app_label}/{self.app_label}.channels.ts";\n'
        code += r"""
const wsUrl = process.argv[2];
if (!wsUrl) {
  console.error("usage: runner.ts <ws-url>");
  process.exit(2);
}

async function main() {
  const channel: any = new (""" + self.channel + """ as any)(wsUrl);

  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    const unsub = channel.rx.subscribe(() => {
      clearTimeout(timer);
      unsub();
      resolve();
    });
  });
"""
        code += f'\n{self.setup_instructions};\n'
        code += r"""

  // Subscribe before executing so we don't miss the diff
  const waitDone = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("wait_for timeout")), """ + f'{self.timeout}' + r""");
    const unsub = channel.rx.subscribe(() => {
      if (""" + self.wait_instructions + r""") {
        clearTimeout(timer);
        unsub();
        resolve();
      }
    });
  });
"""
        code += f'\n{self.exec_instructions};\n'
        code += r"""
  await waitDone;

  process.stdout.write(JSON.stringify(""" + variable + """));
  process.exit(0);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
"""

        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))

        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )

        self.setup_instructions = None
        self.exec_instructions = None
        self.wait_instructions = None

        return json.loads(result.stdout)
