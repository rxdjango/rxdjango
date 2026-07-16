# Reactive List Fields

## Why

ADR-0017 accepted reactive list fields with delta operations: `rx[list[S]]`
for scalar element types, mutated in place with Python list semantics and
delivered incrementally on the `o` slot the wire envelope reserved on day
one. Nothing of it is implemented — `rx[list[int]]` is a `TypeError` today —
and the queryset list tier (ADR-0018/0019) plugs into the client list
contract this change creates, so it is the first implementation step of the
whole lists architecture.

## What Changes

- `rx[list[S]]` declarations: `S` any union drawn from the supported scalar
  set, None-union rule unchanged (`rx[list[S] | None]`), defaults required
  and element-validated, nested containers refused loudly at declaration.
- The descriptor instance is a real `list`; in-place mutation (`append`,
  `insert`, `__setitem__`, `__delitem__`, `remove`, `pop`, `extend`,
  `clear`, `sort`, `reverse`, `+=`, slice assignment) is intercepted
  exhaustively and notifies the consumer; reassignment stays a whole-value
  replace.
- Wire: incremental list updates ride the `o` slot of `rx` frames —
  positional insert / remove / set ops; replace remains the plain frame with
  no `o`. No sequence numbers. Bulk mutators may compile to a replace.
- Client: the `@rxdjango/react` runtime grows the list state machine —
  `T[]` state changed only through replace/insert/remove/set — the base
  contract the queryset tier will later feed as a local producer.
- Codegen: `makefrontend` emits array types — `number[]`,
  `(number | string)[]`, `number[] | null`.
- Three new example pages (docs-first, each a Django app + demo + e2e
  test): scalar list CRUD, optional/union element types, streaming appends
  from a background thread.
- Protocol/e2e test additions: `o`-frame wire shape, exhaustive mutator
  convergence, burst ordering, declaration-time refusals, None-union
  semantics, codegen snapshots.

## Capabilities

### New Capabilities

None — list fields extend existing capability surfaces rather than adding a
new one.

### Modified Capabilities

- `rx-fields`: the scalar-only declaration rule is replaced — `rx[list[S]]`
  becomes legal (the "rx[list] raises TypeError" scenario inverts), with new
  requirements for element unions, list defaults, None-union lists, nested
  refusal, and the in-place mutation surface.
- `wire-protocol`: the "rx frames carry full replacement values, no
  partial-operation key exists" requirement is amended — `rx` frames MAY
  carry an `o` key with a positional list operation; replace remains the
  frame without `o`.
- `frontend-codegen`: generated field types gain array forms for list
  fields, including parenthesized element unions and `| null`.
- `react-client`: `rx` frame handling gains list op application — ops
  mutate the field's array in place (new array identity per publish),
  applied in arrival order.

## Impact

- `packages/core/src/rxdjango/rx.py` — declaration surface, list descriptor
  and mutation interception (the bulk of the new code).
- `packages/core/src/rxdjango/consumers.py` / `channels.py` — op frames
  flow through the rx push path alongside whole-value pushes.
- `packages/core/src/rxdjango/ts/channels.py` — array type generation.
- `packages/react/src/` — list op application in the channel runtime, plus
  TS unit tests.
- `examples/backend/` — three new example apps with migrations, settings
  and urls registration; new protocol/e2e test modules; `examples/frontend/`
  demos and generated pages (`make extract`).
- Wire protocol version: additive change to the `rx` frame; whether `0.1.0`
  bumps is settled in design.
- No breaking changes: existing scalar fields, model fields, and generated
  code are untouched; the `o` key is new surface only.
