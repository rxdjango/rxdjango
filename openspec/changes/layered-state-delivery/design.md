## Context

ADR-0016 decided the delivery architecture; this design maps it onto the code. Today `StateModel.serialize_state()` (`packages/model/src/rxdjango_model/state_model.py`) walks instance attributes lazily (O(rows) queries, duplicate refetches), `RxModelField.serialize()` (`packages/model/src/rxdjango_model/fields.py`) exhausts the generator into one monolithic frame, and the sync ORM runs inside the async consumer. The client (`packages/react/src/StateBuilder.ts`) already has memoized identity semantics, a parents map (`e017d66`), and ADR-0014 watermark reconciliation (`fee4e1b`); unresolved references currently rebuild as `null`.

Constraints inherited from the ADRs: the wire envelope is untouched (ADR-0002/0012); everything derivable from the serializer tree is compiled at class creation (ADR-0015); frames reconcile via DB-minted `_v` and client watermarks (ADR-0013/0014); no `select_related` folding — layers keep a resolver-agnostic shape (pk set per instance type) so the future per-instance cache can slot in as a layer resolver (ADR-0016 decisions 1 and 4).

## Goals / Non-Goals

**Goals:**

- One `pk__in` query per instance type per layer, O(edges), plan compiled at class creation.
- Per-layer flush: anchor paints first, parent-before-child, merge-frame semantics.
- Layer queries off the event loop.
- Client stubs `{ id, _loaded: false }` for referenced-but-unarrived instances; `_loaded` discriminated union in generated types.
- Port v0 stub/arrival-order test scenarios to `packages/react/src/StateBuilder.test.ts`.

**Non-Goals:**

- The per-instance cache, `MGET` layer resolution, broadcast membership granularity, eviction (deferred by ADR-0016 to the cache ADR).
- Any wire-envelope or frame-shape change.
- StateBuilder re-anchor / index-eviction answers (noted by ADR-0016 as in-vocabulary future work, not built here).

## Decisions

### D1. The compiled plan is a layer list with typed edges

At class creation (extending the existing tree compilation in `state_model.py`), derive an ordered breadth-first layer list. Each entry carries: the model class to query, the flat serializer, the `_type`, and the incoming edges — `(source layer, relation field name)` pairs whose serialized values (pk or pk list) feed this layer's pk set. Only pk sets are runtime data. Depth ties (two types at the same depth) are separate entries in the same layer rank and query independently. A serializer type reachable at multiple depths resolves at its shallowest rank; pks discovered later for an already-flushed type are fetched in the rank where they are discovered (the walk is driven by discovered pk sets, not by pre-assigned depth alone). Cycles terminate because already-fetched `_type:pk` keys are dropped from subsequent pk sets.

*Why not derive a `prefetch_related` spec:* rejected by ADR-0016 (Alternative A) — the ORM would give back a composed object graph and monolithic timing; executing the plan ourselves is what makes per-layer flush and future cache resolution possible.

### D2. Walk execution and threading

`serialize_state` becomes an async generator: for each layer rank, run the (sync) `pk__in` queries plus serialization for that rank in a thread via `sync_to_async` (channels' executor), `yield` the completed layer, repeat. The event loop is blocked only for enqueue/handoff, never for queries. Serialization happens in the same thread hop as the query so lazy serializer fields cannot re-enter the ORM on the loop.

### D3. Per-layer flush replaces accumulate-everything

`RxModelField.serialize()` stops exhausting the generator. Assignment iterates the async generator and enqueues one `rx` frame per yielded layer (same envelope, `v` = flat array of that layer's dicts). Ordering is guaranteed by construction: a layer is only discovered from its parent's output, and frames are enqueued in yield order on the same connection queue. Assigning `None` keeps today's single `v: null` frame.

*Test fallout accepted:* backend protocol/integration tests that assert "one frame with N layer dicts" must be updated to assert the layered sequence — that is the specified behavior changing, not collateral damage. The e2e suite (final rendered state) should pass unchanged.

### D4. Stub materialization lives in StateBuilder's splice step

When rebuilding, a relation slot whose pk has no instance in the index materializes a memoized stub `{ id, _loaded: false }` (per `_type:id`, stable reference while unloaded — same memoization discipline as built instances). A serialized `null` stays `null`. When the real instance arrives, normal merge handles it: stubs carry no `_v`, so any real instance wins unconditionally; the slot's ancestors re-key through the existing parents-map propagation. Watermark comparison applies only between real instances.

### D5. Codegen shape: `_loaded: true` on loaded interfaces + a shared `Unloaded` type

ADR-0016 left the exact union shape to implementation (within ADR-0011's hooks). Decision: generated model interfaces carry `_loaded: true`; a single `Unloaded` type `{ id: <pk type>; _loaded: false }` is emitted (in the runtime package or per-app models file — wherever `rxdjango_model`'s hooks already place shared types); relation slots become `X | Unloaded` / `(X | Unloaded)[]` (+ `| null` for `allow_null`). StateBuilder injects `_loaded: true` into built instances client-side — the server payload is unchanged, keeping the wire contract intact.

*Why the flag on both sides of the union (vs. `_loaded` only on the stub):* `x._loaded` is a proper TS discriminant, so `if (x._loaded)` narrows both branches with no `in`-operator idiom and no cast — the honest-types north star. The cost (a synthetic field on every built instance) is client-local.

### D6. Sequencing: two shots, backend first

Shot 1 (backend: D1–D3) is wire-compatible — same flat instances in more, smaller frames — so the existing Django suite validates it with only the frame-count/protocol assertions updated and zero frontend changes (a `null`-rebuilding client still converges once all layers land). Shot 2 (client + codegen: D4–D5) then changes what partial state looks like, pinned by the ported v0 tests.

## Risks / Trade-offs

- [Torn cross-instance snapshots on load: layer queries execute at different instants, so a mid-walk write can briefly tear cross-instance invariants] → Accepted by ADR-0016 as a framework semantic; per-instance repair via watermarked live events (ADR-0013/0014). Document it where merge-frame semantics are documented.
- [`_loaded` union is a breaking change for every consumer of generated relation types] → Accepted deliberately by ADR-0016; example-app components in `examples/frontend` are updated in Shot 2 and double as the migration illustration.
- [Deep trees mean more, smaller frames — per-frame overhead grows] → Frames batch an entire layer (all instances of all types at that rank can share a frame or be enqueued back-to-back); overhead is O(depth), not O(rows).
- [Thread-hopped serialization could hit connection-per-thread ORM pitfalls] → Use channels' standard `sync_to_async` executor semantics, same as the rest of the framework's DB access; one hop per layer keeps connection churn bounded.
- [Diamond/cyclic serializer graphs could double-fetch or loop] → The walk dedupes on already-fetched `_type:pk`; covered by an explicit fan-in test (two parents sharing a child).

## Migration Plan

No deployment migration: single repo, no published consumers. Land as two PR-sized shots (D6). Shot 1 leaves the frontend untouched and green; Shot 2 regenerates the example SDK (`makefrontend`) and updates example components in the same commit, so the repo never holds a half-migrated state.

## Open Questions

- Where exactly the `Unloaded` type is emitted (shared runtime export vs. per-app models file) — settled during Shot 2 by whatever ADR-0011 hook surface makes least duplication; both satisfy the spec delta.
- Whether one layer rank = one frame or one frame per instance type within a rank — spec requires parent-before-child frames per layer; the finer split is an implementation detail chosen for frame-size ergonomics during Shot 1.
