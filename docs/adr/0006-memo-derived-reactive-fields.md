# 0006. `@memo` derived reactive fields

- **Date:** 2026-05-11
- **Deciders:** Luis Fagundes

## Context

ADR-0004 pins how a primary reactive cell is declared (`rx[T](default)`)
and ADR-0005 pins how one declaration on a channel names another (a
string identifier resolved at class-definition time). Between them
they cover state that the developer writes into directly. They do not
cover the equally common case where a value is *derived* from one or
more reactive fields and should itself behave reactively — recomputed
when its inputs change, and observable by the client just like a
primary field.

The carousel makes this concrete. Given a `selected` index, both the
selected fruit and its first letter are functions of state already on
the channel. Expressing them as primary `rx` fields and re-assigning
them inside every `@action` is the boilerplate the framework exists to
remove:

```python
class CarouselChannel(ContextChannel):
    FRUITS = ['banana', 'apple', 'orange']

    selected = rx[int](0)
    fruit = rx[str](FRUITS[selected])
    first_letter = rx[str](fruit[0])

    @action
    async def rotate(self):
        self.selected = (self.selected + 1) % len(self.FRUITS)
        self.fruit = self.FRUITS[self.selected]
        self.first_letter = self.fruit[0]
```

The `rotate` body is mechanical: every primary field after `selected`
restates a derivation that the class body already wrote once. The
channel's surface should let the developer state the derivation once
and let the framework keep it consistent.

A second motivation comes from authorization (a future ADR): the
channel will gate access on reactive state, and that state may itself
be derived. A first-class derived-field primitive lets gating refer to
the derived value through the same string-reference convention from
ADR-0005, instead of asking the developer to maintain an `rx` mirror by
hand.

## Decision

A derived reactive field is declared as a method decorated with
`@memo(*deps)`:

```python
class CarouselMemoChannel(ContextChannel):
    FRUITS = ['banana', 'apple', 'orange']

    selected = rx[int](0)

    @action
    async def rotate(self):
        self.selected = (self.selected + 1) % len(self.FRUITS)

    @memo('selected')
    def fruit(self):
        return self.FRUITS[self.selected]

    @memo('fruit')
    def first_letter(self):
        return self.fruit[0]
```

The semantics:

- **Dependencies are named with strings** under the convention in
  ADR-0005: each positional argument to `@memo` is the attribute name
  of another reactive field on the same channel. Names are resolved
  and validated at class-definition time. A memo may depend on `rx`
  fields and on other `@memo` fields; cycles are rejected at
  class-definition time.
- **Recomputation is eager.** When any declared dependency is assigned
  (directly via `self.dep = ...`, or as the result of another memo
  recomputing), the memo's function is called and its return value
  becomes the field's new value. Recomputation propagates: if
  `first_letter` depends on `fruit` and `fruit` recomputes, then
  `first_letter` recomputes too, in dependency order.
- **The field is strictly derived.** Assignment to a memo
  (`self.fruit = ...`) raises. The decorated function is the single
  source of truth for the value; the framework computes the initial
  value at channel instance construction and on every dependency
  change thereafter.
- **The field is visible to the client by default.** A `@memo` appears
  in the generated TypeScript channel state identically to an `rx`
  field. From the client's perspective there is no observable
  difference between a primary cell and a derived one — both are
  reactive properties on the channel.
- **The function's return type is the source of truth for codegen.**
  `makefrontend` reads the type annotation on the decorated method to
  project the field's TypeScript type, paralleling how `rx[T]` exposes
  `T` syntactically. The exact inference rules (annotation required vs.
  inferred, treatment of unions, etc.) are an implementation matter
  that may evolve, matching the same posture ADR-0004 takes toward the
  set of admissible `T`s.

## Consequences

### Positive
- The carousel's `@action` collapses to a single assignment. The
  derivation lives next to the declaration of the field it produces,
  not scattered across every action that touches an input.
- Chained derivations (`first_letter` depends on `fruit` which depends
  on `selected`) compose without the developer maintaining the order.
  The dependency graph the framework already has from ADR-0005 is what
  drives the order.
- Eager recomputation gives the client a consistent post-action
  snapshot: by the time the diff is emitted, every memo reflects the
  new inputs. There is no window where a primary field has been
  updated but a derived field is stale.
- Memos and `rx` fields are indistinguishable from the client side, so
  TypeScript consumers do not need to know which channel-side
  declarations are primary and which are derived.
- Authorization and any future "reference a reactive value" surface
  can name memos with the same string convention as primary fields,
  with no special case.

### Negative / Trade-offs
- Eager recomputation can do redundant work when one `@action`
  assigns several upstream fields in sequence: a memo with two
  dependencies that are both updated will recompute twice. The
  framework can mitigate this later (batching within an action) but
  the decision here pays the simpler-mental-model cost up front.
- A memo's function runs synchronously on every dependency assignment.
  Expensive memos can therefore inflate action latency in a way that
  is invisible at the call site; the developer is expected to keep
  memo bodies pure and cheap. The framework does not enforce this.
- Strictly-derived semantics mean any state that *sometimes* derives
  and *sometimes* is overridden has to be modelled as an `rx` field
  with manual updates. There is no escape hatch for "derived, but I
  also want to poke at it."
- Coupling to ADR-0005's string convention inherits its trade-offs:
  IDE rename does not propagate through the strings, typos are caught
  at import time rather than by static analysis.

### Neutral
- The exact codegen rules for projecting Python return-type
  annotations to TypeScript types are deliberately not pinned here.
  v0.1 will start narrow (scalar returns) and the surface
  `@memo(*deps)` does not change as it grows.
- Pureness is a convention, not an enforced property. The framework
  treats the function as a value producer; whether the developer
  performs side effects in it is their concern, with the understanding
  that anything observable beyond the return value is outside the
  reactive contract.
- Recomputation triggers off dependency *assignment*, not deep
  mutation. If a future ADR introduces structured reactive fields,
  the rules for what counts as a "change" to such a field will be
  defined there, not here.

## Alternatives Considered

### Option A: Derived fields as `rx[T]` with manual updates
Keep only `rx` fields; expect the developer to reassign them inside
every action. Rejected because it is exactly the boilerplate the
framework exists to remove; the carousel example shows how quickly the
restatements accumulate.

### Option B: Auto-tracked dependencies (no explicit `deps` argument)
A `@memo` decorator that introspects the function — at call time or
via attribute-access tracing — and infers dependencies. Rejected
because it conflicts with ADR-0004: the class-body name of an `rx`
field is the *value*, not a tracked proxy, so a memo body like
`self.FRUITS[self.selected]` performs ordinary attribute access and
list indexing with no hook for the framework to observe. Making it
observable would require giving up the transparency property of
ADR-0004. Explicit string deps preserve that property and serve as
checkable documentation.

### Option C: Lazy recomputation on read
Mark the memo dirty when a dep changes; recompute on the next read.
Rejected because clients receive state via push, not pull — the diff
emitter is itself a reader, but it runs at the end of every action,
so "lazy on read" effectively reduces to "eager at action end" with
extra bookkeeping. Plain eager recomputation is simpler and easier to
reason about, at the cost of redundant work within a multi-write
action (see trade-offs above).

### Option D: Writable derived fields
Permit `self.fruit = ...` and treat the next dep change as
overriding. Rejected because it gives the field two competing sources
of truth and makes its value at any moment depend on assignment
history rather than on the declared derivation. The use cases it
serves are better expressed as an `rx` field with the developer's
chosen update logic.

### Option E: Backend-only memos
Treat `@memo` as a server-side convenience that does not cross the
wire. Rejected because the motivating example (carousel) and the
expected consumer (authorization) both want the derived value
observable. A separate annotation for "server-only computation" can
be added later without affecting this surface; defaulting to invisible
would push the carousel back into reassigning `rx` fields just to make
the value visible to the client.

## References

- ADR-0004 — The `rx[type](default)` reactive field. The transparency
  property is what forces auto-tracking to be rejected.
- ADR-0005 — String references to reactive fields. Defines how
  `@memo`'s `deps` are named, resolved, and validated.
- `examples/backend/memo/channels.py` — `CarouselMemoChannel`
  demonstrates `@memo('selected')` and a memo that depends on another
  memo (`@memo('fruit')`).
- `examples/backend/carousel/channels.py` — the pre-memo version of
  the same example; the boilerplate it carries is what this ADR
  removes.
