# Frontend Codegen

## Purpose

`./manage.py makefrontend` generates the typed TypeScript SDK from the declared channels, so type information crosses the Python↔TypeScript boundary without hand-written glue (ADR-0003). Backend packages extend the generator through registered hooks rather than core depending on them (ADR-0011).

## Requirements

### Requirement: makefrontend writes a per-app SDK

The `makefrontend` management command SHALL generate, for every installed app with a `channels` module declaring channels, `<RX_FRONTEND_DIR>/<app>/<app>.channels.ts`. It SHALL raise `ImproperlyConfigured` when `settings.RX_FRONTEND_DIR` is unset, or when `settings.RX_WEBSOCKET_URL` (a JavaScript expression for the socket base URL) is unset while an app has channels to emit.

#### Scenario: Counter app generated

- **WHEN** `makefrontend` runs on a project whose `counter` app declares `CounterChannel`
- **THEN** `<RX_FRONTEND_DIR>/counter/counter.channels.ts` exists and exports `class CounterChannel extends ContextChannel`

### Requirement: Generated channel mirrors the server channel

Each generated class SHALL declare: its `endpoint` discovered from the project's ASGI websocket routing plus `baseURL` from `RX_WEBSOCKET_URL`; one typed property per reactive field, initialized to the server default (a field with no default must be nullable — otherwise generation fails); and one typed async wrapper per `@action`, forwarding positionally through the runtime's action call.

#### Scenario: Fields and actions carried over

- **WHEN** the server channel declares `counter = rx[int](0)` and `@action async def increment(self)`
- **THEN** the generated class has `counter: number = 0;` and an `increment = async () => ...` wrapper

#### Scenario: Endpoint discovered from routing

- **WHEN** the channel is mounted at `path('ws/counter/', CounterChannel.as_asgi())`
- **THEN** the generated class declares `endpoint: string = "/ws/counter/"`

### Requirement: Typed model interfaces per app

For every serializer reachable from an app's `rx.model` fields (transitively through nesting), the generator SHALL emit a TypeScript interface in `<app>/<app>.models.ts` matching the serializer's output shape — the `Serializer` suffix stripped from the name, DRF field types mapped to TypeScript types, `allow_null` adding `| null`. The channels file imports these types for its model-field properties.

#### Scenario: Nested serializers become interfaces

- **WHEN** `UserSerializer` (name, nested company) feeds a `rx.model` field
- **THEN** `nested_model.models.ts` exports `interface User` with `company: Company` and `interface Company`
- **AND** the generated channel declares `user: User | null = null`

### Requirement: Model rebuild metadata is emitted

For a channel with `rx.model` fields, the generated class SHALL carry a `_modelFields` map from field name to its anchor `_type` and relation map, which the client runtime uses to rebuild flat layers into nested instances.

#### Scenario: Relation map in the generated class

- **WHEN** the `user` field's serializer nests a company
- **THEN** the generated `_modelFields.user` maps the user serializer type's `company` field to the company serializer type

### Requirement: Generated files are marked and regeneration is idempotent

Generated files SHALL open with a header naming the source and stating DO NOT EDIT. Re-running `makefrontend` SHALL leave files whose generated content is unchanged untouched (the header timestamp is ignored in the comparison). `--dry-run` reports what would be written without writing; `--force` rewrites regardless. The command exits 0 when everything is up to date and 1 when changes were made or would be made.

#### Scenario: No-op rerun

- **WHEN** `makefrontend` runs twice with no channel changes in between
- **THEN** the second run rewrites nothing and exits 0

### Requirement: Backend packages extend generation through hooks

The generator SHALL expose registration hooks — a field TS-type resolver, a module import resolver, a channel class-body extras resolver, and an app-level generator — so backend packages add their output without core importing them. The `rxdjango_model` package uses exactly these hooks to emit model-field types, model imports, `_modelFields`, and the models file.

#### Scenario: Model package plugs in

- **WHEN** `rxdjango_model` is installed and `makefrontend` runs
- **THEN** channels with `rx.model` fields gain typed model properties, imports, and `_modelFields` without any model-specific code in core's generator
