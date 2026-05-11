# 0007. Action authorization via a reactive gate field

- **Date:** 2026-05-11
- **Deciders:** Luis Fagundes

## Context

Channels expose `@action` methods that the client may invoke. Most
actions in a non-trivial application are only callable once some
condition holds — the user has authenticated, a session is in the
right phase, a feature flag is on. v0.0.x handled this with consumer
code that inspected request state ad hoc; v0.1 wants the gate to live
on the channel class, where the rest of the channel's state already
lives, and to compose with the reactive primitives the prior ADRs
established.

The shape this takes is consequential. The gate condition is itself
state — typically it changes during a session ("user has now
authorized") and clients should react when it does. The natural place
for that state is an `rx[T]` field (ADR-0004) or a `@memo` derived
from one (ADR-0006). The natural way for an action declaration to
name it is the string-reference convention from ADR-0005. With those
in hand, "this action requires that this reactive field be truthy" is
expressible without inventing a parallel mechanism.

A second concern is the bootstrap case: at least one action on a
gated channel must be callable *before* the gate is satisfied — the
authentication action itself is the obvious example. The framework
needs a way to declare "this action does not participate in gating"
that is local to the action declaration, so the bootstrap path is
visible at the same site as the gate it sets up.

A third concern is the common case of a channel where most actions
share the same gate. Declaring `requires='authorized'` on every
action duplicates the declaration and makes it easy to forget on a
new action. A channel-level default is the natural shape, but its
name must signal that per-action declarations override it rather than
compound with it; ADRs are also the place to pin that semantic
choice.

## Decision

Authorization for `@action` is expressed in three coordinated pieces:

1. **`@action(requires='field_name')`** — per-action gating. The
   string names a reactive field on the same channel under the
   convention of ADR-0005. The field **must** be an `rx[T]` field or a
   `@memo` field (a plain class attribute is rejected at class-
   definition time). The action is callable only when the named
   field's value is truthy at invocation time. `requires=` accepts
   exactly one name; conditions that combine multiple fields are
   expressed by introducing a `@memo` that names the combination.

2. **`class Meta: default_action_requires = 'field_name'`** —
   channel-wide default. Applies to any action on the channel that
   does not declare its own `requires=` and is not marked
   `anonymous=True`. A per-action `requires=` **replaces** the
   default; the two are not AND-ed. The `default_` prefix is load-
   bearing: it follows Django's `Meta` convention (`default_manager_
   name`, `default_related_name`, `default_permissions`) and is what
   makes the override-not-cumulative semantics legible from the name
   alone.

3. **`@action(anonymous=True)`** — explicit bypass. The action is
   callable regardless of any default or per-action gate. This is the
   bootstrap escape hatch: an authentication action that has to be
   reachable before `authorized` is true uses `anonymous=True`. It is
   mutually exclusive with `requires=` on the same declaration;
   combining the two is a class-definition-time error.

Behavior when a gated action is invoked with a falsy gate:

- The framework does **not** run the action body.
- A `403`-coded protocol error frame is sent back over the channel,
  identifying the action and the unsatisfied gate by name.
- The channel remains open; this is per-action denial, not channel-
  level auth failure.

Resolution and validation:

- Gate field names are resolved at class-definition time per
  ADR-0005. Unknown names, names pointing at non-reactive
  attributes, and a `requires=`/`anonymous=True` combination all
  raise at class load.
- The gate is read fresh on every action invocation. There is no
  caching: if a memo's value flips between invocations, subsequent
  calls see the new value.

## Consequences

### Positive
- Authorization composes with the rest of the channel's reactive
  state instead of living in a parallel system. The same `rx[bool]` /
  `@memo` that drives the UI's "logged in" indicator also gates the
  actions; there is no second source of truth.
- The bootstrap path is visible at the call site. A reader sees
  `@action(anonymous=True)` on `authorize` and immediately knows it
  is the way in.
- Channel-wide gating with `default_action_requires` removes the
  per-action restatement. The name itself signals the override
  semantics, so readers do not need to learn a rule from the docs.
- `403` denial without disconnect lets the client distinguish
  "this action is currently not allowed" from "the channel is
  broken." UIs can prompt for credentials in response to a `403`
  on a specific action without tearing down their subscription.
- Requiring the gate to be an `rx` or `@memo` field means the
  client can observe the gate's value directly when the developer
  wants it to — the gate is, by construction, part of the channel's
  reactive state.

### Negative / Trade-offs
- Requiring the gate to be reactive means a developer cannot reach
  for a plain class attribute or instance attribute "just for
  authorization." This rejects the shape used in the current
  authorization examples (`authorized: bool = False`); those
  examples must be updated to `authorized = rx[bool](False)` in the
  same PR that lands this ADR, or in an immediate follow-up.
- `requires=` accepting only one name pushes any compound condition
  through a `@memo`. This is intentional documentation pressure but
  is friction for two-field conditions that would otherwise be
  one-liners.
- The Meta-vs-per-action rule is override, not cumulative — which
  some readers may expect by default. The `default_` prefix is the
  mitigation, but it is a convention, not enforcement.
- `anonymous=True` is a real bypass, not a gate that happens to be
  satisfied. A misplaced `anonymous=True` silently disables
  authorization for that action; the framework cannot detect intent.

### Neutral
- The gate is read on every invocation rather than cached. This is
  the simplest correct rule given that `rx` writes and `@memo`
  recomputation are already cheap; if a performance reason emerges
  later, a caching strategy can be added without changing the
  surface.
- Channel-level authentication (deciding whether the WebSocket may
  connect at all) is out of scope for this ADR. It is a separate
  concern that may reuse the same reactive-field convention or may
  not; that is a later decision.
- The choice of `403` for the denial code aligns with HTTP
  semantics for "authenticated but not authorized." A future
  protocol revision could differentiate "not yet authorized" from
  "permanently forbidden"; this ADR does not pin that distinction.

## Alternatives Considered

### Option A: `requires=` accepts a callable
`@action(requires=lambda self: self.authorized)`. Rejected because
it bypasses ADR-0005's checkable name convention, hides the gate
from codegen and from any future "show me everything that gates X"
tooling, and re-opens the door to the same hand-rolled inspection
v0.0.x had. The reactive-field-plus-`@memo` combination already
covers any condition a lambda could express, in a form the
framework can see.

### Option B: Gate may be any class/instance attribute
Permit a plain `authorized: bool = False` and read it on
invocation. Rejected because such an attribute is invisible to the
client and to codegen, and "assigning to an attribute" is not part
of the reactive contract — there is no mechanism to inform clients
when the gate flips. Requiring `rx`/`@memo` keeps the gate inside
the system that already handles change propagation.

### Option C: Meta is AND with per-action `requires=`
Both must be truthy. Rejected because the common shape of the
feature is "most actions need the same gate, one or two need
something stronger or weaker." AND-ing forces the developer to
restate the channel-level gate inside the per-action `requires=`
whenever they want to *add* a condition, and offers no way to
*replace* it short of `anonymous=True`. Override gives both
shapes cleanly: the per-action `requires=` is the action's full
gate, and `anonymous=True` is the explicit bypass.

### Option D: Keep the Meta name as `action_requires`
Use the name already shipped in commit 8c65886. Rejected because
the name primes a cumulative reading and the actual semantics are
override. Renaming to `default_action_requires` matches Django's
`Meta` convention and makes the rule legible from the name alone.
The cost is a small example-file update; the benefit is years of
not having to explain why `action_requires` doesn't stack.

### Option E: Silent denial / channel disconnect on falsy gate
Either return `None` quietly or close the WebSocket. Rejected:
silent denial is undebuggable from the client; channel disconnect
conflates per-action denial with channel-level auth failure. A
`403` protocol frame is the smallest signal that lets the client
distinguish "this specific call is not allowed right now" from
"the session is gone."

## References

- ADR-0004 — The `rx[type](default)` reactive field. The gate
  field is required to be one of these (or a `@memo`).
- ADR-0005 — String references to reactive fields. Defines how
  `requires=` and `default_action_requires` name their target.
- ADR-0006 — `@memo` derived reactive fields. The escape hatch for
  compound gate conditions.
- `examples/backend/authorization/channels.py` — per-action
  `requires='authorized'` example. To be updated so the gate
  field is `rx[bool](False)`.
- `examples/backend/authorization_meta/channels.py` — channel-
  wide gating example. To be updated to use
  `default_action_requires` and a reactive gate field.
- Commit `8c65886` — introduced `Meta.action_requires`; the name
  is superseded by `default_action_requires` per this ADR.
