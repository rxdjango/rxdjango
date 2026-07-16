# Architecture Decision Records

This directory records architectural decisions for RxDjango. ADRs here are
**records of accepted decisions** — not a workflow for deliberation. A file
exists in this directory only after the decision has been made.

## Conventions

- **Filename:** `NNNN-kebab-case-title.md`, zero-padded, monotonically
  increasing. Numbers are never reused or renumbered.
- **One decision per file.** Keep scope tight so each can be revisited
  independently.
- **Immutable once merged.** If a decision changes, write a new ADR that
  supersedes the old one. Add a `Superseded by ADR-NNNN` line at the top of the
  superseded file, but do not rewrite its body.
- **Reviewed as PRs.** The PR discussion is part of the record — link it under
  *References*.
- **Link from code** when an ADR explains a non-obvious choice in the source
  (e.g. `# See ADR-0002`).

## Authoring

Copy [`TEMPLATE.md`](./TEMPLATE.md) to `NNNN-your-title.md` and fill it in. Add
a row to the index below in the same PR.

## Index

| #    | Title | Date | Status |
| ---- | ----- | ---- | ------ |
| 0001 | [Monorepo layout](./0001-monorepo-layout.md) | 2026-05-05 | Active |
| 0002 | [Define the core WebSocket protocol envelope](0002-core-websocket-protocol.md) | 2026-05-09 | Active |
| 0003 | [Inherit the ContextChannel surface from rxdjango v0.0.x](0003-inherit-context-channel-surface.md) | 2026-05-11 | Active |
| 0004 | [The `rx[type](default)` reactive field](0004-rx-type-reactive-field.md) | 2026-05-11 | Active |
| 0005 | [String references to reactive fields](0005-string-references-to-reactive-fields.md) | 2026-05-11 | Active |
| 0006 | [`@memo` derived reactive fields](0006-memo-derived-reactive-fields.md) | 2026-05-11 | Active |
| 0007 | [Action authorization via a reactive gate field](0007-action-authorization-via-rx-gate.md) | 2026-05-11 | Active |
| 0008 | [`rx[bool]` is exempt from the "descriptor is a T" rule](0008-rx-bool-non-subclassable.md) | 2026-05-12 | Active |
| 0009 | [Adopt Sphinx as the main docs site with React examples stitched under `/react`](0009-sphinx-react-stitched-site.md) | 2026-05-13 | Active |
| 0010 | [`rx.model(serializer)` reactive nested-state fields](0010-rx-model-reactive-nested-state.md) | 2026-05-15 | Active |
| 0011 | [Reactive model support as per-backend packages on a plugin-extensible core](0011-per-backend-model-packages-and-codegen-hooks.md) | 2026-05-15 | Active |
| 0012 | [Flat-layer wire protocol for `rx.model` nested state](0012-flat-layer-wire-protocol.md) | 2026-05-15 | Active |
| 0013 | [Use a `ReactiveModel` base class to weld per-row versions to writes](0013-reactive-model-base-class.md) | 2026-05-14 | Active |
| 0014 | [Client-side version watermarks for layer consistency](0014-client-side-version-watermarks.md) | 2026-05-15 | Active |
| 0015 | [Everything derivable from the serializer tree is derived at class-creation time](0015-compile-time-derivation-from-serializer-tree.md) | 2026-07-12 | Active |
| 0016 | [Layered state delivery and the per-instance cache direction](0016-layered-state-delivery.md) | 2026-07-12 | Active |
| 0017 | [Reactive list fields with delta operations](0017-reactive-list-fields.md) | 2026-07-16 | Active |
| 0018 | [Route live list delivery through per-field Router declarations](0018-router-based-list-delivery.md) | 2026-07-15 | Active |

Status is `Active` by default. Use `Superseded by ADR-NNNN` when replaced.
