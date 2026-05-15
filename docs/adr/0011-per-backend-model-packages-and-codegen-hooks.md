# 0011. Reactive model support as per-backend packages on a plugin-extensible core

- **Date:** 2026-05-15
- **Deciders:** Luis Fagundes

## Context

The core package (`rxdjango`) is deliberately dependency-light: Django and
channels only. It owns the channel/`rx` primitives and the `makefrontend`
codegen, and nothing else.

Reactive nested-state fields (`rx.model`, ADR-0010) need more. They are built
on Django REST Framework serializers, so they pull in DRF. They also assume a
particular model backend — the relational Django ORM.

RxDjango aims to support more than the relational ORM. MongoDB and Neo4j both
have Django integrations, and a reactive app could be written purely against
either of them. The model/serialization story differs per backend, so each
backend needs its own reactive-model support.

If relational model support (and therefore DRF) were baked into core, **every**
project would carry the DRF dependency and the relational machinery — including
a pure-MongoDB or pure-Neo4j app that never touches a relational model or a DRF
serializer.

Separately, once model support lives outside core, core's `makefrontend` codegen
must be extensible from the outside: it has to emit TypeScript for `rx.model`
fields without core importing — or depending on — any model package.

## Decision

Split reactive model support out of core into **per-backend packages**, and give
core's codegen a **resolver-registry plugin architecture** so those packages can
extend it without core depending on them.

- `rxdjango` (core) stays Django + channels only: channel/`rx` primitives and
  the `makefrontend` codegen framework.
- Reactive model support ships as separate packages, one per model backend:
  `rxdjango-model` (relational, DRF-based) exists today; MongoDB and Neo4j
  packages are planned. A project installs core plus the model package(s) it
  needs.
- Core's codegen exposes registration hooks — `register_field_ts_type_resolver`,
  `register_module_import_resolver`, `register_channel_extras_resolver`, and
  `register_app_generator`. A model package registers its resolvers at import
  time, so the dependency direction is strictly model-package → core; core has
  no import-time or runtime knowledge of any model package.

## Consequences

### Positive

- Core stays dependency-light: Django + channels only. A pure-MongoDB or
  pure-Neo4j app never carries DRF or the relational model machinery.
- Each backend's model support evolves and versions independently of core and
  of the other backends.
- The resolver registry is a uniform extension seam: a future backend package
  plugs into codegen the same way the relational one does, with no change to
  core.
- The dependency direction is one-way (model package → core), so core can be
  reasoned about and tested without any model package installed.

### Negative / Trade-offs

- More packages to publish and version. A project doing relational reactive
  models installs two packages (`rxdjango` + `rxdjango-model`).
- The plugin seam is global mutable registry state populated as a side effect
  of importing a model package; import ordering and side effects must be kept
  in mind.
- The resolver signatures become a semi-public contract that every backend
  package depends on; changing them ripples to all model packages.

### Neutral

- The resolver-registry architecture was adopted without weighing alternatives.
  It is the minimal seam that satisfies the constraint — no core → model
  dependency — and is treated here as a consequence of the package split rather
  than an independent decision.
- Three model packages are envisioned (relational, MongoDB, Neo4j); only the
  relational one (`rxdjango-model`) exists today.

## Alternatives Considered

### Option A: Bake relational model support into core

Ship `rx.model` and DRF-based relational serialization as part of `rxdjango`
itself. This would be consistent with Django, which ships the relational ORM as
its default. Rejected: it would add a DRF dependency to core, paid by every
project — including pure-MongoDB and pure-Neo4j apps that never use a relational
model or a DRF serializer.

### Plugin architecture alternatives

None were considered. Once core could not depend on the model packages, an
extension seam that inverts the dependency was a requirement, not a choice; the
resolver registry was adopted directly as the mechanism.

## References

- ADR-0001 — Monorepo layout.
- ADR-0010 — `rx.model(serializer)` reactive nested-state fields.
- `packages/model/src/rxdjango_model/__init__.py` — `install_*` hooks run at
  import time.
- `packages/core/src/rxdjango/ts/channels.py` — the `register_*` resolver
  registry.
