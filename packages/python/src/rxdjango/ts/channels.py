import importlib
import inspect
import json
import os
import types
import typing

from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ..actions import list_actions
from ..channels import ContextChannel
from . import header


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

    endpoints = _discover_endpoints(app)
    content = _render_module(app, channels, endpoints)

    ts_dir = os.path.join(settings.RX_FRONTEND_DIR, app)
    ts_path = os.path.join(ts_dir, f'{app}.channels.ts')

    existing = None
    if os.path.exists(ts_path):
        with open(ts_path, 'r') as fh:
            existing = fh.read()
        if not force and existing.split('\n')[2:] == content.split('\n')[2:]:
            return None

    if not apply_changes:
        return f'Would write {ts_path}'

    os.makedirs(ts_dir, exist_ok=True)
    with open(ts_path, 'w') as fh:
        fh.write(content)

    return f'Wrote {ts_path}'


def _discover_endpoints(app):
    """Walk the project's ASGI routing and return {ContextChannel subclass: endpoint_path}.

    The endpoint is the URL pattern as a string with a leading slash, suitable
    for concatenation with a base URL like 'ws://host:port'.
    """
    routes = _list_consumer_patterns(app)
    endpoints = {}
    for route in routes:
        consumer_class = getattr(route.callback, 'consumer_class', None)
        if consumer_class is None:
            continue
        channel_cls = getattr(consumer_class, 'context_channel_class', None)
        if channel_cls is None:
            continue
        pattern = str(route.pattern)
        if not pattern.startswith('/'):
            pattern = '/' + pattern
        endpoints[channel_cls] = pattern
    return endpoints


def _get_root_routing():
    asgi_app = getattr(settings, 'ASGI_APPLICATION', None)
    if not asgi_app:
        return None
    module_name, app_name = asgi_app.rsplit('.', 1)
    module = importlib.import_module(module_name)
    return getattr(module, app_name, None)


def _list_consumer_patterns(app_name, pattern_list=None, router=None):
    if pattern_list is None:
        pattern_list = []
        router = _get_root_routing()
        if router is None:
            return pattern_list

    inner = getattr(router, 'application', None)
    if inner is not None:
        router = inner

    if isinstance(router, ProtocolTypeRouter):
        websocket_router = router.application_mapping.get('websocket')
        if websocket_router is not None:
            _list_consumer_patterns(app_name, pattern_list, websocket_router)
    elif isinstance(router, URLRouter):
        for route in router.routes:
            callback = route.callback
            consumer_class = getattr(callback, 'consumer_class', None)
            if consumer_class is None:
                if isinstance(route, URLRouter):
                    _list_consumer_patterns(app_name, pattern_list, route)
                continue
            channel_cls = getattr(consumer_class, 'context_channel_class', None)
            if channel_cls is None:
                continue
            if channel_cls.__module__.startswith(f'{app_name}.'):
                pattern_list.append(route)

    return pattern_list


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


def _render_module(app, channels, endpoints):
    socket_url = getattr(settings, 'RX_WEBSOCKET_URL', None)
    if not socket_url:
        raise ImproperlyConfigured(
            "settings.RX_WEBSOCKET_URL is not set. Set it to a JavaScript "
            "expression evaluating to the websocket base URL of your backend "
            "(e.g. \"'ws://localhost:8000'\" or "
            "\"process.env.REACT_APP_WS_URL\")."
        )

    lines = header(
        app,
        f'Based on all ContextChannel subclasses in {app}.channels',
    )
    lines.extend([
        '',
        "import { ContextChannel } from '@rxdjango/react';",
        '',
        f'const SOCKET_URL = {socket_url};',
        '',
    ])
    for channel_cls in channels:
        endpoint = endpoints.get(channel_cls)
        lines.extend(_render_class(channel_cls, endpoint))
        lines.append('')
    return '\n'.join(lines)


def _render_class(channel_cls, endpoint):
    lines = [
        f'export class {channel_cls.__name__} extends ContextChannel {{',
        '',
    ]
    if endpoint is not None:
        lines.append(f'  protected endpoint: string = {json.dumps(endpoint)};')
        lines.append('  protected baseURL: string = SOCKET_URL;')
        lines.append('')
    for field_name, rx_field in channel_cls._rx_fields.items():
        ts_type = _ts_type(rx_field.type)
        if rx_field.has_default:
            literal = _ts_literal(rx_field.default)
            if literal is not None:
                lines.append(f'  {field_name}: {ts_type} = {literal};')
                continue
        if 'null' not in [p.strip() for p in ts_type.split('|')]:
            raise ValueError(
                f"Field '{field_name}' on {channel_cls.__name__} has no default value; "
                f"declare it as Optional (include None in the type) so it can be initialized as null."
            )
        lines.append(f'  {field_name}: {ts_type} = null;')
    for method in list_actions(channel_cls):
        lines.append('')
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
        f'  {method.__name__} = async ({params_str}) => {{',
        f"    return await this.rx.callAction('{method.__name__}', [{forwarded_str}]);",
        '  };',
    ]
