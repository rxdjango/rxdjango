# ADRs — `rxdjango` (Python) internals

Architecture Decision Records scoped to the implementation of the Python package. These decisions are not visible in the developer-facing API and can be revised without breaking user code or the wire protocol.

ADRs here are **records of accepted decisions**, not a deliberation workflow — a file appears here only after the decision has been made.

## Scope

**In scope:**

- Internal module structure of the Python package.
- Cache, broker, and storage choices (Redis / MongoDB / alternatives) and how they coordinate.
- Signal-handling strategy, broadcast fan-out, ORM integration tactics.
- Test infrastructure and management-command internals.
- TypeScript code-generation internals (templates, writers) that produce client artifacts — but **not** the shape of those artifacts (that is part of the developer API and lives in [`/docs/adr`](../../../docs/adr)).

**Out of scope:** anything visible to a user of RxDjango — wire protocol, `ContextChannel` API, `manage.py makefrontend` contract, generated TS shapes. Those go in [`/docs/adr`](../../../docs/adr).

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
