# Proposal: routed-list-delivery

## Why

Cycle 1 (`static-queryset-lists`, archived 2026-07-16) shipped the static
list tier: snapshot plus updates and deletes to known rows. A row created
after the snapshot — or updated *into* a list the connection watches —
never appears until rebind, because no consumer has any relationship to
it. ADR-0018 answers this with Router declarations: explicit delivery
dimensions (`db_index`-style), `publish(instance)` on the writer side
meeting `subscribe(channel)` on the bind side, replacing v0's
per-consumer `is_visible`/`auto_update` scans. This change makes queryset
lists live.

## What Changes

- `rx.model(Serializer(many=True), routing=...)` accepts a **Router** —
  `publish(instance)` / `subscribe(channel)` — with sugar forms: a column
  string (`routing='project_id'` → `ColumnRouter`) and the explicit
  firehose `BroadcastRouter`. `routing=None` is a declaration-time error;
  omitted routing keeps cycle 1's static tier unchanged. `None` is never
  a group value: filtered from whatever either side returns.
- **Lifecycle delivery** through dimension groups: creations broadcast to
  `publish(row)`; updates to `publish(old) ∪ publish(new)` — the old side
  is the stateless leave signal — via a narrow pre-image read of only the
  Router's input columns, inside the existing atomic block, skipped when
  `update_fields` cannot affect them; deletes send the tombstone to
  `publish(row)`. Same dimension declared many times dedupes to one group
  set.
- **Registration at import + autodiscovery**: routing declarations
  register when the channel module is imported; the framework's
  `AppConfig.ready()` autodiscovers `channels.py` in every process type
  (web, workers, management commands) — a writer that skips it silently
  under-broadcasts, so discovery is framework-owned, not app wiring.
- **Consumer bind**: `subscribe(channel)` runs at bind (a bind-time
  snapshot); the consumer joins the dimension groups, relays row events
  tagged with the field, and MAY drop residual-failing *creations* as a
  bandwidth optimization — never updates. A `rebind(field)` lever re-runs
  subscribe and re-snapshots.
- **Client**: the bind descriptor marks routed fields live; for a live
  field the membership basis *grows* when a full-layer anchor row arrives
  passing the descriptor's conditions (enter), and cycle 1's
  condition-failure handling already provides the leave edge. Static
  fields keep the never-grow rule. Protocol version 0.3.0 → 0.4.0.
- Example app + docs page + Playwright e2e for live lists (creation
  appears, dimension move leaves/enters, two connections on different
  dimension values stay isolated).

Out of scope (recorded future work, per ADR-0018/0019): residual-traffic
digest (Bloom filter), index eviction, pagination, delta reconnect,
cascade-delete emission, non-local-`publish` frame annotation, and
removing the per-instance-group redundancy for routed anchors (v1 relies
on `_v` idempotence to make duplicate delivery safe).

## Capabilities

### New Capabilities

- `list-routing`: the Router declaration surface (class form, column
  sugar, broadcast singleton, `None` filtering, declaration-time
  validation), lifecycle delivery through dimension groups (create /
  update with pre-image / delete), import-time registration with
  framework-owned autodiscovery, and the `rebind` lever.

### Modified Capabilities

- `queryset-lists`: the routed tier — `routing=` on the field makes the
  list live: basis grows from qualifying full-layer events, leave rides
  the old-side update frame, consumers may drop residual-failing
  creations; the static tier's semantics are unchanged.
- `wire-protocol`: the `q` descriptor gains a live marker; ready-frame
  protocol version becomes `0.4.0`.
- `reactive-models`: committed writes additionally broadcast to the
  routed dimension groups registered for the model (with the pre-image
  read for updates); per-instance group delivery is unchanged.

## Impact

- `packages/model/src/rxdjango_model/` — Router classes, routing
  registry, `ReactiveModel.save()`/`delete()` broadcast path (pre-image
  read), field declaration validation.
- `packages/core/src/rxdjango/` — consumer group joins at bind, relay
  tagging, creation-drop optimization, `rebind`, autodiscovery in
  `AppConfig.ready()`, protocol version.
- `packages/react/src/` — live-marker handling in membership derivation
  (basis growth); no new transport or codegen surface.
- `examples/backend` / `examples/frontend` / `docs/examples` — routed
  list example with e2e.
- ADRs governing this change: 0018 (Routers, doctrine, static/live
  boundary), 0019 (derivation, coverage), 0013 (write path the broadcasts
  extend), 0016 (consumer relay composition).
