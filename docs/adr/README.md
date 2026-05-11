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
| 0002 | [Define the core WebSocket protocol envelope](0002-core-websocket-protocol.md) | 2026-05-09 | Active |
| 0003 | [Inherit the ContextChannel surface from rxdjango v0.0.x](0003-inherit-context-channel-surface.md) | 2026-05-11 | Active |

Status is `Active` by default. Use `Superseded by ADR-NNNN` when replaced.
