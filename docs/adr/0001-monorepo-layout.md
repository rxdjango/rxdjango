# 0001. Adopt a monorepo with per-language packages

- **Date:** 2026-05-05
- **Deciders:** @lfagundes, @isaquebc

## Context

RxDjango is being rebuilt ground-up from the 0.0.x code at [CDIGlobalTrack/rxdjango](https://github.com/CDIGlobalTrack/rxdjango). Before any source lands in the new repo, we needed to decide whether the project would live in one repository or be split into several, and to lock the directory layout that follows from that.

The original 0.0.x repository bundled the React/TypeScript client inside the Python package, which made it awkward to run frontend tests against multiple framework versions. That pain motivated splitting *something* off, and the question became: how far?

The candidates discussed in [issue #1](https://github.com/rxdjango/rxdjango/issues/1):

- **Three repos.** `rxdjango` (umbrella + integration tests + cross-cutting ADRs), `rxdjango-core` (the Python framework), `rxdjango-react` (the React/TS client). Initially favored on the thread.
- **Monorepo, two published artifacts.** A single repo with `packages/python/` and `packages/react/`, publishing `rxdjango` to PyPI and `@rxdjango/react` to npm from the same tag.

The forces in tension:

- RxDjango's value is type-safe Python↔TypeScript glue. The Python serializer and the generated TS SDK share one contract; a breaking change to either is a breaking change to both.
- Integration and end-to-end tests are unavoidable — they exercise both halves together — and need a place to live.
- Release cadence is currently identical across the two halves; there is no concrete pressure to version them independently.
- The project has no source code yet, so discoverability for new contributors weighs more than mature-repo concerns.

## Decision

We will keep RxDjango in a single Git repository organized as a monorepo, with two independently published artifacts:

```
.
├── packages/
│   ├── python/   # `rxdjango` on PyPI
│   └── react/    # `@rxdjango/react` on npm
├── examples/     # integration + end-to-end test apps
└── docs/
    └── adr/     # cross-cutting & developer-API decision records
```

Each package additionally has its own `adr/` folder for implementation-internal decisions. Cross-cutting decisions and the developer-facing API live in `/docs/adr/`.

## Consequences

### Positive
- Changing a serializer, regenerating its TypeScript types, and updating an integration test land in one PR and one CI run. Atomic across the language boundary.
- Integration and end-to-end tests have a natural home (`examples/`) without needing to coordinate three repos.
- One issue tracker, one PR queue, one contributor onboarding path.
- Cross-package ADRs (the Python and TypeScript developer interfaces, kept together) can sit alongside the code they describe.

### Negative / Trade-offs
- The repo carries mixed-language tooling (Python + JS/TS). CI must run both ecosystems.
- Releases need automation that can publish to PyPI and npm from a single tag. Tooling exists (changesets, release-please, etc.) but must be set up.
- A larger checkout for contributors who only care about one half.

### Neutral
- ADRs are split between cross-cutting (`/docs/adr/`) and per-package (`packages/*/adr/`). This is independent of the repo decision — it follows from keeping developer APIs together while letting implementation choices stay local.

## Alternatives Considered

### Option A: Three repositories (`rxdjango`, `rxdjango-core`, `rxdjango-react`)
Initially favored on the issue thread. Rejected because it forces a coordinated release dance across three repos for changes that are inherently atomic, prevents single-PR review of contract changes, and creates a "which python-x works with which react-y" compatibility matrix that the monorepo simply does not need at this stage. The third "umbrella" repo proposed in this option already conceded that the pieces only make sense together — that is the monorepo asking to exist.

### Option B: Two repositories (split only the React client out)
A weaker version of Option A motivated by the 0.0.x pain of running frontend tests against bundled backend code. Rejected for the same atomic-change reason: the separation that pain demanded is between *test runs*, not between repos. A monorepo with independent CI jobs per package solves the original pain without splitting the contract.

## References

- [Issue #1 — Decide repositories layout](https://github.com/rxdjango/rxdjango/issues/1)
- [Original RxDjango 0.0.x](https://github.com/CDIGlobalTrack/rxdjango)
