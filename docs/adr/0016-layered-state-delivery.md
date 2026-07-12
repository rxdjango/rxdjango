# 0016. Layered state delivery and the per-instance cache direction

- **Date:** 2026-07-12
- **Status:** Active
- **Deciders:** Luis Fagundes

## Context

### Where initial-state delivery stands today

When a channel assigns an `rx.model` field, the current pipeline is the worst
of three worlds:

1. **N+1 queries.** `StateModel.serialize_state()`
   (`packages/model/src/rxdjango_model/state_model.py`) walks the instance
   graph lazily — `getattr(inst, field_name)`, `.all()` on managers — with no
   prefetching. For a Project with T tasks (each with an assignee and
   comments), that is roughly `2 + 3T` queries, including duplicate refetches:
   the pk-list serialization and the child recursion each hit the database
   separately for the same rows.
2. **Monolithic delivery.** `serialize_state()` is a generator yielding one
   flat layer at a time — but `RxModelField.serialize()`
   (`packages/model/src/rxdjango_model/fields.py`) exhausts it into a single
   list and enqueues one frame. The client's `state` is `null` until the last
   comment of the last task has been fetched. No first paint, no loaders.
3. **Sync ORM in the event loop.** All of those queries run synchronously
   inside the async consumer context, stalling every other connection on the
   worker.

v0 sat at one coherent point in the design space: incremental delivery from a
per-anchor MongoDB cache, with `{ id, _loaded: false }` stubs as first-class
partial state (pinned by the hand-written v0 suite,
`rxdjango-0/rxdjango-react/src/StateBuilder.test.ts`, not yet ported). The
rebuild currently sits at neither coherent point: it pays incremental's query
pattern and monolithic's latency. An earlier framing of the stub-vs-null
question treated unloaded placeholders as an isolated representation choice;
this ADR resolves it as a consequence of the delivery architecture instead.

### Forces

- **Incremental delivery is a requirement.** Monolithic sending makes
  time-to-first-paint proportional to the deepest, widest branch of the tree.
  State must flush as it is retrieved.
- **A cache is a requirement** — without one the framework re-serializes the
  world from Postgres on every connect. It is future work, but the delivery
  architecture must be built *around* it, not have it bolted on.
- **Nested caching is not viable.** RxDjango exists because caching composed
  structures makes invalidation intractable — one row write invalidates every
  nested structure containing it. Whatever is cached must be invalidatable by
  single-row writes.
- **The N+1 must not become the cached design.** A per-instance cache naively
  read one key at a time would merely relocate the N+1 from Postgres to the
  KV store.
- **Types must stay honest across the Python↔TS boundary** (project north
  star; ADR-0010..0012). Whatever partial state looks like, the generated
  types must describe it without `any` or user-side casts.
- **The query plan must be a compile-time artifact** (ADR-0015): everything
  derivable from the serializer tree is derived at class-creation time. The
  walk this ADR introduces derives its structure — layer order, types per
  layer, relation edges — from the tree once; only the pk sets are runtime
  data.
- ADR-0013 (DB-minted per-row `_v`, broadcast welded to the write) and
  ADR-0014 (subscribe-before-fetch, client-side per-`_type:id` watermarks)
  already define how concurrent writes reconcile with a snapshot. This ADR
  must compose with them, not duplicate them.

### The key structural fact

The flat protocol gives the fetch path something the naive `getattr` walk
throws away: **a parent's flat instance carries its children's pks before the
children are fetched** (`tasks: [1, 2, 3]`, `assignee: 7`). Discovery and
retrieval are separable. Every fetch can therefore be a batch — the set of
keys needed for layer N+1 is fully known once layer N is in hand.

## Decision

Four coupled decisions, one unifying primitive.

### 1. Replace the lazy walk with a pk-first layered walk

`serialize_state` stops traversing Python object attributes. Instead it
executes the StateModel tree as a query plan, breadth-first:

```
layer 1:  Project pk=1                      → 1 query (the anchor)
layer 2:  Task     WHERE pk IN (1, 2, 3)    → 1 query
layer 3:  User     WHERE pk IN (7, 9)       → 1 query
          Comment  WHERE pk IN (...)        → 1 query
```

Each layer is one `pk__in` query per instance type, with the pk set collected
from the previous layer's serialized relation fields. Query count is
**O(edges in the serializer tree)** — independent of row counts. The
StateModel tree *is* the prefetch plan; we execute it ourselves rather than
deriving a `prefetch_related` spec for the ORM. Per ADR-0015, the plan is
compiled at class-creation time.

To-one edges are **not** folded into their parent layer's query via
`select_related`. Every layer — to-one and to-many alike — is resolved the
same way: a pk set per instance type. The fold exists only on the SQL path,
and decision 4 depends on layers keeping a resolver-agnostic shape, servable
from cache (`MGET`) or database (`pk__in`) interchangeably; a folded edge has
no cache-path equivalent. The round trip it would save is already overlapped
by per-layer flush, and under fan-in the JOIN ships duplicated child rows
where the deduped `pk__in` fetch retrieves each distinct child once.

Layer queries run off the event loop (thread executor / `sync_to_async`),
fixing force 3 as a side effect: the loop blocks per batched layer handoff,
not per row.

### 2. Flush per layer

Each completed layer is enqueued immediately as its own frame. The anchor
paints first; depth arrives progressively, parent-before-child by
construction. `RxModelField.serialize()`'s accumulate-everything behavior is
removed. The wire format does not change — the same flat `_type`-tagged
instances (with `_v` per ADR-0013/0014) simply arrive in more, smaller
frames. Frame semantics are explicitly **merge**, reconciled per instance by
watermark (ADR-0014); "one field payload = one complete frame" is dead.

### 3. Represent unloaded children as typed stubs (v0 semantics)

When the client has a parent whose relation lists reference pks that have not
arrived, `StateBuilder` materializes `{ id, _loaded: false }` stubs in those
slots — restoring v0's partial-state semantics, pinned by the hand-written v0
suite. When the real instance arrives, the stub is replaced (reference change
propagating up the parents map, per the identity semantics landed in
`e017d66`).

- **No protocol change.** Stubs are constructed client-side from the pk lists
  the parent layer already carries. The server never sends a stub.
- **Why stubs and not `null`:** delivery is now *always* observably partial
  during load. `null` conflates "explicitly null FK" with "not yet delivered",
  and a `(Task | null)[]` full of nulls gives React nothing to key list rows
  on. The stub carries exactly the key.
- **Type impact:** generated relation types become a discriminated union on
  `_loaded` (exact codegen shape — `Task | Unloaded` vs `_loaded` flag on the
  loaded type — settled at implementation, within ADR-0011's codegen hooks).
  This is a real cost, accepted deliberately: components that care render a
  keyed skeleton; components that don't branch once.
- Stubs carry no `_v`; any real layer replaces a stub unconditionally, and
  watermarks apply only between real layers.

### 4. The cache is a per-instance store, slotted in as a layer resolver

Future work, recorded now as the direction the above is built around:

**Cache unit = wire unit = invalidation unit = the flat instance**, keyed
`instance_type:pk` (serializer-scoped, e.g. `project.TaskSerializer:5`). A
row write touches exactly one key per registered serializer shape and emits
exactly one broadcast frame. The server never composes nested structures —
only the client's `StateBuilder` does — so nested invalidation does not get
solved; it stops existing. The client's flat `index` is, structurally, a
partial replica of this store: Postgres → server object store → client object
store → React tree, every hop moving the same flat instances.

The layered walk is the unifying primitive that keeps the cache from
inheriting the N+1. The walk is source-agnostic; only the **layer resolver**
varies:

| Cache state | Layer resolution |
|---|---|
| Hot | `MGET` all keys — one round trip, no DB |
| Cold | `pk__in` query per type — one query; write-through to cache |
| Partial | `MGET`, then one `pk__in` for the misses only |

Because the pk set for each layer is known in advance, the miss path is
always a batch — never a per-key fallback. The cold path is not a separate
code path from the cached path; it is the fully-missed cached path. Retrieval
is O(depth) round trips against the store, O(edges) queries against Postgres,
in any mix.

## Consequences

### Positive

- Query count drops from O(rows) to O(edges); no duplicate refetches.
- First paint is one anchor-layer round trip away, regardless of tree size.
- The N+1 is dead in *all* resolver modes — batching is a property of the
  walk, not of the backend.
- Stubs restore v0's partial-state semantics: keyed skeletons, no `null`
  ambiguity, and the v0 placeholder tests plus the cross-call arrival-order
  scenarios from the v0 suite become portable to the rebuild's suite.
- No wire-format change for stubs; layered flushing is invisible to the
  protocol (more frames, same frames).
- Composes with ADR-0013/0014 rather than adding a consistency mechanism:
  subscribe-before-fetch plus per-row watermarks already make interleaved
  snapshot layers and live events safe.
- The event-loop blocking and the monolithic accumulation are fixed by the
  same rewrite that fixes the queries.

### Negative / Trade-offs

- Generated relation types carry the `_loaded` union — every consumer of a
  relation either branches or uses a helper. This is a known cost of the stub
  representation, accepted because partial state is now a permanent,
  observable phase of every connection, not an edge case.
- Cross-layer consistency on cold load is **eventual, per instance**: layer
  queries execute at different instants, so a write landing mid-walk can
  produce a momentarily torn snapshot across instances. Watermarked live
  events repair each instance; cross-instance invariants can still tear
  briefly. This must be documented as a framework semantic. (The alternative
  — snapshot-isolation transactions held across flushes — was judged not
  worth the cost.)
- Edge coherence is the residual hard problem the cache work must own: pk
  lists are denormalized reverse relations stored on the *parent's* cached
  instance. Creating a Task must also update `ProjectSerializer:1.tasks`.
  Bounded — the StateModel tree statically knows which parent types embed
  which child types, and the FK identifies the specific parent — but M2M and
  ordering are fiddly, and this is where the cache design's complexity budget
  goes. (The client already does the mirror-image bookkeeping in
  `detach`/`relink`.)
- `StateBuilder`'s index now legitimately accumulates partial state, making
  its pre-existing re-anchor and unbounded-index-growth issues part of this
  design's scope: merge semantics mean eviction and anchor reassignment need
  explicit answers, client-side and (later) cache-side, in the same
  vocabulary.

### Neutral

- `prefetch_related` derivation as previously conceived is subsumed: the tree
  is still the plan, but we execute it directly. `select_related` is not used
  either — to-one edges go through the same per-layer `pk__in` fetch as every
  other edge.
- Per-anchor cache topology (v0's Mongo design: membership precomputed,
  instances duplicated per anchor) is abandoned in favor of deduped
  per-instance storage; membership is derived by walking edges at read time.
- Subscription/broadcast membership granularity (per-instance groups vs
  per-anchor groups with server-side edge walk) is deliberately **not**
  decided here — it belongs to the cache ADR proper, along with eviction and
  the `MGET`/`MSET` backend choice.

## Alternatives Considered

### Option A: Monolithic delivery + derived `prefetch_related` (status quo, fixed)

Keep accumulate-then-send; fix only the N+1 by deriving a
`prefetch_related`/`select_related` spec from the StateModel tree. Types stay
maximally clean (`Task[]`, no stubs).

**Rejected.** Fixes query count but leaves time-to-first-paint proportional
to total tree size, forecloses incremental delivery without a later break,
and — decisively — is incompatible with the cache direction: a per-instance
store reads layer-wise by nature, so its natural output *is* incremental.
Committing to monolithic frames now means rearchitecting delivery when the
cache lands.

### Option B: `null` for unloaded slots, partial delivery legal

Keep `null` as the only empty representation; document that `null` means "not
here (yet or ever)"; expose loading progress out-of-band at channel level.

**Rejected.** Conflates explicit-null FKs with undelivered children, erases
the missing child's identity (the parent knows the pk; the state throws it
away), and breaks React list keying during load — precisely when keying
matters for skeleton UIs. Under always-incremental delivery the "loading"
phase is universal, so the representation must carry the id.

### Option C: Naive per-instance cache reads (the feared design)

Cache per instance but resolve children one key at a time as the rebuild
walks.

**Rejected** — this is the N+1 relocated to the KV store. Avoided entirely by
the pk-first layered walk: the next layer's full key set is always known
before it is fetched, so single-key reads never need to exist on the state
path.

### Option D: Per-anchor cache (v0's topology)

Materialize each anchor's full flat state under the anchor's key, as v0 did
with Mongo.

**Rejected as direction.** Precomputes membership (cheap reads) but
duplicates every shared instance across anchors and reintroduces a shade of
the nested-invalidation problem: one row write must find and update every
anchor state containing it. Per-instance storage keeps invalidation O(1) per
serializer shape and derives membership at read time via the walk.

## References

- ADR-0010 — `rx.model` reactive nested state (flat-serializer rebuild).
- ADR-0011 — per-backend model packages and codegen hooks (where the
  `_loaded` union shape lands).
- ADR-0012 — flat-layer wire protocol (`_type`-tagged instances; unchanged by
  this ADR).
- ADR-0013 — `ReactiveModel`, DB-minted per-row `_v` welded to writes.
- ADR-0014 — client-side version watermarks; subscribe-before-fetch. The
  merge frame semantics this ADR commits to are the ones 0014 assumes.
- ADR-0015 — compile-time derivation from the serializer tree; the layered
  walk's query plan is a compile-time artifact under that rule.
- `rxdjango-0/rxdjango-react/src/StateBuilder.test.ts` — hand-written v0
  suite pinning stub semantics (the tests Decision 3 unblocks).
- `packages/react/src/StateBuilder.ts` — client rebuild with memoized
  identity semantics and parents map (commit `e017d66`) and ADR-0014
  watermark reconciliation (merged in `fee4e1b`, scenarios pinned in
  `packages/react/src/StateBuilder.test.ts`, commit `5150955`); gains stub
  materialization under Decision 3.
- `packages/model/src/rxdjango_model/state_model.py`,
  `packages/model/src/rxdjango_model/fields.py` — the lazy walk and the
  monolithic flush this ADR replaces.
