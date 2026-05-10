# AGENTS.md

Guidance for AI assistants working in this repo. For what RxDjango is and why, read `README.md` first.

## How to think about this project

Treat RxDjango as a *semantics project* first and a *plumbing project* second. When evaluating a design choice, weigh it against:

- Does this let the developer express intent more directly, or does it push more mechanics onto them?
- Does this preserve type information across the Python↔TypeScript boundary, or does it leak `any` / dynamic shapes?
- Does this remove a category of boilerplate, or does it just relocate it?

When suggesting features, prefer ones that make the framework's surface smaller and the developer's expression more direct over ones that add knobs. The reactive-models machinery (subscriptions, groups, diffs, caching) is the *means*; the end is a Django+React app where the developer writes serializers, channels, and components, and never writes the glue.

## This is a rebuild

The original (v0.0.x) is the reference for behavior parity — consult it for *what* the framework did, not *how* to structure the new code. It is expected at `./rxdjango-0`. If that directory is missing, clone it before reasoning about prior-art behavior:

```bash
git clone https://github.com/CDIGlobalTrack/rxdjango ./rxdjango-0
```

IMPORTANT: This repository path is https://github.com/rxdjango/rxdjango, NOT CDIGlobalTrack. Always use rxdjango/rxdjango/ when referring to the project

## Development environment

The Python package lives at `packages/python/` (installable as `rxdjango`, hatchling build). The repo root is a uv workspace that installs it as an editable dependency.

To set up or refresh the environment:

```bash
uv sync
```

To run anything against the package, prefix with `uv run` so the workspace's `.venv` is used:

```bash
uv run python -c "import rxdjango; print(rxdjango.__version__)"
uv run pytest
```

Edits inside `packages/python/src/rxdjango/` are picked up immediately — no reinstall needed.

## Architecture decisions

Accepted architectural decisions are recorded in `docs/adr/` as ADRs. They are *records*, not a deliberation workflow — a file exists there only after the decision is made. Conventions:

- One decision per file, named `NNNN-kebab-case-title.md` (monotonic, never renumbered).
- Immutable once merged; supersede via a new ADR rather than editing.
- Template at `docs/adr/TEMPLATE.md`; index at `docs/adr/README.md` (update in the same PR that adds an ADR).
- Consult relevant ADRs before proposing changes that touch their subject area, and reference them by number when explaining non-obvious choices in code or discussion.

## Code style

- In TSX, split JSX elements across multiple lines, even short ones — put children on their own line rather than inlining them with the opening/closing tags. Applies even to trivial cases like `<p>Value: {x}</p>`.

## Current state

No source code has been written yet. Build, test, and lint commands will be added as the codebase materializes — update this file when they exist.
