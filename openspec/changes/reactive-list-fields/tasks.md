# Tasks — Reactive List Fields

## 1. Server descriptor (`packages/core/src/rxdjango/rx.py`)

- [x] 1.1 Accept `list[S]` in `rx.__class_getitem__`: parse element union, validate against the scalar set, refuse bare `list` and nested containers with the ADR-0017 totality message, keep the field-level None-union rule
- [x] 1.2 Element-validate list defaults at declaration; produce a `list`-subclass class-body value carrying the default (descriptor-is-a-T)
- [x] 1.3 Implement `ReactiveList` proxy: explicit mutator table per design D2, element validation on introduced values, index normalization/clamping before emission, local apply then enqueue
- [x] 1.4 Per-connection default copy at channel init; `__set__` validates element-wise, wraps a copy, enqueues replace; mutation-while-None raises `AttributeError` naturally
- [x] 1.5 Unit-style declaration tests (testing app): refusals (`rx[list]`, `rx[list[list[int]]]`, `rx[list[dict]]`, missing default, bad default element), accepted shapes (`list[int]`, `list[int | str]`, `list[str | None]` elements, `rx[list[int] | None]`)

## 2. Wire emission (`packages/core/src/rxdjango/consumers.py`, `channels.py`)

- [x] 2.1 Extend the rx push path to carry an optional op: `o` ∈ `i`/`s`/`d` with `v` as `[index, value]` or bare index; replace stays a plain frame
- [x] 2.2 Bump the protocol version constant to `0.2.0` (server side)
- [x] 2.3 Protocol tests: wire-shape asserts for append/insert/set/del/pop/remove (op frames, canonical indices) and reassignment (no `o`); flush-after-`ac` ordering holds for op frames

## 3. Client runtime (`packages/react/src/`)

- [x] 3.1 Apply `o` frames in the channel runtime: `Array.isArray` gate, positional apply, new array identity per frame, publish per frame; discard `o` frames for non-array fields
- [x] 3.2 Bump the client protocol version constant to `0.2.0`
- [x] 3.3 TS unit tests: streamed appends, mixed burst convergence, replace-after-ops, `o`-on-non-list discarded

## 4. Codegen (`packages/core/src/rxdjango/ts/channels.py`)

- [x] 4.1 `_ts_type`: `list[S]` → mapped element union, parenthesized when >1 member, `[]` suffix; field-level `| null` outside
- [x] 4.2 `_ts_literal`: render list defaults
- [x] 4.3 makefrontend tests: generated snapshots for `string[]`, `(number | string)[]`, `number[] | null` with default literals

## 5. Convergence and semantics tests (backend suite)

- [x] 5.1 Table-driven mutator convergence test: iterate the same mutator table as D2 (append, insert, `__setitem__`, `__delitem__`, remove, pop, extend, clear, sort, reverse, `+=`, `*=`, slice assignment/deletion); apply server-side, assert client list equals server list
- [x] 5.2 Burst-ordering test: interleaved op sequence in one action converges
- [x] 5.3 None-union semantics test: `null` travels on replace; `AttributeError` on mutate-while-None; wrong-typed append raises and sends nothing
- [x] 5.4 Connection-isolation test: one connection's mutation leaves another's list untouched

## 6. Example: scalar_list (docs page + app + demo + e2e)

- [x] 6.1 Backend app `scalar_list`: `rx[list[str]]` channel with append/insert/set/remove/pop/replace actions; settings + urls registration
- [x] 6.2 `docs/examples/scalar_list.md` + toctree entry; `demo.tsx`; run `make extract`; `makefrontend` for the generated client
- [x] 6.3 Playwright e2e: each button mutates the rendered list live and order is preserved

## 7. Example: list_types (docs page + app + demo + e2e)

- [x] 7.1 Backend app `list_types`: `rx[list[int | str]]` and `rx[list[int] | None]` fields with actions toggling None/empty and mixing element types
- [x] 7.2 Docs page + demo + `make extract` + `makefrontend`
- [x] 7.3 Playwright e2e: mixed list renders both types; null renders distinctly from empty

## 8. Example: streaming_list (docs page + app + demo + e2e)

- [ ] 8.1 Backend app `streaming_list`: background-thread timer appending to `rx[list[int]]` (reactive_model's thread pattern)
- [ ] 8.2 Docs page + demo + `make extract` + `makefrontend`
- [ ] 8.3 Playwright e2e: items arrive one at a time without reload

## 9. Wrap-up

- [ ] 9.1 Full suite green: `cd examples/backend && uv run ./manage.py test`, `make check`, `packages/react` TS tests
- [ ] 9.2 Update `openspec/specs/` baselines happen at archive; verify delta specs validate (`openspec validate --change reactive-list-fields`)
