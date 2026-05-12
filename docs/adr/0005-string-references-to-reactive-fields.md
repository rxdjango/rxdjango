# 0005. String references to reactive fields

- **Date:** 2026-05-11
- **Deciders:** Luis Fagundes

## Context

Several pieces of the framework need a way for one declaration on a
`ContextChannel` to *name* another reactive field on the same channel:

- `@memo('selected')` declares a derived field that recomputes when the
  named field changes (subject of ADR-0006).
- A future authorization mechanism will accept a `requires=` argument
  whose value is the name of a reactive field that gates the channel or
  an action.
- Further consumers along the same lines are expected (e.g.
  subscriptions, gating of individual actions on specific reactive
  state).

The shape of that "name" is the question this ADR pins, separately from
any individual consumer, because the convention is cross-cutting: once
chosen, it will appear in every place where one class-body declaration
references another.

ADR-0004 forces the question. Under `rx[T](default)`, the class-body
name `selected` *is* an instance of `T` — writing `@memo(selected)`
passes the value `0`, not a handle on the field. There is no in-class
expression that evaluates to "the descriptor for `selected`" without
breaking the property that makes class-body code in ADR-0004 read as
ordinary Python (`FRUITS[selected]`, `fruit[0]`, `selected + 1`). The
descriptor is, by design, invisible at the names it binds.

A reference mechanism therefore has to live one level removed from
ordinary Python name resolution. The two reasonable shapes are a string
(`'selected'`) or some kind of sentinel/proxy object exposed under a
different name. This ADR chooses strings and pins the rules around
them.

## Decision

When one declaration on a `ContextChannel` needs to reference another
reactive field on the same channel, the reference is a **string
containing the field's attribute name**.

- The string is a single top-level identifier matching an `rx[T](...)`
  field or a `@memo(...)` field declared on the same class (or
  inherited from a base `ContextChannel`).
- Dotted paths (`'user.name'`) are **not** part of this ADR. The
  convention covers top-level names only; reaching into structured
  fields is a future extension and will be introduced by a later ADR
  if and when structured reactive fields exist.
- Names are resolved and validated **at class-definition time** —
  typically in the channel's metaclass or `__init_subclass__`, after
  the class body has executed so that forward references work. An
  unknown name raises immediately, with the channel class and the
  offending reference identified.
- For references that cannot be resolved at class-definition time
  (e.g. a reference supplied at call time rather than in a class-body
  decorator), resolution and validation happen at the earliest moment
  the framework can see both the reference and the channel — never
  deferred to first read.
- The reference string is also the source of truth for any codegen or
  diagnostic surface: error messages, generated TypeScript dependency
  metadata, and logs all use the same name the developer wrote.

## Consequences

### Positive
- Very simple to write and implement on this stage, while still allowing
  future support of fields directly
- Django already uses hybrid string/referencing for ForeignKeys, so
  supporting strings is not weird.
- One mechanism serves every cross-field reference site (`@memo`,
  authorization `requires=`, future consumers), so a developer learns
  it once.
- Class-definition-time validation catches typos and renames before any
  channel instance is constructed; the failure mode is "the file won't
  import," which is the loudest signal available.
- The string the developer wrote is the same string that appears in
  errors and codegen, so navigating from a diagnostic back to the
  source is trivial.

### Negative / Trade-offs
- Strings are opaque to static type-checkers and IDEs. A reference to
  `'selectd'` (misspelled) is only caught when the class is loaded, not
  by `mypy` or by "go to definition." Class-definition-time validation
  mitigates this but does not eliminate it.
- Rename refactors do not propagate through strings. A developer who
  renames `selected` to `index` via an IDE rename will not have
  `@memo('selected')` updated automatically.
- The framework cannot prevent a string reference from pointing at a
  non-reactive class attribute that happens to share a name; the
  validator has to check the *kind* of the referenced attribute, not
  just its existence.

### Neutral
- The choice is scoped to references to reactive fields on the *same*
  channel (or its bases). Cross-channel references, if they ever
  exist, are out of scope and would need their own convention.
- Multiple references at a single call site (e.g. a memo that depends
  on two fields) are expected to be expressed as multiple positional
  string arguments, but the exact call shape is a per-consumer concern
  and not pinned here.

## Alternatives Considered

### Option A: Pass the descriptor — `@memo(selected)`
This is a good syntax, that will probably be implemented in the future.
It requires some wiring: ContextChannel metaclass needs to inject the
field name in each RxField at compile time so this field name can be
recovered.

## References

- ADR-0004 — The `rx[type](default)` reactive field. The transparency
  property defined there is what forces references to be strings.
- ADR-0006 — `@memo` derived reactive fields. First consumer of this
  convention.
- `examples/backend/memo/channels.py` — `@memo('selected')` and
  `@memo('fruit')` are the first concrete uses of the convention.
