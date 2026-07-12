# 0015. Everything derivable from the serializer tree is derived at class-creation time

- **Date:** 2026-07-12
- **Status:** Active
- **Deciders:** Luis Fagundes

## Context

RxDjango's `StateModel` introspects a nested `ModelSerializer` tree, and a
growing amount of framework machinery is *derivable* from that tree: the flat
per-layer serializers, the frontend relation map, the `instance_type` →
field-name routing map the consumer uses to route broadcasts, the reactive
broadcast groups a row change must reach, and — prospectively — the batched
query plan for initial-state delivery (the StateModel tree *is* the
prefetch plan).

The intention, held since v0.0.x and throughout the rebuild, has always been
that all of this is computed **once, at class-creation (import) time**. That
intention was never stated as a decision, and the result was repeated drift in
agent-driven work toward per-connection and per-message derivation. Observed
drifts, all since corrected:

- Flat serializers were instantiated on every save — DRF re-deepcopies all
  declared fields per instantiation, making per-save construction ~25× slower
  than calling `to_representation()` on a shared, pre-bound instance
  (fixed in `1a2418c`, `packages/model/src/rxdjango_model/state_model.py`).
- `rx.model` assignment paid the full serialization cost even when no
  consumer was bound to deliver to (fixed in `dba37b8`).
- Reactive group names and the broadcast-routing index were derived per
  message by re-scanning payloads, rather than once from the tree
  (moved to compile time in `2863e8a`,
  `RxModelField.contribute_to_channel`).

Each fix was correct in isolation, but nothing prevented the next drift,
because the rule they all follow existed only as unstated intention. ADRs
0010–0012 imply it ("compile-time introspection", "produced at compile
time") without committing to it.

## Decision

**Everything derivable from the serializer tree is derived once at
class-creation time — never per-connection, never per-message.**

Runtime work touches only per-request *data*: model rows, payloads, queue
contents. *Structure* — serializer instances, relation maps, routing maps,
broadcast group derivations, query plans — is computed when the channel class
is created (at import, via `ContextChannelMeta` /
`contribute_to_channel`) and reused for the life of the process.

The bright-line test for reviews, human or agent: **if code computes
something from the serializer tree after import time, it is wrong** — either
the computation moves to class creation, or what it produces was not actually
derivable from the tree.

Corollary invariant: because derivation happens once, the flat serializer is
one shared, pre-bound, *mutable* DRF instance reused across all
serializations of a node. Per-call serializer state is therefore forbidden,
and `to_representation()` is assumed reentrant. Code that needs per-call
state must carry it outside the serializer.

Sanctioned exception: `RxModelField.serialize` keeps a lazy `StateModel`
fallback for channel classes built outside the metaclass (raw use in tests).
It is a test convenience, not a pattern to extend.

## Consequences

### Positive

- Structural cost is O(1) per process instead of O(connections) or
  O(messages); hot paths pay only for data.
- Serializer-shape errors surface at import — at startup, loudly — instead of
  mid-request on the first unlucky connection.
- Reviewers and agents get a mechanical rule instead of having to infer
  intent; the drift pattern this ADR exists to stop becomes rejectable on
  sight.
- Future work inherits the rule by default: the layered-walk query plan for
  initial-state delivery is a compile-time artifact of the same tree.

### Negative / Trade-offs

- Import time and resident memory grow with the channel surface — every
  channel's full derivation is built and held whether or not it is ever
  connected to.
- The shared bound serializer forbids per-call serializer state and assumes
  `to_representation` reentrancy; this constraint is invisible at the call
  site and must be protected by this record.
- Runtime-parameterized serializer shapes (e.g. per-connection field sets)
  are out of scope by construction; supporting them would require a new ADR
  superseding this one.
- Registries derived across channel classes (routing maps, the reactive
  index) are only complete once all channel modules are imported; import
  order and app-loading discipline matter.

### Neutral

- ADRs 0010–0012 already implied this rule; it is now explicit and citable.
- The lazy fallback in `RxModelField.serialize` remains, documented as a
  test-convenience exception.

## Alternatives Considered

### Option A: Derive lazily, per connection or per message

The drift pattern itself: build serializers, scan payloads for groups, or
introspect the tree wherever the result is first needed.

**Rejected.** Charges structural work to hot paths (measured at ~25× on the
serializer case), hides shape errors until runtime, and — demonstrated by
this project's own history — is the default agents fall into when the rule is
unstated.

### Option B: Derive on first use, memoized

Compute lazily but cache, amortizing the cost.

**Rejected.** Avoids repeat cost but keeps errors late, makes first-use
latency unpredictable, and offers no bright-line rule: "is this memoized
high enough?" replaces "is this computed at import?", which is exactly the
ambiguity that produced drift.

### Option C: Record each instance case-by-case

Keep pinning individual fixes with tests and code comments, or fold the
principle into the layered-state-delivery ADR when it is promoted.

**Rejected.** Buries a general rule inside specific documents. The
individual fixes were already pinned and drift happened anyway; the rule has
to exist at the level where new work looks for constraints.

## References

- ADR-0010, ADR-0011, ADR-0012 — the `rx.model` / flat-layer architecture
  this rule governs.
- Commits `1a2418c` (shared pre-bound flat serializer), `dba37b8` (skip
  serialization when unbound), `2863e8a` (group/index derivation moved to
  compile time).
- `packages/model/src/rxdjango_model/state_model.py` (`StateModel.__init__`),
  `packages/model/src/rxdjango_model/fields.py`
  (`RxModelField.contribute_to_channel`) — where class-creation derivation
  lives.
