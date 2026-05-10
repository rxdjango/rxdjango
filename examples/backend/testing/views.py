import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.http import FileResponse, Http404

APP_RE = re.compile(r'^[a-z_]+$')
FILENAME_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

BACKEND_FILES = {'channels.py', 'models.py'}

BACKEND_ROOT = Path(settings.BASE_DIR)
FRONTEND_ROOT = Path(settings.BASE_DIR).parent / 'frontend' / 'src' / 'app' / 'rx'


def source(request, app, filename):
    if not APP_RE.match(app) or not FILENAME_RE.match(filename):
        raise Http404()

    if app == 'testing' or not apps.is_installed(app):
        raise Http404()

    if not (BACKEND_ROOT / app).is_dir():
        raise Http404()

    if filename in BACKEND_FILES:
        path = BACKEND_ROOT / app / filename
        content_type = 'text/x-python'
    elif filename == f'{app}.channels.ts':
        path = FRONTEND_ROOT / app / filename
        content_type = 'application/typescript'
    else:
        raise Http404()

    if not path.is_file():
        raise Http404()

    return FileResponse(path.open('rb'), content_type=content_type)
