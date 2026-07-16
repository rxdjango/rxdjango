# Tasks: static-queryset-lists

## 1. Server: list anchors compile and snapshot

- [x] 1.1 Unwrap `ListSerializer` in `StateModel` so `rx.model(S(many=True))` compiles at class creation, with the field marked list-valued (fixes the `_disassemble_nested` crash); unit tests for compile parity with the single-instance form
- [x] 1.2 Accept queryset assignment on list fields: the layered walk's anchor layer is the queryset's full row set in one frame; empty queryset sends `v: []`; reassignment supersedes per existing semantics; unit/integration tests
- [x] 1.3 Consumer group management across rebind: new snapshot's rows joined, rows only in the old snapshot left; integration test asserting no frames arrive for dropped rows after rebind

## 2. Server: bind-time introspection and the `q` descriptor

- [x] 2.1 Introspect `queryset.query.where` and ordering at bind: extract `(column, lookup, value)` conjunctions; reject OR/NOT, joined paths, unsupported lookups, non-serialized columns, non-JSON values — loudly, naming the condition; unit tests per rejection class
- [x] 2.2 Emit the descriptor on the snapshot anchor frame as `q: {"w": [...], "s": [...]}`; datetimes serialized exactly as DRF renders them; protocol tests for filtered, ordered, and empty querysets
- [x] 2.3 Bump `PROTOCOL_VERSION` to `0.3.0`; update protocol tests

## 3. Client: membership derivation in StateBuilder

- [ ] 3.1 Replace the single-anchor assumption with a per-field membership basis (pk set) + shared index; `q` frame resets the basis atomically, demoting absent rows with watermarks retained; vitest for reset, demotion, and stale-frame-after-demotion
- [ ] 3.2 Condition evaluator for `exact`, `in`, `gt`, `gte`, `lt`, `lte`, `isnull` matching Django verdicts on serialized values (including ISO datetime strings); per-lookup vitest parity suite
- [ ] 3.3 Ordering comparator honoring the `s` spec (`-` prefix, multi-column); derivation = basis ∩ passing conditions, sorted; new array identity on membership/order change, element reference stability preserved; vitest
- [ ] 3.4 Wire membership changes to frame handling: merge frames re-derive when touching basis rows (residual flip out/in), `_del` shrinks the basis through the detach path; `null` → `[]` → `T[]` state semantics; vitest

## 4. Client: persistent socket

- [ ] 4.1 Port v0's `PersistentWebsocket` (exponential backoff, reset on open, stop on last unsubscribe) as the `ContextChannel` transport; vitest for backoff and unmount-stops-retrying
- [ ] 4.2 Reconnect as rebind over a warm index: new connection's `q` frames reset bases, re-delivered layers merge idempotently under `_v`; vitest for warm-reconnect convergence and reference stability

## 5. Codegen

- [ ] 5.1 Generate `T[] | null` channel properties for `many=True` fields, initialized `null`; `_modelFields` marks list anchors; makefrontend tests
- [ ] 5.2 `make check` passes (docgen + `tsc --noEmit`) with a generated list channel in the examples

## 6. Example app and e2e

- [ ] 6.1 Backend example app for the static list tier (seed data migration, channel binding a filtered ordered queryset) and docs page `docs/examples/<slug>.md` wired into the toctree + generated page + hand-written demo
- [ ] 6.2 Playwright e2e: snapshot render, live update to a member, residual flip out and back in, delete removes the row, ordering change re-sorts, empty list renders `[]` state not loading
- [ ] 6.3 Reconnect e2e/integration: drop the socket server-side, assert the client heals with backoff and converges after rebind

## 7. Wrap-up

- [ ] 7.1 All three test tiers green: `uv run pytest`, `cd examples/backend && uv run ./manage.py test`, `cd packages/react && npm test`
- [ ] 7.2 Update `docs/issues.md` if any known inconsistency is affected; verify no doc claims routed delivery exists yet
