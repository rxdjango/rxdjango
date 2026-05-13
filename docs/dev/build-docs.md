# Building the docs and examples

The root `Makefile` orchestrates two build pipelines that share one input: the MyST docs under `docs/examples/`.

- `tools/docgen/docgen.py` generates React example pages from the docs.
- `site/` holds the Sphinx site, sourced from `docs/examples/`.
- `examples/frontend/` is the React demo app, embedded into doc pages via iframe.

The targets below all run from the repository root.

## `make help` (default)

Prints the target list. Runs when you type `make` with no args.

## `make extract`

Runs `python3 tools/docgen/docgen.py`. Reads `docs/examples/index.md` (toctree → order) and each `docs/examples/<slug>.md`, then regenerates `<Pascal>Page.tsx` for every example plus `pages.generated.ts`. Idempotent — only rewrites files whose contents changed, so it's cheap to run on every build.

## `make docs`

Depends on `extract`. Then delegates to `site/Makefile` (`$(MAKE) -C site html`), which runs `sphinx-build` over `docs/examples/` and writes static HTML into `site/_build/html/`. Result: the Sphinx site, with iframe URLs pointing to wherever `demo_base_url` in `site/conf.py` says (currently `http://localhost:3000`).

## `make examples`

Depends on `extract`. Then runs `npm --prefix examples/frontend run build`, which is `react-scripts build` — produces a production bundle in `examples/frontend/build/`. This is the standalone demo app, with the freshly generated page components baked in.

## `make site`

Depends on `docs` and `examples` (so both run, each pulling `extract` in turn — but `extract` is idempotent so the double-trigger is a no-op the second time). Then:

1. `rm -rf site/_build/html/react`
2. `mkdir -p site/_build/html/react`
3. `cp -R examples/frontend/build/. site/_build/html/react/`

End state: one self-contained directory (`site/_build/html/`) holding the Sphinx HTML at the root and the React app under `/react/`. That's what you'd publish. Note: for this to actually work in production, `demo_base_url` would need to point at `/react` (or the deployed URL) instead of `localhost:3000` — currently the iframes will still target localhost. Worth tightening when you wire up deployment.

## `make dev`

Depends on `extract` (one-shot — no watch mode yet, so editing a `.md` after this starts won't refresh until you re-run `make extract` in another terminal). Then opens a bash subshell that:

1. Installs a `trap` so Ctrl+C (or normal exit) kills the whole process group — both servers die together.
2. Starts `sphinx-autobuild` in the background via `uv run --with sphinx-autobuild` (fetches it ephemerally if not installed). Watches `docs/examples/`, rebuilds on change, serves on port 8000 with browser auto-reload.
3. Starts `npm start` (react-scripts dev server) in the background on port 3000.
4. `wait` blocks until both exit.

Open `http://localhost:8000` for the docs; iframes load demos from `http://localhost:3000`.

## `make check`

Depends on `extract`. Then runs the frontend's local `tsc -p examples/frontend --noEmit` — typechecks the whole React app, including the freshly generated files. This is the guardrail that a bad doc edit can't silently break the build: docgen runs, tsc verifies the output compiles.

## `make clean`

Removes build artifacts only:

1. `make -C site clean` → deletes `site/_build/`
2. `rm -rf examples/frontend/build`

Does *not* touch `pages.generated.ts` or the generated `<Pascal>Page.tsx` files — those track the docs and live in the working tree (currently committed). If you ever decide to gitignore them, `clean` is where you'd add the `rm`.

## Cross-cutting notes

- Every build target chains through `extract` first. That's the single point that enforces "docs are the source of truth" — you can't build either side without regenerating from the docs.
- `extract` is the only target with a real dependency graph; everything else is bookkeeping on top.
- There's no incremental `extract --watch` yet — the dev loop currently has a seam where doc edits don't auto-propagate. That's the next thing to add if dev ergonomics start hurting.
