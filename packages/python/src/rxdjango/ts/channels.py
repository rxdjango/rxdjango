import importlib
import inspect
import os
import types
import typing

from django.conf import settings

from ..actions import list_actions
from ..channels import ContextChannel


TYPE_MAP = {
    int: 'number',
    str: 'string',
    bool: 'boolean',
    float: 'number',
    type(None): 'null',
}


def _ts_type(py_type):
    origin = typing.get_origin(py_type)
    if origin is typing.Union or origin is types.UnionType:
        parts = [_ts_type(arg) for arg in typing.get_args(py_type)]
        seen = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return ' | '.join(seen)
    return TYPE_MAP.get(py_type, 'any')


def _ts_literal(value):
    if value is None:
        return 'null'
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace("'", "\\'")
        return f"'{escaped}'"
    if isinstance(value, (int, float)):
        return repr(value)
    return None


def create_app_channels(app, apply_changes=True, force=False):
    """Generate {RX_FRONTEND_DIR}/{app}/{app}.channels.ts for an app.

    Scans the app's channels module for ContextChannel subclasses and emits
    a TypeScript class per channel, declaring a typed field for each rx[type]
    field. Returns a diff string if changes were made (or would be made when
    apply_changes is False), otherwise None.
    """
    channels = _find_channels(app)
    if not channels:
        return None

    content = _render_module(channels)

    ts_dir = os.path.join(settings.RX_FRONTEND_DIR, app)
    ts_path = os.path.join(ts_dir, f'{app}.channels.ts')

    existing = None
    if os.path.exists(ts_path):
        with open(ts_path, 'r') as fh:
            existing = fh.read()
        if not force and existing == content:
            return None

    if not apply_changes:
        return f'Would write {ts_path}'

    os.makedirs(ts_dir, exist_ok=True)
    with open(ts_path, 'w') as fh:
        fh.write(content)

    return f'Wrote {ts_path}'


def _find_channels(app):
    try:
        module = importlib.import_module(f'{app}.channels')
    except ModuleNotFoundError:
        return []

    found = []
    for name in dir(module):
        obj = getattr(module, name)
        if not isinstance(obj, type):
            continue
        if obj is ContextChannel:
            continue
        if not issubclass(obj, ContextChannel):
            continue
        if obj.__module__ != module.__name__:
            continue
        found.append(obj)
    return found


def _render_module(channels):
    lines = [
        "import { ContextChannel } from '@rxdjango/react';",
        '',
    ]
    for channel_cls in channels:
        lines.extend(_render_class(channel_cls))
        lines.append('')
    return '\n'.join(lines)


def _render_class(channel_cls):
    lines = [f'export class {channel_cls.__name__} extends ContextChannel {{']
    for field_name, rx_field in channel_cls._rx_fields.items():
        ts_type = _ts_type(rx_field.type)
        if rx_field.has_default:
            literal = _ts_literal(rx_field.value)
            if literal is not None:
                lines.append(f'  {field_name}: {ts_type} = {literal};')
                continue
        lines.append(f'  {field_name}: {ts_type};')
    for method in list_actions(channel_cls):
        lines.extend(_render_action(method))
    lines.append('}')
    return lines


def _render_action(method):
    hints = typing.get_type_hints(method)
    sig = inspect.signature(method)
    params = []
    forwarded = []
    for name in sig.parameters:
        if name == 'self':
            continue
        ts_type = _ts_type(hints.get(name, type(None)))
        params.append(f'{name}: {ts_type}')
        forwarded.append(name)
    params_str = ', '.join(params)
    forwarded_str = ', '.join(forwarded)
    return [
        f'  async {method.__name__}({params_str}) {{',
        f"    return await this.rx.callAction('{method.__name__}', [{forwarded_str}]);",
        '  }',
    ]
