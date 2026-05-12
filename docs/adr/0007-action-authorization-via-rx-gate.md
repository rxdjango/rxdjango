# 0007. Action authorization via a reactive gate field

- **Date:** 2026-05-11
- **Deciders:** Luis Fagundes

## Context

Since we removed nested authentication from v0.0.1, channel starts always
anonymously and have privileges raised along execution. So actions need
some authorization form and this will quickly spread boilerplates if
not handled in an simple way.

This has to be done so that client knows if an action is authorized or not,
so to avoid displaying interface for calling unauthorized actions.

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
  authorization."
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
