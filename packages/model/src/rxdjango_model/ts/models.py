from __future__ import annotations

import json
import os

from django.conf import settings
from rest_framework import relations, serializers

from rxdjango.sdk import register_app_generator
from rxdjango.ts import header
from rxdjango.ts.channels import (
    find_channels,
    register_channel_extras_resolver,
    register_field_ts_type_resolver,
    register_module_import_resolver,
)

from rxdjango_model.fields import RxModelField


def install_typescript_hooks() -> None:
    register_field_ts_type_resolver(resolve_model_field_ts_type)
    register_module_import_resolver(resolve_model_imports)
    register_channel_extras_resolver(resolve_channel_extras)
    register_app_generator(create_app_models)


def resolve_channel_extras(channel_cls):
    """Emit a ``_modelFields`` map for each rx.model field on the channel.

    The frontend ``StateBuilder`` uses this map to rebuild a nested instance
    from the flat array of layers sent over the wire.
    """
    entries = []
    for field_name, rx_field in channel_cls._rx_fields.items():
        if not isinstance(rx_field, RxModelField):
            continue
        state_model = rx_field.state_model
        if state_model is None:
            continue
        entries.append((
            field_name,
            state_model.instance_type,
            state_model.frontend_model(),
        ))
    if not entries:
        return []

    lines = ['protected _modelFields: Record<string, {']
    lines.append('    anchor: string;')
    lines.append('    model: Record<string, Record<string, string>>;')
    lines.append('  }> = {')
    for field_name, anchor, model_map in entries:
        lines.append(f'    {json.dumps(field_name)}: {{')
        lines.append(f'      anchor: {json.dumps(anchor)},')
        lines.append('      model: {')
        for type_name, relations in model_map.items():
            rels = ', '.join(
                f'{json.dumps(k)}: {json.dumps(v)}' for k, v in relations.items()
            )
            lines.append(f'        {json.dumps(type_name)}: {{ {rels} }},')
        lines.append('      },')
        lines.append('    },')
    lines.append('  };')
    return lines


def create_app_models(app, apply_changes=True, force=False):
    serializers_used = _collect_app_serializers(app)
    if not serializers_used:
        return None

    content = _render_models_module(app, serializers_used)
    ts_dir = os.path.join(settings.RX_FRONTEND_DIR, app)
    ts_path = os.path.join(ts_dir, f'{app}.models.ts')

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


def resolve_model_field_ts_type(rx_field):
    if not isinstance(rx_field, RxModelField):
        return None
    name = interface_name(rx_field.serializer_class)
    if rx_field.many:
        name = f'{name}[]'
    return f'{name} | null'


def resolve_model_imports(app, channels):
    serializers_used = _collect_serializers(channels)
    if not serializers_used:
        return []
    names = ', '.join(sorted(interface_name(cls) for cls in serializers_used))
    return [f"import type {{ {names} }} from './{app}.models';"]


def interface_name(serializer_class):
    name = serializer_class.__name__
    suffix = 'Serializer'
    if name.endswith(suffix):
        name = name[:-len(suffix)]
    return name


def _collect_app_serializers(app):
    return _collect_serializers(find_channels(app))


def _collect_serializers(channels):
    seen = set()
    serializers_used = []

    def visit(serializer_class):
        if serializer_class in seen:
            return
        seen.add(serializer_class)
        serializers_used.append(serializer_class)
        try:
            instance = serializer_class()
        except Exception:
            return
        for field in instance.fields.values():
            child_cls = _nested_serializer_class(field)
            if child_cls is not None:
                visit(child_cls)

    for channel_cls in channels:
        for rx_field in channel_cls._rx_fields.values():
            if not isinstance(rx_field, RxModelField):
                continue
            visit(rx_field.serializer_class)
    return serializers_used


def _nested_serializer_class(field):
    if isinstance(field, serializers.ListSerializer):
        return type(field.child)
    if isinstance(field, serializers.BaseSerializer):
        return type(field)
    return None


def _render_models_module(app, serializers_used):
    lines = header(
        app,
        f'Based on serializers used by {app}.channels',
    )
    lines.append('')
    for serializer_class in serializers_used:
        lines.extend(_render_interface(serializer_class))
        lines.append('')
    if lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def _render_interface(serializer_class):
    lines = [f'export interface {interface_name(serializer_class)} {{']
    serializer = serializer_class()
    for field_name, field in serializer.fields.items():
        lines.append(f'  {field_name}: {_serializer_field_ts_type(field)};')
    lines.append('}')
    return lines


def _serializer_field_ts_type(field):
    nullable = getattr(field, 'allow_null', False)
    ts_type = _serializer_field_base_ts_type(field)
    if nullable and 'null' not in [part.strip() for part in ts_type.split('|')]:
        ts_type = f'{ts_type} | null'
    return ts_type


def _serializer_field_base_ts_type(field):
    if isinstance(field, serializers.ListSerializer):
        return f'{_serializer_field_ts_type(field.child)}[]'
    if isinstance(field, serializers.ListField):
        return f'{_serializer_field_ts_type(field.child)}[]'
    if isinstance(field, serializers.DictField):
        return 'Record<string, unknown>'
    if isinstance(field, serializers.BooleanField):
        return 'boolean'
    if isinstance(field, serializers.IntegerField):
        return 'number'
    if isinstance(field, (serializers.FloatField, serializers.DecimalField)):
        return 'number'
    if isinstance(field, relations.PrimaryKeyRelatedField):
        return 'number'
    if isinstance(field, (
        serializers.CharField,
        serializers.EmailField,
        serializers.RegexField,
        serializers.SlugField,
        serializers.URLField,
        serializers.UUIDField,
        serializers.FilePathField,
        serializers.IPAddressField,
        serializers.DateTimeField,
        serializers.DateField,
        serializers.TimeField,
        serializers.DurationField,
    )):
        return 'string'
    if isinstance(field, serializers.BaseSerializer):
        return interface_name(field.__class__)
    return 'any'
