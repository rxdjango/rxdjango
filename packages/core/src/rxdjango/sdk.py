from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rxdjango.ts.channels import create_app_channels


_app_generators = [create_app_channels]


def register_app_generator(generator):
    if generator not in _app_generators:
        _app_generators.append(generator)


def make_sdk(apply_changes=True, quiet=False, force=False):
    print("Generating RxDjango SDK")
    check()

    def log(msg):
        if not quiet:
            print(msg)

    installed_apps = sorted({config.name.split('.')[0] for config in apps.get_app_configs()})

    changed = False

    for app in installed_apps:
        for generator in _app_generators:
            diff = generator(app, apply_changes, force)
            if diff:
                changed = True
                log(diff)

    return changed


def check():
    if not getattr(settings, 'RX_FRONTEND_DIR', None):
        raise ImproperlyConfigured(
            "settings.RX_FRONTEND_DIR is not set. Configure it with a folder "
            "inside your react application."
        )
