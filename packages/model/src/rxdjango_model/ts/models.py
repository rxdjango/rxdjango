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
    from the flat array of layers sent over the wire. A ``many=True`` field
    additionally carries ``many: true`` (design D6), which the runtime uses
    to route the field through membership derivation instead of the
    single-anchor rebuild.
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
            rx_field.many,
        ))
    if not entries:
        return []

    lines = ['protected _modelFields: Record<string, {']
    lines.append('    anchor: string;')
    lines.append('    model: Record<string, Record<string, string>>;')
    lines.append('    many?: boolean;')
    lines.append('  }> = {')
    for field_name, anchor, model_map, many in entries:
        lines.append(f'    {json.dumps(field_name)}: {{')
        lines.append(f'      anchor: {json.dumps(anchor)},')
        if many:
            lines.append('      many: true,')
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
    # Only anchor serializers appear as identifiers in the channels file
    # (field declarations); nested types are referenced there by _type
    # string literals only, and importing them trips no-unused-vars.
    anchors = []
    for channel_cls in channels:
        for rx_field in channel_cls._rx_fields.values():
            if isinstance(rx_field, RxModelField):
                if rx_field.serializer_class not in anchors:
                    anchors.append(rx_field.serializer_class)
    if not anchors:
        return []
    names = ', '.join(sorted(interface_name(cls) for cls in anchors))
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
    if _any_relation_field(serializers_used):
        lines.append('')
        lines.append("import type { Unloaded } from '@rxdjango/react';")
    lines.append('')
    for serializer_class in serializers_used:
        lines.extend(_render_interface(serializer_class))
        lines.append('')
    if lines[-1] == '':
        lines.pop()
    return '\n'.join(lines)


def _any_relation_field(serializers_used):
    for serializer_class in serializers_used:
        try:
            instance = serializer_class()
        except Exception:
            continue
        for field in instance.fields.values():
            if _nested_serializer_class(field) is not None:
                return True
    return False


def _render_interface(serializer_class):
    lines = [f'export interface {interface_name(serializer_class)} {{']
    # Client-injected discriminant (design D5): honest against `Unloaded`,
    # since the server never sends this field -- `StateBuilder` sets it on
    # every rebuilt instance, so `if (x._loaded)` narrows with no cast.
    lines.append('  _loaded: true;')
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
        # Always a nested-serializer list here (state_model.py's `_build_child`
        # is the only producer of `many=True` relation fields), so the union
        # from the BaseSerializer branch below always needs the parens --
        # `X | Unloaded[]` would parse as `X | (Unloaded[])`.
        return f'({_serializer_field_ts_type(field.child)})[]'
    if isinstance(field, serializers.ListField):
        return f'{_serializer_field_ts_type(field.child)}[]'
    if isinstance(field, serializers.DictField):
        return 'Record<string, unknown>'
    # `MultipleChoiceField` subclasses `ChoiceField` but serializes to a
    # set/list of choices, not one -- excluded here so it falls through to
    # the generic `any` rather than being (wrongly) typed as one literal.
    if isinstance(field, serializers.ChoiceField) and not isinstance(
        field, serializers.MultipleChoiceField,
    ):
        return _choice_field_ts_type(field)
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
        # Relation slot: discriminated union with the unloaded stub shape
        # (design D5) -- partial state during delivery is expressed in the
        # types themselves, no cast needed.
        return f'{interface_name(field.__class__)} | Unloaded'
    return 'any'


def _choice_field_ts_type(field):
    """A `ChoiceField`'s TS type is the literal union of its choice keys --
    string choices become `'a' | 'b'`, integer choices `1 | 2`, and a
    serializer mixing both a union of both -- rather than `any`, so a
    `choices=` model field carries its exact value set across to the
    frontend. `allow_blank` folds in `''` here; `allow_null`'s `| null` is
    added by the caller (`_serializer_field_ts_type`), same as for every
    other field type.
    """
    literals: list[str] = []
    seen: set[str] = set()

    def add(literal: str) -> None:
        if literal not in seen:
            seen.add(literal)
            literals.append(literal)

    for key in field.choices.keys():
        if isinstance(key, bool):
            add('true' if key else 'false')
        elif isinstance(key, (int, float)):
            add(repr(key))
        else:
            add(_ts_string_literal(str(key)))

    if getattr(field, 'allow_blank', False):
        add(_ts_string_literal(''))

    if not literals:
        return 'never'
    return ' | '.join(literals)


def _ts_string_literal(value: str) -> str:
    # Single-quoted, matching this codebase's TS literal convention
    # (rxdjango.ts.channels._ts_literal).
    escaped = value.replace('\\', '\\\\').replace("'", "\\'")
    return f"'{escaped}'"
