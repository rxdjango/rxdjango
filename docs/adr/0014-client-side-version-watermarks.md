# 0014. Client-side version watermarks for layer consistency

- **Date:** 2026-05-15
- **Status:** Active
- **Deciders:** Luis Fagundes

> **Implementation note.** The per-layer version described below as `version`
> travels on the wire as `_v` (see ADR-0013). The watermark reconciliation is
> implemented in `StateBuilder.update()` (`packages/react/src/StateBuilder.ts`);
> delete events arrive as `_del`-tagged layers carrying `_v`.

## Context

The `ReactiveModel` base class (see ADR-0013) gives every
reactive row a database-minted, monotonically increasing `version`, and
broadcasts each `(payload, version)` pair from the same atomic write. Deletes
broadcast at `v + 1`. This is the *server* half of the framework's central
invariant — broadcast state matches DB state at the broadcast's version.

ADR-0012 transports `rx.model` nested state as flat, `_type`-tagged layers,
each a self-contained instance keyed `_type:id`, rebuilt into the nested shape
on the client by `StateBuilder`.

To deliver state consistently the server **subscribes to the event stream
before fetching the initial snapshot** — the only ordering that does not miss a
write committed during connection setup (fetch-then-subscribe drops it
entirely). That ordering has two consequences the client must absorb:

1. **The snapshot can be older than queued events.** A row edited between the
   subscribe and the fetch is read by the fetch at its old version, while a
   newer event for that same row is already in the queue.
2. **Layer arrival order is not logical order.** Each flat layer is an
   independent `_type:id` instance on the wire. A `v2` event for a child layer
   can arrive *before* the `v1` snapshot of the anchor that references it — the
   child is, momentarily, an orphan.

The current `StateBuilder.update()` (`packages/react/src/StateBuilder.ts`,
lines 31-40) indexes every incoming layer unconditionally:

```ts
this.index[key] = instance;
```

This is last-write-wins **by arrival order**. Replay consequence 1: the `v2`
event arrives and is indexed; then the `v1` snapshot arrives and *overwrites it
with stale data*. The client is now silently behind the database — the exact
invariant the server-side versioning exists to protect, lost on the client.
A delete is worse: a stale snapshot arriving after the delete event resurrects
a row the database no longer has.

Orphan *storage* is already handled — `StateBuilder` keeps a flat `index` keyed
by `_type:id` and stores every incoming layer regardless of whether its parent
has arrived; `rebuild` splices it in once the anchor is present. What is
missing is not a place to put orphans, but a rule for *which* version of a
layer wins when copies arrive out of order.

## Decision

Every flat layer carries its `version` on the wire, and `StateBuilder`
reconciles layers by version rather than by arrival order.

- **Versioned wire format.** Every flat layer — snapshot layers and event
  layers alike — carries the row's `version`. Delete events carry `v + 1`, as
  minted by the `ReactiveModel` delete path.
- **Per-`_type:id` high-water mark.** `StateBuilder` tracks, for each
  `_type:id` key, the highest `version` it has applied.
- **Discard-by-watermark.** `update()` becomes a conditional merge: an incoming
  layer is applied only if its `version` is strictly greater than the stored
  watermark for its key; a layer with `version ≤` watermark is discarded. A
  late `v1` snapshot racing an already-applied `v2` event is dropped; the `v2`
  state stands.
- **Delete tombstones.** A delete is applied only if its `version` exceeds the
  watermark. The watermark for a deleted key is **retained for the lifetime of
  the connection** as a tombstone, so a stale snapshot of that row arriving
  afterward is `≤` the tombstone and discarded — the row stays deleted.
- **Non-versioned layers.** A layer with no `version` (a non-reactive nested
  `ModelSerializer` flattened into an `rx.model` tree) is always applied. A
  non-reactive model emits no events, so its layer only ever arrives once, in
  the snapshot; there is no race to reconcile and no watermark is kept for it.

The watermark is connection-scoped client state. A reconnect re-subscribes and
re-fetches a fresh snapshot, so watermarks and tombstones start empty again;
cross-reconnect consistency is out of scope for this ADR.

## Consequences

### Positive

- Closes the connect-time race on the client: the client converges to the
  database state regardless of the order in which flat layers arrive.
- Idempotent under re-delivery and reordering — any layer at or below the
  watermark is harmlessly discarded, so duplicate or late delivery cannot
  corrupt state.
- No buffering and no "snapshot complete" signal: each layer self-describes via
  its `version`, and is reconciled the moment it arrives.
- Reuses the existing flat `index` — orphan layers are already stored there;
  this adds only the version metadata and the comparison, not a new structure.

### Negative / Trade-offs

- `StateBuilder` must keep a watermark per `_type:id`, and tombstone watermarks
  for deleted keys persist for the connection's lifetime (one integer per key).
- Each flat layer on the wire grows by one integer.
- A new cross-package invariant: the wire format and `StateBuilder` must stay
  in lockstep with the server's versioning. The server minting the version and
  the client honoring it are a matched pair — neither is correct alone.
- Non-versioned layers are applied unconditionally. This is safe only as long
  as the assumption holds that such layers come from non-reactive models that
  emit no events; a future feature that broadcasts updates for a non-versioned
  layer would reintroduce the race for it.

### Neutral

- The watermark is per-row, matching the per-row version scope of the
  `ReactiveModel` ADR; there is no cross-row ordering to reconcile.
- Watermarks and tombstones are connection-scoped and reset on reconnect, since
  a reconnect re-fetches a fresh snapshot.

## Alternatives Considered

### Option A: Keep last-write-wins, rely on server send order

Leave `update()` as unconditional assignment and have the server send layers in
an order the client can trust.

**Rejected.** The hazard is created by subscribing before fetching — the only
ordering that does not miss a write during connection setup. The snapshot and
the event stream are two independent sources; no send order within either one
can tell the client that a `v1` snapshot layer is older than a `v2` event layer
for the same row. The reconciliation has to happen on the client, by version.

### Option B: Global / channel-level version counter

Use a single monotonically increasing counter for the whole channel instead of
a per-row version, and compare layers against that.

**Rejected.** Versions are per-row — each reactive model row is minted from its
own table's counter (ADR-0013). Rows of different `_type:id`
have no shared, comparable ordering, so a single global counter cannot be
derived from them without a separate sequencing authority the architecture does
not have.

### Option C: Separate orphan store

Keep a structure for orphan layers distinct from the main index, and promote
them once their parent arrives.

**Rejected** — and this was the framing the investigation started from. The
current `StateBuilder` already stores every layer in one flat `index` keyed by
`_type:id`, parent present or not; orphans are not a storage problem. The real
gap is version reconciliation, which a separate store would not address. Adding
one would be a structure with no purpose.

## References

- ADR-0013 — server-side `ReactiveModel`, DB-minted per-row
  `version`, delete events at `v + 1`.
- ADR-0012 — flat-layer wire protocol for `rx.model` nested state.
- `packages/react/src/StateBuilder.ts` — client-side nested rebuild; `update()`
  is the method this ADR changes.
- Replicache sync model (per-row version watermarks):
  https://doc.replicache.dev/concepts/how-it-works
