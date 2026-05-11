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

The counter example (`examples/backend/counter/channels.py` +
`examples/frontend/.../counter.channels.ts`) is the smallest end-to-end
demonstration of that surface: a Python class subclassing `ContextChannel`,
methods marked with `@action`, a Django Channels consumer mounted at a ws
URL, and a generated `*.channels.ts` SDK with a class whose methods mirror
the server-side actions one-for-one. Every piece of that flow except the
field-declaration syntax (`rx[type](default)`, deferred to ADR-0004) is
recognisable from v0.0.x.

This ADR records the decision to keep that surface. It does not relitigate
the v0.0.x design; it pins which v0.0.x pieces are load-bearing for v0.1,
which are being dropped, and which are being deferred for redesign in
later ADRs. Subsequent ADRs (field syntax, reactive serializers, broadcast)
build on top of this surface rather than alongside an alternative.

The wire format underneath the consumer is *not* inherited — ADR-0002
already replaced it with a new envelope. This ADR is about the
developer-facing API surface; the transport beneath it is the new one.

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

## Consequences

### Positive
- The v0.1 developer story is anchored in a surface that has already been
  validated in production use of v0.0.x. The rebuild is not gambling on an
  untested DX.
- Naming and shape (`ContextChannel`, `@action`, `makefrontend`,
  `*.channels.ts`) are preserved, so v0.0.x users have a recognisable
  migration target and existing documentation/examples remain instructive
  for the surface even where internals have changed.
- Subsequent ADRs (field syntax in ADR-0004, reactive serializers,
  broadcast) have a fixed substrate to build on; they design *into* this
  surface rather than around it.
- Locking the surface here lets the implementation work proceed without
  re-opening "should this even be a class?" each time a new feature lands.

### Negative / Trade-offs
- Inheriting the surface inherits its constraints. Choices like
  "one `ContextChannel` instance per connection" or "actions are methods
  on the channel class" are now load-bearing for v0.1 and harder to
  revisit without a superseding ADR.
- API-surface fidelity to v0.0.x can mask the fact that the internals are
  a rewrite — bug reports and Stack Overflow answers that worked against
  v0.0.x internals will not transfer.
- Anything kept "because v0.0.x had it" risks being kept past its
  usefulness; the rebuild should still feel free to drop inherited pieces
  in later ADRs when they no longer earn their place.

### Neutral
- The reactive-field declaration syntax is *not* decided here. v0.0.x's
  approach is treated as prior art for ADR-0004 to react to, not as
  inherited.
- The wire envelope under the consumer is the ADR-0002 envelope, not the
  v0.0.x ad-hoc format. "Surface preserved, internals refactored" is the
  rule.

## Dropped from v0.0.x

These v0.0.x mechanisms are explicitly *not* coming back, in any later
ADR:

- **MongoDB caching layer.** Reactive state will not be persisted into
  Mongo.
- **Redis syncing.** Cross-process state synchronisation via Redis is
  removed.
- **The "anchor" concept.** The v0.0.x notion of an anchor object that
  rooted a channel's state graph does not survive into v0.1.
- **Nested authentication.** v0.0.x's per-nested-serializer auth checks
  are removed; authentication will live at the channel boundary only.

## Deferred for redesign in later ADRs

These v0.0.x capabilities are out of scope for ADR-0003 but will be
re-architected — not simply ported — in subsequent ADRs:

- **`rx.model` / serializer-driven reactive graphs.** The mechanism by
  which a DRF serializer becomes a reactive, diffable subtree.
- **Signal-driven invalidation.** How ORM changes propagate into
  reactive updates.
- **Broadcast across connections.** Multi-subscriber fan-out so that
  multiple clients viewing the same channel state see each other's
  updates.

Each of these will get its own ADR rather than being inherited wholesale.

## Alternatives Considered

### Option A: Redesign the surface from scratch
Treat v0.0.x purely as background reading and design a new top-level API
for v0.1. Rejected because the v0.0.x surface — `ContextChannel`,
`@action`, generated `*.channels.ts` — is the strongest part of the prior
art and the part users were happiest with; the pain points were in the
internals (Mongo, Redis, anchors, nested auth), not in the developer's
class body. Throwing out the surface would discard the framework's
clearest existing win.

### Option B: Port v0.0.x as-is, internals and all
Keep the surface *and* the v0.0.x internals (Mongo cache, Redis sync,
anchor, nested auth, ad-hoc wire format). Rejected because the rebuild's
motivation is precisely to shed those internals; preserving them would
make this rebuild a no-op.

### Option C: Defer the surface decision until each subsystem ADR
Let each later ADR (field syntax, reactive serializers, broadcast) decide
its own slice of the developer surface as it lands. Rejected because the
surface is interconnected — `@action` only makes sense on a class with a
metaclass; the generated SDK only makes sense given a discovery model for
channels. Deciding these in isolation would produce a surface that
doesn't compose.

## References

- ADR-0002 — Core WebSocket protocol envelope (the transport this
  surface is refactored onto).
- `rxdjango-0/rxdjango/` — prior-art source for the inherited pieces.
- `examples/backend/counter/channels.py` and
  `examples/frontend/src/app/rx/counter/counter.channels.ts` — the
  minimal end-to-end demonstration of the inherited surface.
