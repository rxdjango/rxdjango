## Why

Initial-state delivery for `rx.model` fields is currently the worst of three worlds (ADR-0016): the lazy `getattr` walk issues O(rows) queries with duplicate refetches, `RxModelField.serialize()` accumulates everything into one monolithic frame so the client's state is `null` until the deepest branch is fetched, and all of it runs synchronous ORM inside the async consumer, stalling the worker. ADR-0016 decided the replacement architecture; this change implements it.

## What Changes

- Replace the lazy attribute walk in `StateModel.serialize_state()` with a pk-first, breadth-first layered walk: one `pk__in` query per instance type per layer, query count O(edges in the serializer tree). The query plan is compiled at class creation (ADR-0015). No `select_related` folding — every edge, to-one and to-many, resolves as a pk set (ADR-0016 decision 1).
- Run layer queries off the event loop (`sync_to_async` / thread executor) instead of blocking the consumer.
- **BREAKING (behavioral, not wire-format):** flush each completed layer immediately as its own `rx` frame. "One field payload = one complete frame" is dead; frames are merge frames reconciled by ADR-0014 watermarks. The wire envelope itself is unchanged.
- Client-side: `StateBuilder` materializes `{ id, _loaded: false }` typed stubs for referenced-but-not-yet-arrived instances (v0 semantics), replaced on arrival with reference-change propagation. Stubs are constructed from parent pk lists; the server never sends a stub.
- Codegen: generated relation types become a discriminated union on `_loaded`, emitted through the `rxdjango_model` codegen hooks (ADR-0011).
- Port the v0 placeholder and arrival-order tests (`rxdjango-0/rxdjango-react/src/StateBuilder.test.ts`) to the rebuild's suite.

Out of scope (deferred by ADR-0016 itself to a future cache ADR): the per-instance cache, layer resolvers other than the database, broadcast membership granularity, eviction.

## Capabilities

### New Capabilities

None — this change reshapes how existing model-state delivery behaves; no new capability surface.

### Modified Capabilities

- `model-state`: "Assignment sends flat, type-tagged layers" changes from a single frame to per-layer frames delivered progressively, parent-before-child, produced by the layered `pk__in` walk off the event loop; "The client rebuilds the nested shape" changes unresolved references from `null` to `{ id, _loaded: false }` stubs; stub replacement composes with reference stability and watermarks.
- `frontend-codegen`: "Typed model interfaces per app" changes — relation types are emitted as a `_loaded` discriminated union so partial state is honest in the generated types.

## Impact

- `packages/model/src/rxdjango_model/state_model.py` — lazy walk replaced by compiled query plan + layered execution.
- `packages/model/src/rxdjango_model/fields.py` — `RxModelField.serialize()` accumulate-everything removed; per-layer enqueue.
- `packages/react/src/StateBuilder.ts` — stub materialization; index accepts partial state.
- `rxdjango_model` TS codegen hooks — `_loaded` union in generated model interfaces.
- Existing suites: the backend Django suite (integration/protocol/makefrontend/e2e) validates wire compatibility of the backend half with zero frontend edits expected; `packages/react/src/StateBuilder.test.ts` gains stub/arrival-order scenarios ported from v0.
- No protocol change (ADR-0012 envelope untouched); composes with ADR-0013/0014 rather than adding mechanisms.
