# ADRs — `@rxdjango/react` internals

Architecture Decision Records scoped to the implementation of the React client. These decisions are not visible in the developer-facing API and can be revised without breaking user code or the wire protocol.

ADRs here are **records of accepted decisions**, not a deliberation workflow — a file appears here only after the decision has been made.

## Scope

**In scope:**

- Internal module structure of the React/TS package.
- WebSocket connection strategy, reconnection and backoff tactics, `last_update` bookkeeping.
- State-tree rebuild internals, diff application, optimistic-write reconciliation mechanics.
- Build / bundling choices, TypeScript configuration, test infrastructure.

**Out of scope:** anything visible to a user — wire protocol, `useChannelState` API, the shape of generated channel classes, write-method semantics. Those go in [`/docs/adr`](../../../docs/adr).

## Conventions

Same as [`/docs/adr`](../../../docs/adr):

- **Filename:** `NNNN-kebab-case-title.md`, zero-padded, monotonically increasing. The numbering is independent from `/docs/adr/` (each ADR folder has its own counter).
- **One decision per file.**
- **Immutable once merged.** Supersede via a new ADR.
- **Reviewed as PRs.** Link the PR under *References*.

## Authoring

Copy [`/docs/adr/TEMPLATE.md`](../../../docs/adr/TEMPLATE.md) to `NNNN-your-title.md` here and fill it in. Add a row to the index below in the same PR.

## Index

| #    | Title | Date | Status |
| ---- | ----- | ---- | ------ |
| —    | _no ADRs yet_ | | |

Status is `Active` by default. Use `Superseded by ADR-NNNN` when replaced.
