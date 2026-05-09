from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rxdjango.ts.channels import create_app_channels


def make_sdk(apply_changes=True, quiet=False, force=False):
    print("Generating RxDjango SDK")
    check()

    def log(msg):
        if not quiet:
            print(msg)

    installed_apps = sorted({config.name.split('.')[0] for config in apps.get_app_configs()})

    changed = False

    for app in installed_apps:
        diff = create_app_channels(app, apply_changes, force)
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
