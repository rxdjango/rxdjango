## 1. Backend: compiled query plan (design D1)

- [ ] 1.1 Extend the class-creation tree compilation in `packages/model/src/rxdjango_model/state_model.py` to derive the ordered breadth-first layer list: model class, flat serializer, `_type`, and incoming edges (source layer + relation field) per entry
- [ ] 1.2 Handle plan edge cases: same type at multiple depths (shallowest rank wins, late-discovered pks fetch where discovered), cycle termination via already-fetched `_type:pk` dedup
- [ ] 1.3 Unit-cover the plan in the backend suite: layer order, edges, and dedup for a nested fixture (project → tasks → users/comments), asserted at import/class-creation time

## 2. Backend: layered walk, deposit/drain bridge, per-layer flush (design D2, D3, D6)

- [ ] 2.1 Rewrite `serialize_state` as an async generator: per rank, run `pk__in` queries + serialization in one `sync_to_async` hop, yield the completed layer
- [ ] 2.2 Collect and deduplicate next-rank pk sets from the yielded layer's serialized relation fields; drop already-fetched `_type:pk` keys
- [ ] 2.3 Replace `RxModelField.serialize()` accumulate-everything in `packages/model/src/rxdjango_model/fields.py`: `__set__` stays sync and deposits the field's pending layer walk on the consumer, keyed by field name (replacing any undrained walk for that field); `None` assignment supersedes likewise and yields a single `v: null` frame
- [ ] 2.4 Drain pending walks in `_flush_rx` (`packages/core/src/rxdjango/consumers.py`): async-iterate each walk, applying that layer's group joins before sending that layer's frame, then drain `_pending_rx` as today
- [ ] 2.5 Update protocol/integration assertions that expect one monolithic frame to expect the layered frame sequence (parent-before-child)
- [ ] 2.6 Add query-count assertions: O(edges) queries for the nested fixture regardless of row count; shared child (fan-in) fetched once; no `select_related` in the walk
- [ ] 2.7 Add supersession tests (reassign before drain → only the newer walk's frames; clear before drain → no layer frame after `v: null`) and per-layer group-join coverage (a row committed after its layer was delivered is pushed, not dropped)
- [ ] 2.8 Run the full backend suite (`cd examples/backend && uv run ./manage.py test`) — e2e must pass with the frontend untouched (wire-compatible shot 1)

## 3. Client: stub materialization (design D4)

- [ ] 3.1 In `packages/react/src/StateBuilder.ts`, materialize memoized `{ id, _loaded: false }` stubs for relation pks with no instance in the index; serialized `null` stays `null`
- [ ] 3.2 Inject `_loaded: true` into built (real) instances at build time; ensure stub→real replacement is unconditional (no watermark check against a stub) and propagates new references up the parents map
- [ ] 3.3 Keep stub references stable across reads while unloaded (same memoization discipline as built instances)
- [ ] 3.4 Port the v0 placeholder and arrival-order scenarios from `rxdjango-0/rxdjango-react/src/StateBuilder.test.ts` into `packages/react/src/StateBuilder.test.ts`, adapted to the rebuild's API

## 4. Codegen: `_loaded` discriminated union (design D5)

- [ ] 4.1 Emit `_loaded: true` on generated model interfaces and a shared `Unloaded` type via the `rxdjango_model` codegen hooks; type relation slots as `X | Unloaded` / `(X | Unloaded)[]` (+ `| null` for `allow_null`)
- [ ] 4.2 Update makefrontend suite expectations for the new interface shape; verify regeneration idempotence still holds
- [ ] 4.3 Regenerate the example SDK (`makefrontend`) and update `examples/frontend` components to branch on `_loaded` where they consume relations

## 5. Verification and docs

- [ ] 5.1 Full backend suite green (`cd examples/backend && uv run ./manage.py test`) and TS tests green (`packages/react` test run + `make check`)
- [ ] 5.2 Document the merge-frame semantic and the accepted torn-snapshot-on-load behavior where frame semantics are documented (per ADR-0016 consequences)
