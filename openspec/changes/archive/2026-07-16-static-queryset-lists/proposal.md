# Proposal: static-queryset-lists

## Why

`rx.model(Serializer(many=True))` crashes at class creation today, and even
server-side delivery would land on a client with no list story: `StateBuilder`
latches onto a single anchor, `state` is `T | null`, and an empty list is
indistinguishable from an unloaded one. ADR-0019 defines the list contract —
a bare queryset assigned in `on_connect`, membership derived client-side —
and ADR-0018 defines its zero-cost tier: **omitted routing means a static
list** (snapshot plus updates and deletes to known rows, no new-row
delivery). This change builds that static tier end to end; the routed tier
(Routers, live new-row delivery, ADR-0018) is a follow-up change layered on
top of it.

## What Changes

- `rx.model(Serializer(many=True))` compiles at class creation: anchor
  becomes a list anchor, generated `state` type becomes `T[]`.
- Assigning a queryset to a `many=True` field in `on_connect` snapshots it
  through the existing layered walk (ADR-0016); reassignment supersedes.
- **Bind-time introspection**: the framework walks `queryset.query.where`
  and `order_by`; every condition must be frame-evaluable from serializer
  fields and every ordering column must be a serializer field — anything
  else fails loudly at bind, naming the condition. (The Router-coverage
  alternative arrives with the routed tier.)
- A **bind descriptor** travels to the client at (re)bind: conditions,
  ordering, snapshot marker. New wire surface; protocol version bumps
  0.2.0 → 0.3.0.
- **Client-derived membership**: `StateBuilder` grows an anchor *set* per
  list field; membership is a pure function — rows in the index passing the
  descriptor's conditions, sorted by its ordering spec. Django lookup
  semantics are matched per supported lookup. `state` is `null` before the
  first snapshot frame, `[]` after an empty one, `T[]` thereafter. `_del`
  tombstones detach through the existing path; a mutable residual column
  flipping toggles membership via an ordinary update frame.
- **Rebind is authoritative**: on any (re)bind the snapshot resets the
  membership basis — index rows absent from it are demoted to non-member
  cache with watermarks retained, re-entering only via a fresh full layer.
- **Reconnect**: persistent socket with backoff (ported from v0's
  `PersistentWebsocket`); a reconnect is a rebind over a warm index,
  idempotent by watermarks.
- Example app(s) + docs page(s) + Playwright e2e for the static list tier.

Out of scope (deliberately, per the two-cycle split): Routers and all of
ADR-0018's delivery machinery, Router-coverage in bind validation, index
eviction, pagination, delta reconnect.

## Capabilities

### New Capabilities

- `queryset-lists`: the static queryset list tier — bare-queryset
  interface on `many=True` fields, bind-time condition/ordering
  introspection with loud unsupported-condition failures, the bind
  descriptor, client-derived membership (condition evaluation, ordering,
  null/`[]`/`T[]` semantics, tombstone detach), and the
  rebind-authoritative membership reset.

### Modified Capabilities

- `model-state`: declaration accepts `many=True` serializer instances
  (list anchors) at class creation; queryset assignment/reassignment
  semantics extended to list fields.
- `wire-protocol`: the bind descriptor frame/slot is added under the
  short-key rule; ready-frame protocol version becomes `0.3.0`.
- `frontend-codegen`: `many=True` anchor fields generate `T[]` state
  types (`null` before first snapshot).
- `react-client`: the connection becomes a persistent socket with backoff;
  reconnect performs an authoritative rebind over the warm index.

## Impact

- `packages/core/src/rxdjango/` — state-model compilation
  (`_disassemble_nested` crash), consumer bind path, queryset
  introspection, descriptor emission, protocol version.
- `packages/react/src/` — `StateBuilder` (anchor sets, membership
  derivation, rebind reset), `ContextChannel`, new persistent-websocket
  transport; TS unit tests for lookup parity.
- `packages/core/src/rxdjango/ts/` and model-package codegen hooks —
  `T[]` generated types.
- `examples/backend` / `examples/frontend` / `docs/examples` — new static
  list example(s) with e2e coverage.
- ADRs governing this change: 0016 (layered walk, supersede), 0018 (static
  tier definition), 0019 (interface, derivation, rebind, reconnect),
  0013/0014 (versions and watermarks, reused unchanged).
