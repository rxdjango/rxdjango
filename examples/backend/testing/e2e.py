"""Shared scaffolding for browser-driven example tests."""

from __future__ import annotations

import atexit
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
from functools import partial
from pathlib import Path

from channels.testing import ChannelsLiveServerTestCase
from channels.testing.live import make_application, set_database_connection
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test import TransactionTestCase, modify_settings


REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / 'examples' / 'frontend'


class _E2ERuntime:
    started = False
    lock = threading.Lock()
    output: deque[str] = deque(maxlen=200)
    frontend_proc: subprocess.Popen[str] | None = None
    frontend_pgid: int | None = None
    frontend_output_thread: threading.Thread | None = None
    live_server_modified_settings = None
    server_process = None
    shutdown_timer: threading.Timer | None = None
    shutdown_generation = 0
    atexit_registered = False
    live_server_port: int | None = None
    frontend_port: int | None = None
    frontend_base_url: str | None = None

    @classmethod
    def start(cls, test_case: type['RxE2ETestCase']) -> None:
        with cls.lock:
            if cls.shutdown_timer is not None:
                cls.shutdown_timer.cancel()
                cls.shutdown_timer = None
                cls.shutdown_generation += 1
            if cls.started:
                return

            for connection in connections.all():
                if test_case._is_in_memory_db(connection):
                    raise ImproperlyConfigured(
                        'RxE2ETestCase cannot be used with in-memory databases.'
                    )

            cls.live_server_modified_settings = modify_settings(
                ALLOWED_HOSTS={'append': test_case.host},
            )
            cls.live_server_modified_settings.enable()

            static_wrapper = (
                test_case.static_wrapper if test_case.serve_static else None
            )
            get_application = partial(make_application, static_wrapper=static_wrapper)
            cls.server_process = test_case.ProtocolServerProcess(
                test_case.host,
                get_application,
                setup=set_database_connection,
            )
            cls.server_process.daemon = True
            cls.server_process.start()
            while True:
                if not cls.server_process.ready.wait(timeout=1):
                    if cls.server_process.is_alive():
                        continue
                    raise RuntimeError('E2E live server stopped before it was ready.')
                break
            cls.live_server_port = cls.server_process.port.value

            cls.frontend_port = _free_port()
            cls.frontend_base_url = f'http://127.0.0.1:{cls.frontend_port}'
            cls.frontend_proc = cls._start_frontend_server(test_case)
            cls._wait_for_frontend(test_case)

            cls.started = True
            if not cls.atexit_registered:
                atexit.register(cls.stop)
                cls.atexit_registered = True

    @classmethod
    def stop_when_idle(cls, delay: float = 0.5) -> None:
        with cls.lock:
            if not cls.started:
                return
            if cls.shutdown_timer is not None:
                cls.shutdown_timer.cancel()
            cls.shutdown_generation += 1
            generation = cls.shutdown_generation
            cls.shutdown_timer = threading.Timer(
                delay,
                cls._stop_if_idle,
                args=(generation,),
            )
            cls.shutdown_timer.daemon = False
            cls.shutdown_timer.start()

    @classmethod
    def _stop_if_idle(cls, generation: int) -> None:
        with cls.lock:
            if generation != cls.shutdown_generation:
                return
        cls.stop()

    @classmethod
    def stop(cls) -> None:
        with cls.lock:
            if (
                cls.shutdown_timer is not None
                and cls.shutdown_timer is not threading.current_thread()
            ):
                cls.shutdown_timer.cancel()
            cls.shutdown_timer = None

            cls._stop_frontend_server()

            if cls.server_process is not None:
                cls.server_process.terminate()
                cls.server_process.join()
                cls.server_process = None

            if cls.live_server_modified_settings is not None:
                cls.live_server_modified_settings.disable()
                cls.live_server_modified_settings = None

            cls.started = False

    @classmethod
    def _start_frontend_server(cls, test_case: type['RxE2ETestCase']):
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
                f'http://{test_case.host}:{cls.live_server_port}',
            ),
            'WDS_SOCKET_HOST': '127.0.0.1',
            'WDS_SOCKET_PORT': str(cls.frontend_port),
        })

        proc = subprocess.Popen(
            [npm, 'start'],
            cwd=test_case.frontend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
        )

        def collect_output():
            assert proc.stdout is not None
            for line in proc.stdout:
                cls.output.append(line.rstrip())

        thread = threading.Thread(target=collect_output, daemon=True)
        thread.start()
        cls.frontend_output_thread = thread
        cls.frontend_pgid = proc.pid
        return proc

    @classmethod
    def _wait_for_frontend(cls, test_case: type['RxE2ETestCase']):
        deadline = time.monotonic() + test_case.frontend_timeout
        assert cls.frontend_base_url is not None

        while time.monotonic() < deadline:
            assert cls.frontend_proc is not None
            if cls.frontend_proc.poll() is not None:
                output = '\n'.join(cls.output)
                raise RuntimeError(
                    'examples/frontend dev server exited before it was ready.\n'
                    f'{output}'
                )

            try:
                with urllib.request.urlopen(
                    cls.frontend_base_url,
                    timeout=1,
                ) as response:
                    if response.status < 500:
                        return
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(0.25)

        output = '\n'.join(cls.output)
        raise RuntimeError(
            f'examples/frontend did not start within {test_case.frontend_timeout}s.\n'
            f'{output}'
        )

    @classmethod
    def _stop_frontend_server(cls):
        proc = cls.frontend_proc
        pgid = cls.frontend_pgid
        if proc is None or pgid is None:
            return

        os.killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(pgid, signal.SIGKILL)
            proc.wait()
        finally:
            cls.frontend_proc = None
            cls.frontend_pgid = None


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


class RxE2ETestCase(TransactionTestCase):
    """Base class for Playwright-driven tests against the examples frontend."""

    frontend_dir = FRONTEND_DIR
    frontend_timeout = 90
    browser_name = 'chromium'
    headless = True
    host = ChannelsLiveServerTestCase.host
    ProtocolServerProcess = ChannelsLiveServerTestCase.ProtocolServerProcess
    static_wrapper = ChannelsLiveServerTestCase.static_wrapper
    serve_static = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _E2ERuntime.start(cls)
        cls._port = _E2ERuntime.live_server_port
        cls.frontend_port = _E2ERuntime.frontend_port
        cls.frontend_base_url = _E2ERuntime.frontend_base_url

    @classmethod
    def tearDownClass(cls):
        _E2ERuntime.stop_when_idle()
        super().tearDownClass()

    @property
    def live_server_url(self):
        return 'http://%s:%s' % (self.host, self._port)

    @property
    def live_server_ws_url(self):
        return 'ws://%s:%s' % (self.host, self._port)

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
    def _is_in_memory_db(cls, connection):
        if connection.vendor == 'sqlite':
            return connection.is_in_memory_db()
        return False

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
