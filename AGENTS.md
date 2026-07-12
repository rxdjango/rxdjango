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

The Python package lives at `packages/core/` (installable as `rxdjango`, hatchling build). The repo root is a uv workspace that installs it as an editable dependency.

To set up or refresh the environment:

```bash
uv sync
```

To run anything against the package, prefix with `uv run` so the workspace's `.venv` is used:

```bash
uv run python -c "import rxdjango; print(rxdjango.__version__)"
uv run pytest
```

Edits inside `packages/core/src/rxdjango/` are picked up immediately — no reinstall needed.

## Running the demo site

`make demo` (a wrapper around `scripts/demo.sh`) sets up and runs the whole demo: the Django/Channels backend on `:8000` and the React frontend on `:3000`, both in the foreground until you Ctrl-C. Setup is idempotent, so re-running it is cheap.

It exists because three prerequisites are easy to miss: a reachable **Redis** (the channel layer is `channels_redis` with no in-memory fallback — reactive broadcasts silently vanish without it), a built **`packages/react`** (the frontend depends on it via a `file:` path), and **`migrate`** (the demo's seed data ships as data migrations).

Useful variants: `make demo-setup` / `scripts/demo.sh --setup-only` (prepare without starting), `--no-setup` (skip straight to running), `--backend-only` / `--frontend-only`. `BACKEND_PORT`, `FRONTEND_PORT`, and `REDIS_URL` override the defaults.

Do not confuse this with `make dev`, which serves the *docs* (sphinx-autobuild) and also binds port 8000 — the two cannot run at the same time.

## Architecture decisions

Accepted architectural decisions are recorded in `docs/adr/` as ADRs. They are *records*, not a deliberation workflow — a file exists there only after the decision is made. Conventions:

- One decision per file, named `NNNN-kebab-case-title.md` (monotonic, never renumbered).
- Immutable once merged; supersede via a new ADR rather than editing.
- Template at `docs/adr/TEMPLATE.md`; index at `docs/adr/README.md` (update in the same PR that adds an ADR).
- Consult relevant ADRs before proposing changes that touch their subject area, and reference them by number when explaining non-obvious choices in code or discussion.

## Examples: docs are the source of truth

The example pages shown in `examples/frontend/` are *generated* from the MyST docs in `docs/examples/`. Do not hand-edit the generated files.

- Source: `docs/examples/index.md` (toctree → ordering) and `docs/examples/<slug>.md` (H1 → title, lead paragraph → description, each `## Section` + `literalinclude` → a page section).
- Generator: `tools/docgen/docgen.py` (stdlib Python, no extra deps). Run with `make extract` (or `python3 tools/docgen/docgen.py` directly) from the repo root.
- Build orchestration lives in the root `Makefile`: `make docs` (Sphinx → `site/_build/html`), `make examples` (React → `examples/frontend/build`), `make site` (both, stitched), `make dev` (sphinx-autobuild + react dev server in parallel), `make check` (docgen + `tsc --noEmit`). All build targets depend on `extract`.
- Generated outputs (carry a `// @generated` header — never edit by hand):
  - `examples/frontend/src/app/examples/<slug>/<Pascal>Page.tsx`
  - `examples/frontend/src/app/examples/pages.generated.ts` (consumed by `Main.tsx`)
- Hand-written, lives next to the generated page: `examples/frontend/src/app/examples/<slug>/demo.tsx` (the actual interactive demo).
- To add a new example: create `docs/examples/<slug>.md`, add the slug to the toctree in `docs/examples/index.md`, write `examples/frontend/src/app/examples/<slug>/demo.tsx` exporting `${Pascal}Demo`, then run the generator.
- Conventions enforced by the generator: slug → PascalCase for component names; `literalinclude` paths under `examples/frontend/` mark a section as frontend (adds `ExampleClientBadge`); section ids are `${kebab-slug}-${section-name-lower}`.

## Code style

- In TSX, split JSX elements across multiple lines, even short ones — put children on their own line rather than inlining them with the opening/closing tags. Applies even to trivial cases like `<p>Value: {x}</p>`.

## Running tests

The test suite is the Django suite under `examples/backend`, run with Django's
own test runner:

```bash
cd examples/backend && uv run ./manage.py test
```

This runs 49 tests (integration, protocol, makefrontend, and e2e). Two
prerequisites:

- **Node toolchain on PATH** — the integration suite builds `packages/react`
  via `npm run build` on first run, so `npm` and `node` must be available.
- **Playwright browser** — the e2e tests drive a real browser. Install it once
  with `uv run playwright install chromium` from the repo root, or the 8 e2e
  tests error out with a missing-browser-runtime message.

> Note: there is currently no pytest suite for the `rxdjango` core package, and
> no pytest config at the repo root. Running a bare `uv run pytest` fails during
> collection (it tries to import the Django example apps and the `rxdjango-0`
> reference checkout without `DJANGO_SETTINGS_MODULE`). Use the Django runner
> above.
