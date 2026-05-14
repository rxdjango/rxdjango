"""Shared scaffolding for browser-driven example tests."""

from __future__ import annotations

import os
import signal
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

from channels.testing import ChannelsLiveServerTestCase


REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / 'examples' / 'frontend'


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _ws_base_url(http_url: str) -> str:
    if http_url.startswith('https://'):
        return 'wss://' + http_url[len('https://'):]
    if http_url.startswith('http://'):
        return 'ws://' + http_url[len('http://'):]
    raise ValueError(f'Unsupported live server URL: {http_url!r}')


class RxE2ETestCase(ChannelsLiveServerTestCase):
    """Base class for Playwright-driven tests against the examples frontend."""

    frontend_dir = FRONTEND_DIR
    frontend_timeout = 90
    browser_name = 'chromium'
    headless = True
    serve_static = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._frontend_output: deque[str] = deque(maxlen=200)
        cls.frontend_port = _free_port()
        cls.frontend_base_url = f'http://127.0.0.1:{cls.frontend_port}'
        cls._frontend_proc = cls._start_frontend_server()
        cls._wait_for_frontend()

    @classmethod
    def tearDownClass(cls):
        cls._stop_frontend_server()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                'E2E tests need the Python `playwright` package. '
                'Run `uv sync` from the repository root.'
            ) from exc

        self._playwright = sync_playwright().start()
        browser_factory = getattr(self._playwright, self.browser_name)
        try:
            self.browser = browser_factory.launch(headless=self.headless)
        except Exception as exc:
            self._playwright.stop()
            raise RuntimeError(
                'Playwright is installed, but its browser runtime is missing. '
                'Run `uv run playwright install chromium` from the repository root.'
            ) from exc
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self._playwright.stop()
        super().tearDown()

    @classmethod
    def _start_frontend_server(cls):
        npm = shutil.which('npm')
        if npm is None:
            raise RuntimeError(
                'E2E tests need `npm` on PATH to serve examples/frontend.'
            )

        env = os.environ.copy()
        env.update({
            'BROWSER': 'none',
            'HOST': '127.0.0.1',
            'PORT': str(cls.frontend_port),
            'REACT_APP_RX_WEBSOCKET_URL': _ws_base_url(
                f'http://{cls.host}:{cls._port}',
            ),
            'WDS_SOCKET_HOST': '127.0.0.1',
            'WDS_SOCKET_PORT': str(cls.frontend_port),
        })

        proc = subprocess.Popen(
            [npm, 'start'],
            cwd=cls.frontend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
        )

        def collect_output():
            assert proc.stdout is not None
            for line in proc.stdout:
                cls._frontend_output.append(line.rstrip())

        thread = threading.Thread(target=collect_output, daemon=True)
        thread.start()
        cls._frontend_output_thread = thread
        return proc

    @classmethod
    def _wait_for_frontend(cls):
        deadline = time.monotonic() + cls.frontend_timeout
        url = cls.frontend_base_url

        while time.monotonic() < deadline:
            if cls._frontend_proc.poll() is not None:
                output = '\n'.join(cls._frontend_output)
                raise RuntimeError(
                    'examples/frontend dev server exited before it was ready.\n'
                    f'{output}'
                )

            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status < 500:
                        return
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(0.25)

        output = '\n'.join(cls._frontend_output)
        raise RuntimeError(
            f'examples/frontend did not start within {cls.frontend_timeout}s.\n'
            f'{output}'
        )

    @classmethod
    def _stop_frontend_server(cls):
        proc = getattr(cls, '_frontend_proc', None)
        if proc is None or proc.poll() is not None:
            return

        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()

    def frontend_url(self, path: str = '/') -> str:
        if not path.startswith('/'):
            path = '/' + path
        return self.frontend_base_url + path

    def goto(self, path: str = '/'):
        self.page.goto(self.frontend_url(path), wait_until='domcontentloaded')
        return self.page

    def goto_demo(self, slug: str):
        return self.goto(f'/{slug.strip("/")}/demo')

    def field(self, label: str):
        return self.page.locator(f'dt:has-text("{label}") + dd')
