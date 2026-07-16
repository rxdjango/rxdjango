# Design — Reactive List Fields

## Context

ADR-0017 fixed the semantics: `rx[list[S]]` with scalar-union elements,
in-place mutation as the server interface, positional delta ops on the `o`
slot, no sequencing, and a client list state machine that the queryset tier
(ADR-0018/0019) later feeds as a local producer. This design settles the
implementation shape across the four touched surfaces: `rx.py` (descriptor),
the consumer push path, `ts/channels.py` (codegen), and the
`@rxdjango/react` runtime — plus the example apps and test modules that
demonstrate and pin the behavior.

Current state: `rx.py` supports scalars only (`_SUPPORTED`), `_ts_type` maps
unknown types to `any`, the client applies every `rx` frame as a full
replacement, and the `o` key is reserved but never read or written.

## Goals / Non-Goals

**Goals:**

- `rx[list[S]]` declaration, validation, and per-connection list state.
- Exhaustive mutation interception emitting `i`/`s`/`d` ops or replace.
- Client op application with per-frame array identity for React.
- Array types in makefrontend output.
- Three example pages and the protocol/e2e test suite from the proposal.

**Non-Goals:**

- The queryset tier (Routers, membership derivation, `many=True` anchors) —
  separate change.
- Op batching/coalescing, a move op, nested containers — all recorded as
  additive-later in ADR-0017.
- `o` frames for model or scalar fields.

## Decisions

### D1. Descriptor shape: a bound proxy list per connection

`rx[list[S]](default)` produces a `ListRxField` descriptor whose class-body
value is a real `list` subclass carrying the default (ADR-0004's
descriptor-is-a-T trick, same as `int`/`str`/`float`). At `__get__` on a
connected channel, the stored value is a `ReactiveList` — a `list` subclass
bound to `(consumer, field_name)` that intercepts mutators **by explicit
enumeration**, not `__getattribute__` magic: each intercepted method
validates introduced elements, applies the mutation locally, then enqueues
the op. `__set__` validates element-wise, wraps a *copy* in a new
`ReactiveList`, and enqueues a replace. Each connection copies the default
at channel init (`list(default)`), so state is never shared across
connections or with the class default.

Why explicit enumeration: the exhaustiveness risk is real either way, but an
enumerated table is greppable, testable one-to-one (the convergence test
iterates the same table), and does not slow every attribute access.

### D2. Mutator → wire mapping

Positional ops for mutations whose effect *is* a bounded set of positional
edits; replace for permutations and slice-shaped edits:

| Mutator | Emission |
| --- | --- |
| `append(x)` | `i` at `len` (pre-mutation) |
| `insert(i, x)` | `i` at the **normalized, clamped** index (Python clamps) |
| `lst[i] = x` (int index) | `s` at normalized index |
| `del lst[i]` (int index), `pop(i)`, `remove(x)` | `d` at normalized/located index |
| `extend(xs)`, `+=` | one `i` per element (exact intent, in order) |
| `sort`, `reverse`, `clear`, `*=`, slice assignment/deletion | whole-value replace |

Indices are normalized server-side before emission: negative indices resolve
against the pre-mutation length, `insert` clamps like Python. The wire only
ever carries canonical non-negative indices, so the client needs no Python
index semantics.

### D3. Wire spellings

`o` ∈ `"i" | "s" | "d"`; operand rides the existing `v` slot: `[index,
value]` for `i`/`s`, bare `index` for `d` (ADR-0002 short-key rule). Replace
stays the frame with no `o`. Protocol version bumps `0.1.0` → `0.2.0`:
additive frame surface, minor bump. Ops flow through the existing
`enqueue_rx` path so the flush-after-`ac` ordering rule holds unchanged.

### D4. Client application without metadata

The runtime applies an `o` frame iff the field's current value is an array
(`Array.isArray`); otherwise the frame is discarded per the wire spec. No
generated metadata is needed: an optional list holding `null` can never
legitimately receive an op (server-side mutation of `None` raises before
emitting). Application copies the array, applies the op, assigns the new
identity, publishes — one render per frame.

### D5. Codegen

`_ts_type` gains a `typing.get_origin(t) is list` branch: map the element
union, parenthesize when more than one member, suffix `[]`; the field-level
None union stays outside (`number[] | null`). `_ts_literal` renders list
defaults (`[]`, `[1, 2]`, `['a', 1]`). Element `None` maps to `null` inside
the parens. All in core's `ts/channels.py` — no hook changes, list fields
are core fields.

### D6. Examples and tests

Three docs-first example apps (page + app + demo + Playwright e2e):
`scalar_list` (CRUD on `rx[list[str]]` — append/insert/set/remove/pop plus
a replace button), `list_types` (`list[int | str]` and `list[int] | None` —
union rendering and null-vs-empty at the value tier), `streaming_list`
(background thread appends on a timer — the delta story visible).

E2e-only protocol tests (backend suite): wire-shape asserts (`o` frames vs
replace frames at the raw-frame level); table-driven mutator convergence
over D2's full table (same table as the interception enumeration); mixed
burst ordering; declaration refusals (`rx[list]`, `rx[list[list[int]]]`,
missing default, bad default element); None-union semantics
(`AttributeError` on mutate-while-None, `null` on replace); makefrontend
snapshots for the three type shapes.

## Risks / Trade-offs

- [A missed mutator silently diverges client state] → the interception
  table and the convergence test iterate the *same* enumerated list of
  mutators; adding one without the other fails review; the table-driven
  test is the named guard for this bug class.
- [Index semantics mismatch (negative indices, clamping)] → normalization
  happens server-side only; the wire carries canonical indices; scenarios
  pin `insert` clamping and negative-index normalization.
- [`bool`/`int` overlap in element validation (`True` is an `int`)] → reuse
  the existing scalar `allowed`-tuple machinery, which already orders the
  check; add an explicit test with `list[int]` rejecting `True` only if the
  existing scalar rule does — parity with scalars, whichever way it points.
- [Protocol bump ripples] → version constant lives in one place per side;
  both change in this same commit series; no compatibility window exists
  yet (no deployed clients).
- [One frame per `extend` element could surprise] → documented ADR
  trade-off (no batching in v1); the streaming example demonstrates the
  per-op behavior as a feature.

## Migration Plan

Purely additive — no data migration, no breaking surface. Existing scalar
and model fields emit identical frames; generated files for existing apps
are unchanged except the protocol constant. Rollback is reverting the
commits.

## Open Questions

None blocking. Deferred by ADR-0017 (not this change): batching, move op,
nested containers via deep proxying.
