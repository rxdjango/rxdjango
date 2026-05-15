# 0010. `rx.model(serializer)` reactive nested-state fields

- **Date:** 2026-05-15
- **Deciders:** Luis Fagundes

## Context

`rx[T](default)` (ADR-0004) covers *scalar* reactive fields. The bulk of what
RxDjango v0.0.x did — forwarding nested model state to the client — still needs
a way into a channel.

v0.0.x expressed nested state through a state-forwarding architecture, but it
supported only **one state per channel**. That was a real limitation: a channel
that needed to expose two independent nested structures had no way to do it.
The rebuild reuses that state-forwarding architecture but lifts the restriction
— a channel may now declare **several** nested-state fields.

The goal was to make nested-state fields sit in the **same `rx` field family**
as scalar fields: collected by the same `ContextChannelMeta`, same descriptor
protocol. But the `rx[T]` form has a hard constraint — the descriptor *is* a
`T`. For nested state there is **no single `T`**: the backend stores a Django
`Model` instance, while the frontend sees an object *shaped by the serializer*.
The stored type and the wire/client type genuinely differ.

## Decision

Declare nested reactive state on a `ContextChannel` as `rx.model(serializer)`.

- The serializer is the single source of truth — it drives backend flattening
  and the generated frontend types.
- Multiple `rx.model` fields may be declared per channel. This generalises the
  v0.0.x state-forwarding architecture, which was limited to one state per
  channel.
- Frontend TypeScript interfaces are generated per-app into `<app>.models.ts`
  (the file is ported from v0.0.x and renamed to `.models.ts`). Generated
  channel files `import type` from that file.

`rx.model()` is a distinct namespace, not a subscript form, because the
backend/frontend type asymmetry means there is no single type parameter that
honestly describes the field.

## Consequences

### Positive

- `rx.model` is an `RxField` like the scalars — same metaclass collection, same
  descriptor protocol, one consistent channel surface.
- Several nested states per channel, lifting the one-state-per-channel limit of
  the v0.0.x state-forwarding architecture while reusing its design.
- The `.model` namespace reads as intent: a developer sees immediately that
  this is a nested-state field, not a scalar.
- The serializer is one declaration that drives both backend serialization and
  the generated frontend types.

### Negative / Trade-offs

- Two declaration forms (`rx[T](...)` vs `rx.model(...)`) — the visual symmetry
  of `rx[T]` is broken.
- The backend/frontend type asymmetry is now baked into the field: the
  developer relies on generated types to keep client code in sync with the
  serializer.

### Neutral

- `.models.ts` naming is ported from v0.0.x (renamed).
- `rx.model` is installed onto `rx` by the `rxdjango-model` package; it only
  exists when that package is installed.

## Alternatives Considered

### Option A: `rx[T](default)` subscript form

Reuse the scalar declaration form for nested state. Rejected: no single `T` is
correct on both sides of the boundary (`Model` in the backend, serializer-shaped
in the frontend), so the "descriptor is a `T`" property of ADR-0004 cannot hold.

### Option B: `rx(serializer)`

A hybrid typed form parallel to `rx[T]` but without the subscript. Rejected: it
visually resembles the scalar form but behaves differently, and is less explicit
about what kind of field it is.

### Option C: `rx[ModelClass](serializer)`

Subscript with the Django model class. Rejected: the model class only describes
the *backend* type; the frontend type is serializer-shaped, so the subscript
would be misleading and redundant with the serializer argument.

## References

- ADR-0004 — The `rx[type](default)` reactive field.
- `packages/model/src/rxdjango_model/fields.py` — `RxModelField` and the
  `rx.model()` factory.
- `packages/model/src/rxdjango_model/ts/models.py` — per-app `.models.ts`
  interface generation.
