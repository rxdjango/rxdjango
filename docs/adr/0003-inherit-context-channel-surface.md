# 0003. Inherit the ContextChannel surface from rxdjango v0.0.x

- **Date:** 2026-05-11
- **Deciders:** Luis Fagundes

## Context

RxDjango v0.0.x already shipped a working developer surface for declaring a
reactive backend endpoint and consuming it from a typed TypeScript client.
The rebuild has to decide, for each piece of that surface, whether to keep
it, redesign it, or drop it. Doing this piecemeal across many ADRs would
fragment a single coherent answer to the question *"what does a v0.1
RxDjango app look like to the developer who writes it?"*

## Decision

The v0.1 rebuild inherits the following developer-facing surface from
rxdjango v0.0.x, with internals refactored onto the ADR-0002 envelope but
the externally observable API preserved:

- **`ContextChannel` base class and its metaclass.** Developers subclass
  `ContextChannel` and declare reactive fields and `@action` methods on the
  class body. The metaclass collects these at class-definition time and
  registers them for codegen and runtime dispatch.
- **`@action` decorator.** Methods marked `@action` are exposed as
  client-callable RPCs. The decorator's user-facing signature is preserved
  from v0.0.x; dispatch is rewired onto the ADR-0002 `ac` envelope.
- **Django Channels `AsyncWebsocketConsumer` wiring.** Each connection
  instantiates one `ContextChannel`; the consumer is the bridge between
  Django Channels and the channel instance.
- **URL routing pattern.** A `ContextChannel` subclass is mounted at a
  WebSocket URL via the project's routing configuration, the same way as
  in v0.0.x.
- **`makefrontend` management command and the generated-SDK pattern.**
  The command discovers `ContextChannel` subclasses in the project and
  emits a `*.channels.ts` file per app. The generated class mirrors the
  server-side channel one-for-one: declared fields become typed properties,
  `@action` methods become typed methods that round-trip through the
  WebSocket. The DO-NOT-EDIT generated-SDK pattern — where the TypeScript
  surface is derived from the Python surface and the developer never
  hand-writes the boundary — is itself part of what is inherited.

## Dropped from v0.0.x

These v0.0.x mechanisms are explicitly *not* planned to be included in
new architecture:

- **MongoDB caching layer.** Reactive state will not be persisted into
  Mongo as part of the core functionality
- **The "anchor" concept.** The v0.0.x notion of an anchor object that
  rooted a channel's state graph does not survive into v0.1.
- **Nested authentication.** v0.0.x's per-nested-serializer auth checks
  are removed; authentication will live at the channel boundary only.

## Deferred for redesign in later ADRs

These v0.0.x capabilities are out of scope for ADR-0003 but will be
re-architected — not simply ported — in subsequent ADRs:

- **Serializer-driven reactive graphs.** The mechanism by which a DRF
  serializer becomes a reactive, diffable subtree.
- **Signal-driven invalidation.** How ORM changes propagate into
  reactive updates.

Each of these will get its own ADR rather than being inherited wholesale.

## References

- ADR-0002 — Core WebSocket protocol envelope (the transport this
  surface is refactored onto).
- `rxdjango-0/rxdjango/` — prior-art source for the inherited pieces.
- `examples/backend/counter/channels.py` and
  `examples/frontend/src/app/rx/counter/counter.channels.ts` — the
  minimal end-to-end demonstration of the inherited surface.
