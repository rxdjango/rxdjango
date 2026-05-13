# 0009. Adopt Sphinx as the main docs site with React examples stitched under `/react`

- **Date:** 2026-05-13
- **Deciders:** Luis Fagundes and Gabriel Furlan

## Context

RxDjango needs a documentation site whose example pages stay in perfect sync
with runnable demos in the React example app. Two pressures shape the choice:

- **Framework agnosticism.** RxDjango is designed to grow beyond React (Vue is
  the obvious next target). The doc site must not be tied to React.
- **Sync without manual work.** Earlier iterations carried hand-written prose
  alongside hand-written example pages and they drifted. Whatever we ship must
  keep them aligned automatically, not by discipline.
- **Team shape.** Gabriel Furlan (deep React experience) is the natural author
  of the example app's layout and UX. Luis carries the Sphinx/MyST side. If
  both sides require Gabriel's bandwidth, the doc work becomes a bottleneck.
- **Dev ergonomics.** Sphinx in the inner loop is friction for contributors who
  only touch the framework or examples. A React dev server is the path of
  least resistance day-to-day.
- **SEO.** The public site needs to be crawlable as static HTML. A React-only
  site would require SSR (Next.js or equivalent) — additional complexity for a
  benefit Sphinx delivers for free.

## Decision

The published documentation is a static **Sphinx site** built from MyST sources
under `docs/examples/`. The React example app is built separately and stitched
into the Sphinx output at `/react/`; individual demos are embedded into Sphinx
pages via iframe pointing at a dedicated `/react/<slug>/demo` route that
renders the demo bare (no surrounding example chrome).

MyST docs are the **source of truth for page structure**.
`tools/docgen/docgen.py` reads `docs/examples/*.md` and regenerates the React
app's `<Pascal>Page.tsx` files and `pages.generated.ts` index. The React app
is the **layout reference** — Gabriel iterates on the React composition; Luis
(with AI assistance) mirrors that layout into the Sphinx templates under
`site/_templates/` and `site/_static/`. The two surfaces are designed to look
near-identical so the iframe seam is invisible.

Packaging is one self-contained directory. `make site` produces
`site/_build/html/` containing the Sphinx HTML at the root plus the React
production bundle copied to `site/_build/html/react/`. The React app remains
reachable for developers at `/react`, but is not linked from the main site —
end users only ever see Sphinx pages with iframed demos. Inside the inner dev
loop, `make dev` runs `sphinx-autobuild` on port 8000 and `npm start` on port
3000 in parallel; `make extract` (the docgen step) is a dependency of every
build target so docs are always the input.

## Consequences

### Positive
- Framework-agnostic doc site: adding Vue (or any other) examples later means
  another sub-app stitched under another path, not rewriting the doc site.
- Docs and example-page structure cannot drift: changes to a
  `docs/examples/*.md` regenerate the React page, and `make check` (tsc) is
  the guardrail.
- Static HTML for SEO with no SSR machinery.
- Gabriel is unblocked: he codes the React app freely; Luis mirrors layout
  into Sphinx asynchronously. Neither blocks the other.
- Developer inner loop stays React-native — the React app is the day-to-day
  surface for contributors; Sphinx only runs when docs are touched.

### Negative / Trade-offs
- The Sphinx templates and the React layout must be hand-kept visually
  similar. There is no automation enforcing parity; visible drift will require
  manual reconciliation.
- Iframe embedding has known costs: an extra HTTP round trip per demo,
  double-loaded React runtime per page, no shared scrollbar/keyboard focus,
  and a same-origin assumption (the deployed React bundle must live at the
  same origin as the Sphinx site).
- Two build pipelines (Sphinx, react-scripts) plus a codegen step is more
  moving parts than a single framework would be. The root `Makefile` exists
  to hide that complexity.

### Neutral
- `examples/frontend/build/` and `site/_build/html/` are both build artifacts;
  the canonical deliverable is `site/_build/html/` after `make site` stitches
  them.
- Generated TSX files (`<Pascal>Page.tsx`, `pages.generated.ts`) carry an
  `@generated` header and are currently committed to the working tree.
  Whether to gitignore them is a follow-up, not part of this decision.
- The `/react` route is reachable in production. It is not advertised, but
  this is an open-source project — anyone can clone the repo and run the same
  app locally, so there is no surface here that isn't already public.

## Alternatives Considered

### Option A: A single React app serving the whole documentation (Gabriel's proposal)
One codebase, one build, no codegen, no Sphinx templates to mirror. Rejected
on two grounds. First, framework lock-in: the doc site becomes a React app
and onboarding Vue (or anything else) means either rebuilding the site or
hosting a React doc site for a Vue framework, which is incoherent. Second,
SEO requires SSR (Next.js or equivalent), which is unnecessary complexity for
a documentation site that is fundamentally static content. A third practical
concern: every doc edit would require Gabriel's bandwidth, making him a
bottleneck.

### Option B: Jupyter Book / executable notebooks
Considered briefly. Rejected: the value proposition (executable Python cells
inline with prose) does not match the task. Our demos are interactive React
components talking to a Django backend over WebSocket, not Python cells
producing static output. Jupyter Book would not remove the React build; it
would only replace Sphinx with a less appropriate doc tool.

## References

- `Makefile` — `extract`, `docs`, `examples`, `site`, `dev`, `check`, `deploy`
  targets; the orchestrator that enforces docs-as-source-of-truth by making
  every build chain through `extract`.
- `tools/docgen/docgen.py` — MyST → TSX generator.
- `docs/dev/build-docs.md` — narrative guide to the build pipeline.
- `site/conf.py`, `site/_templates/layout.html`, `site/_static/custom.css` —
  the Sphinx side of the layout mirror.
- `examples/frontend/src/app/Main.tsx`,
  `examples/frontend/src/app/examples/pages.generated.ts` — the React side;
  consumes the codegen output.
