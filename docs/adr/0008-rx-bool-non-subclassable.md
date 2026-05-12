# 0008. `rx[bool]` is exempt from the "descriptor is a T" rule

- **Date:** 2026-05-12
- **Deciders:** Luis Fagundes

## Context

ADR-0004 pins the shape of reactive fields as `rx[T](default)` and commits
to a load-bearing property: **the object the descriptor exposes for
class-body use is itself an instance of `T`.** That property is what makes
`FRUITS[selected]` and `fruit[0]` in the carousel example read as ordinary
Python — the operand *is* the value.

The implementation realises that property by generating a synthetic class
that inherits from both `T` and `RxField` (see `_make_typed_field` in
`packages/python/src/rxdjango/rx.py`). For `int`, `str`, `float` this
works. For `bool`, it does not: in CPython, `bool` is not an acceptable
base type, and the class statement raises `TypeError` at import time. The
example `AuthorizationChannel.authorized = rx[bool](False)` crashes before
any reactive machinery runs.

ADR-0004 anticipated bool would be awkward — it flagged that instances of
an `rx[bool]` subclass would not be the `True`/`False` singletons and that
`is` comparisons would silently misbehave. What it did not anticipate is
that the subclass cannot be constructed at all. Bool is not "awkward to
subclass"; it is unsubclassable. The trade-off section of ADR-0004 is
therefore understated on this point: there is no version of the trick
that works for bool.

Two shapes were considered for closing the gap:

1. Drop the "descriptor is a T" property for `T = bool`, and have
   `rx[bool]` produce a plain descriptor whose identity is *not* a bool.
2. Introduce a separate exported type, e.g. `boolean`, that *is*
   subclassable and is required in place of `bool` at the declaration
   site (`rx[boolean](False)`), making the non-singleton-ness loud at the
   call site.

Option 2 restores symmetry with `int`/`str`/`float` and advertises the
identity leak in the type signature. It also adds a new exported concept
that users must learn, import, and reach for in place of the obvious
Python primitive — a cost paid on every bool declaration in exchange for
class-body affordances on bool that have no compelling use case (there
is no `bool` analogue of `FRUITS[selected]` or `fruit[0]` worth
preserving).

We accept the asymmetry: `bool` is genuinely the odd one out in Python's
type system, and pretending otherwise via a parallel framework type
leaks more cleverness than it hides.

## Decision

`rx[bool]` is exempt from the ADR-0004 property that the descriptor's
class-body representative is an instance of `T`.

Concretely:

- `bool` is removed from the set of subclassable bases used by
  `_make_typed_field`. `rx[bool](default)` falls back to the plain
  descriptor path (`_PlainRxField`).
- Reads and writes still pass real `True` / `False` through the instance
  dict, so user code outside the class body sees an ordinary Python
  bool. The leak is confined to the class-body identity of the
  declaration itself, where bool affordances are not load-bearing.
- The plain descriptor for `rx[bool]` gains a `__bool__` and a
  `__repr__` so that incidental truthiness and debugging behave
  sensibly when someone does inspect the descriptor object directly.
- `bool` remains a first-class `T` for codegen: `makefrontend` still
  emits a `boolean` TypeScript property from the declared type.
- No new exported type is introduced. The declaration site stays
  `rx[bool](default)`.

## Consequences

### Positive
- `rx[bool]` works. The authorization example imports cleanly and the
  framework's reference type set (`int`, `str`, `float`, `bool`) is
  honoured end-to-end.
- No new concept is added to the public surface. Users write the
  obvious thing.
- The identity hazard ADR-0004 warned about (`flag is True` quietly
  wrong) is no longer reachable, because the descriptor isn't a bool
  at all — it cannot be mistaken for the `True` singleton.

### Negative / Trade-offs
- The ADR-0004 invariant "the descriptor is a `T`" now has an
  exception. Anyone reading the rx machinery must know that bool is
  special-cased and why.
- Class-body expressions that would treat a reactive bool as a value
  (e.g. indexing into a two-element list with it) do not work. We
  judge this acceptable: such uses are rare and have ergonomic
  alternatives (`rx[int]` with 0/1).

### Neutral
- The runtime contract for callers of a bound bool field is
  unchanged: reads return real `True`/`False`, writes accept real
  `True`/`False`.

## Alternatives Considered

### Option A: Introduce a `boolean` type
A subclassable stand-in for bool, exported alongside `rx`. Declarations
would read `rx[boolean](False)`. Rejected: pays a permanent ergonomic
and learning cost on every bool field to preserve class-body
affordances on bool that have no compelling use case, and starts a
parallel type system that invites `integer` / `string` / `floating`
follow-ons.

### Option B: Reject `rx[bool]` entirely
Force users to model truthiness as `rx[int]` with 0/1 or a string
enum. Rejected: gratuitously worse DX; the type system already has
`bool` for exactly this purpose, and codegen has no trouble emitting
TypeScript `boolean`.

### Option C: Drop the "descriptor is a T" trick for all types
Treat every `rx[T]` as a plain descriptor, losing class-body
affordances uniformly. Rejected as out of scope: ADR-0004's
class-body composition is load-bearing for `int` and `str` (the
carousel example), and this ADR is about closing a single gap, not
relitigating the broader design.

## References

- ADR-0004 — The `rx[type](default)` reactive field. This ADR
  amends ADR-0004's invariant for the `T = bool` case; ADR-0004
  otherwise stands.
- `packages/python/src/rxdjango/rx.py` — `_SUBCLASSABLE`,
  `_make_typed_field`, `_PlainRxField`.
- `examples/backend/authorization/channels.py` — declares
  `authorized = rx[bool](False)`; was the surfaced failure.
