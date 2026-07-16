"""Framework-owned autodiscovery of app `channels` modules (ADR-0018 D6,
task 1.3): registration must land in every process type, not just ones that
happen to import `urls.py` -- so a writer that never imports a channel
module itself still gets it registered, because `rxdjango`'s AppConfig
imports it for every installed app during `django.setup()`.
"""
from __future__ import annotations

import sys

from rxdjango.apps import autodiscover_channels


def test_testapp_channels_autodiscovered_without_any_test_importing_it():
    """`testapp.channels` is a marker module nothing else in this suite
    imports (see its docstring). Its presence in `sys.modules` -- by the
    time any test runs, `django.setup()` has already run `ready()` for
    every app -- is proof that autodiscovery, not a test, imported it."""
    assert 'testapp.channels' in sys.modules
    assert sys.modules['testapp.channels'].AUTODISCOVERED is True


def test_autodiscover_channels_is_idempotent():
    # Calling it again (e.g. a second AppConfig.ready() in a re-exec'd
    # process) must not raise -- import_module is itself idempotent, so
    # this just pins that the walk over installed apps stays side-effect
    # free on a repeat call.
    autodiscover_channels()
    assert 'testapp.channels' in sys.modules
