# 0017. Reactive list fields with delta operations

- **Date:** 2026-07-16
- **Status:** Active
- **Deciders:** Luis Fagundes

## Context

`rx[T]` (ADR-0004) supports scalars only — `int`, `str`, `float`, `bool`,
and `None` unions; `rx[list[int]]` is a `TypeError` today. No plain-value
list exists anywhere in the framework.

The queryset list records (ADR-0018, ADR-0019) define lists of model rows —
delivery through Routers, membership derived client-side — but the
client-facing list contract itself (`T[]` state, ordered, keyed rendering)
is born nowhere. The intent from the start: a list architecture first,
querysets built over it.

Forces:

- ADR-0002 reserved the `o` operation slot on the `rx` envelope on day one;
  it is still unused.
- Plain rx fields are per-connection channel state: one producer (the
  connection's own consumer), one FIFO socket. The sequencing problem that
  killed the retracted edge-delta design arose entirely from multi-writer
  group broadcast — it does not exist in this tier.
- Incremental updates are a requirement, not an optimization: the framework
  must not be limited by assumptions about typical list size or churn.

## Decision

**Type surface.** `rx[list[S]]` for `S` any union drawn from the supported
scalar set, generated mechanically: `list[int]` → `number[]`,
`list[int | str]` → `(number | string)[]`. A default is required, like
every rx field, and the None-union rule applies unchanged —
`rx[list[S] | None]` is optional with implicit default `None`, generated as
`S'[] | null`. The descriptor instance is a real `list` (ADR-0004's
descriptor-is-a-T trick; `list` is subclassable).

**Nested containers are refused loudly.** `list[list[int]]` fails at
declaration — not a type-system limitation but a semantic guarantee: scalar
elements are immutable, so every possible change to the field must flow
through a descriptor operation. A mutable element could be changed in place
(`self.matrix[0].append(x)`) without the descriptor seeing it, silently
diverging client from server. Element immutability is what keeps "every
change is an op" total. Support would require proxying all the way down —
its own decision, additive later.

**Server surface.** In-place mutation is the interface: `append`, `insert`,
`__setitem__`, `del` / `remove`, `pop` — each maps one-to-one to a delta
operation. Reassignment (`self.items = [...]`) is a whole-value replace. No
new verbs, just Python list semantics.

**Wire.** Delta ops travel on the `o` slot of ordinary `rx` frames. Replace
is today's plain frame (no `o`); the incremental vocabulary is positional —
insert-at-index, remove-at-index, set-at-index. **No sequence numbers**:
single producer plus FIFO socket means op order is application order by
construction. No move op — a reorder is remove+insert, consistent with the
queryset tier; additive later if justified.

**The base contract.** The client implements one list state machine: `T[]`
state changed only through replace/insert/remove/set. Two producers feed
it: wire ops (this tier) and the queryset tier's derivation engine, which
compiles membership verdicts into the same local operations. The boundary
is explicit and one-directional: the queryset tier reuses the client
container, op application, and vocabulary — it never puts list ops on the
wire (its membership stays derived, per ADR-0019).

## Consequences

### Positive

- The rx type system gains containers at the cost of one new concept (the
  op vocabulary) — the server surface is Python list semantics, no new
  verbs, and `rx[list[S]]` composes with the existing None-union and
  default rules unchanged.
- Wire cost per mutation is O(1) regardless of list size — no assumption
  about what lists typically hold survives into the design.
- The client-facing list contract (`T[]` state, replace/insert/remove/set
  application, ordered keyed rendering, generated array types) is born
  here, once — the queryset tier plugs into it as a local producer, so
  implementation order matches the architectural layering.
- Correct ordering costs nothing: single producer plus FIFO socket makes op
  order application order by construction — no sequences, no watermarks, no
  resync machinery in this tier, ever.
- The `o` slot finally earns its ADR-0002 reservation, and its first use is
  the simplest case the protocol has.

### Negative / Trade-offs

- The descriptor becomes a mutation-intercepting proxy, and interception
  must be **exhaustive** over `list`'s mutating API (`append`, `insert`,
  `__setitem__`, `__delitem__`, `remove`, `pop`, `extend`, `clear`, `sort`,
  `reverse`, `+=`, slice assignment). A missed method is a silent
  server-side divergence — a real new bug class, contained in `rx.py`.
- Client op application is load-bearing: positional ops applied exactly, in
  order. A client-side bug diverges silently until the next replace. (Loss
  is not the risk — implementation correctness is.)
- One mutation = one frame: a loop of `append`s emits a frame each.
  Batching (coalescing ops within an action) is deliberately absent in v1 —
  additive later if it earns its place.
- `null` means different things across tiers — explicit `None` here, "not
  yet snapshotted" in the queryset tier. A documentation burden,
  mechanically unambiguous within any one field.
- Nested containers refused: an expressiveness limit, deliberate — element
  immutability is what keeps "every change is an op" total.

### Neutral

- Bulk mutators (`sort`, `reverse`, `clear`, large `extend`) may compile to
  a whole-value replace rather than op storms — an implementation choice
  inside the contract, invisible to semantics.
- Exact operand key spellings deferred to implementation under ADR-0002's
  short-key rule.
- Generated types follow mechanically: `number[]`, `(number | string)[]`,
  `| null` via the union rule — makefrontend-only surface growth.
- The queryset records are unchanged by this one; the wire boundary (ops
  never on the wire for derived lists) is one-directional and stated on
  both sides.

## Alternatives Considered

### Option A: Whole-value re-send on every change

Every mutation re-broadcasts the full list as an ordinary `rx` frame — no
new wire vocabulary, uniform with scalars. Rejected: O(n) wire per change
assumes lists stay small, and the framework must not be limited by an
assumption about what's typical. Incremental delivery is a requirement; the
`o` slot was reserved precisely so semantics could serve performance.

### Option B: Reassignment-only surface with server-side diffing

Keep the scalar discipline (only `self.items = [...]` notifies) and have
the framework diff old against new to emit minimal ops. Preserves a single
write idiom, but replaces exact intent with reconstruction: diffing is O(n)
heuristic work per write that can misread a change (a remove+insert of
equal values vs. a move), while in-place mutation methods carry the
developer's intent one-to-one for free. Rejected — Python list semantics
*are* the interface; no new verbs were invented.

### Option C: Sequenced ops with gap detection

Number the ops per field so the client can detect loss — the retracted
edge-delta lineage's machinery. Rejected as solving a problem this tier
does not have: one producer, one FIFO WebSocket; partial loss without
disconnection is impossible, and a disconnect rebuilds the field through
the ready/replace path anyway. Sequencing existed to order multi-writer
group broadcast, which plain per-connection fields never face.

### Option D: One op wire for both tiers

Make the queryset tier emit these same list ops on the wire, "completing"
the layering. Rejected: that is the retracted server-authoritative
membership design re-entering through the base — wire ops for shared lists
reintroduce exactly the sequencing and ownership problems ADR-0019
dissolved. The queryset tier reuses the client container and vocabulary as
a *local* producer; the wire boundary is deliberate and one-directional.

### Option E: No value tier — querysets are the only lists

Plain lists stay inexpressible, and the first `T[]` client contract is born
inside the queryset tier. Rejected: pure channel state (a list of scalars)
would require a model and a database table to express, and the layering
inverts — the general contract would be defined by its most specialized
consumer.

## References

- ADR-0002 — the envelope; the `o` slot this record populates and the
  short-key rule its operands follow.
- ADR-0004 — the `rx[T]` descriptor surface this record extends; the
  descriptor-is-a-T trick and None-union rule reused unchanged.
- ADR-0018, ADR-0019 — the queryset list tier that reuses this record's
  client contract as a local producer.
- `packages/core/src/rxdjango/rx.py`,
  `packages/core/src/rxdjango/ts/channels.py` — the surfaces this record
  extends.
