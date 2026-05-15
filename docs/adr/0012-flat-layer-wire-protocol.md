# 0012. Flat-layer wire protocol for `rx.model` nested state

- **Date:** 2026-05-15
- **Deciders:** Luis Fagundes

## Context

`rx.model(serializer)` fields (ADR-0010) carry nested model state. The
developer declares an ordinary nested `ModelSerializer` and reads/writes an
ordinary nested instance on the channel — the nested shape is the experience
we want to preserve.

Sending that nested shape over the wire as-is is the naive option, and it is
the wrong one. A nested payload re-transmits a shared child every time it
appears under a different parent, and a change to one deep instance forces the
whole nested tree to be re-serialized and re-sent. v0.0.x already solved this:
it disassembled the nested serializer into **flat layers**, transported each
instance once tagged with its `_type`, and rebuilt the nested structure on the
client. That mechanism is a proven performance core — it gave a flat transport
and update architecture while keeping the nested experience for developers.

The rebuild keeps that mechanism, but moves it. In v0.0.x the flattened state
was a *single* nested state attached to the channel. Here it is ported into the
`rx.model` field, so it composes with the rest of the `rx` field family and a
channel can carry several such fields (ADR-0010). This is one instance of the
broader flattening the rebuild applies throughout.

## Decision

`rx.model` nested state is transported as **flat, `_type`-tagged layers** and
rebuilt on the client.

- **Compile-time introspection.** When a channel class is built, each
  `rx.model` field's serializer is walked once into a `StateModel` tree
  (`contribute_to_channel`). The walk produces, per node, a *flat* serializer
  (nested serializer fields replaced with primary-key references) and the
  relation map between layers. Serializer-shape errors surface at import time,
  and no introspection happens per request.
- **Flat transport.** Serializing an `rx.model` value yields a list of flat
  dicts, one per instance, each carrying a `_type` marker. A shared child is
  transported once; an update to one instance sends only that instance's layer.
- **Client rebuild.** The generated channel class carries a `_modelFields`
  descriptor — the per-field anchor `_type` and relation map emitted by
  codegen. The frontend `StateBuilder` indexes incoming flat instances by
  `_type:id` and follows the relation map to splice them back into the nested
  shape the serializer declares.

The developer surface stays nested on both sides; the flat layout is an
internal transport detail of `rx.model`.

## Consequences

### Positive

- Proven performance core: each instance is transported once, and an update
  re-sends only the changed instance's layer instead of a whole nested tree.
- The nested developer experience is preserved end to end — a nested serializer
  in the backend, a nested instance in the frontend — with flatness confined to
  the wire.
- Per-request work is minimal: the `StateModel` and relation map are computed
  once at class-build time and the relation map ships as static codegen output.
- Shape errors in a serializer fail loudly at import time, not mid-request.

### Negative / Trade-offs

- The protocol has moving parts on both sides — `StateModel`/flat serializers
  in Python, `StateBuilder`/`_modelFields` in TypeScript — that must agree.
- The client cannot render an instance until every layer it references has
  arrived; a partially-delivered state resolves missing children to `null`.
- `_type`-tagging and id-keyed indexing assume every transported instance has a
  stable identity (`id`); shapes without one are special-cased.

### Neutral

- `_modelFields` is emitted into the generated channel class as static data
  rather than recomputed at runtime.
- The mechanism is ported from v0.0.x; what changed is its home — from a single
  channel-level nested state to a per-field `rx.model` value — as part of the
  rebuild's overall flattening.

## Alternatives Considered

### Option A: Send the nested shape as-is

Serialize and transport the nested instance directly. Rejected: shared children
are re-transmitted under every parent, and any change re-serializes and re-sends
the whole nested tree. This is the cost v0.0.x's flat-layer design exists to
avoid.

### Option B: Keep flattening, but as a single channel-level state

Port the v0.0.x mechanism unchanged — one nested state per channel. Rejected:
it does not compose with the `rx` field family and forecloses multiple nested
states per channel (ADR-0010). Hosting the mechanism inside `rx.model` keeps the
proven core while fitting the rebuilt architecture.

## References

- ADR-0010 — `rx.model(serializer)` reactive nested-state fields.
- `packages/model/src/rxdjango_model/state_model.py` — `StateModel`
  introspection and flat serialization.
- `packages/react/src/StateBuilder.ts` — client-side nested rebuild.
- `packages/model/src/rxdjango_model/ts/models.py` — emits the `_modelFields`
  descriptor consumed by `StateBuilder`.
