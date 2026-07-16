"""Framework-owned autodiscovery of app `channels` modules (ADR-0018 D6).

A writer's routing (and reactive-model) registrations live inside plain
imported code -- a channel module's class bodies, run once at import. Web
workers pick that up incidentally, because `asgi.py` imports the URL
conf, which imports every app's `channels.py` to build `as_asgi()` routes.
Task workers and management commands have no reason to import `urls.py` at
all, and a writer process that never imports the declarations under-
broadcasts silently (list-routing: "the dimension-group broadcast is still
sent, because `AppConfig.ready()` imported the channel declarations").

Every Django process type runs `django.setup()`, so hooking this into
`AppConfig.ready()` -- rather than requiring each app to wire up its own
import -- satisfies ADR-0018's hard requirement by installing the app, not
by per-app discipline.
"""
from __future__ import annotations

from importlib import import_module

from django.apps import AppConfig, apps
from django.utils.module_loading import module_has_submodule


class RxDjangoConfig(AppConfig):
    name = 'rxdjango'

    def ready(self) -> None:
        autodiscover_channels()


def autodiscover_channels() -> None:
    """Import every installed app's `channels` module, tolerating its
    absence -- the same `module_has_submodule` idiom Django's own
    `contrib.admin.autodiscover_modules` uses, so a genuine import error
    inside a `channels.py` that does exist still propagates loudly instead
    of being swallowed as "module not found"."""
    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, 'channels'):
            import_module(f'{app_config.name}.channels')
