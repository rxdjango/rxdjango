---
description: Scaffold a new RxDjango example app — creates the Django app, channel, urls, frontend demo, MyST docs, and tests. Use when the user says "create a new app", "scaffold an example", "add a new example", or "/new-app".
allowed-tools: Read, Edit, Write, Bash
---

## new-app skill

This skill scaffolds a new RxDjango example app end-to-end. Examples in this repo are *generated* from MyST docs, so the doc page is the source of truth for the displayed code, but the Django app + frontend demo + tests are hand-written.

The arguments passed to this skill (if any) describe the desired app name and what it should do. If no arguments are given, ask the user:
- A short snake_case app name (e.g. `simple_model`, `counter`)
- A one-line description of what the example should demonstrate
- Which steps to skip, if any

Tests may or may not be required, and if they are, they are boilerplate and probably not functional, so don't mind running them, and only implemented if explicitly requested.

## Reference layout (look at an existing example before writing anything)

Read these to mirror conventions for the new app:

- Backend app: `examples/backend/simple_model/` (channels.py, urls.py, models.py, serializers.py, apps.py, tests/)
- Backend wiring: `examples/backend/backend/settings.py` (INSTALLED_APPS), `examples/backend/backend/urls.py` (APP_URLS list)
- Frontend demo: `examples/frontend/src/app/examples/simple_model/demo.tsx`
- Doc page: `docs/examples/simple_model.md` and its entry in `docs/examples/index.md`
- Tests: `examples/backend/<app>/tests/test_makefrontend.py`, `test_integration.py`, `test_e2e.py` (counter has e2e)

The `*Page.tsx` file alongside `demo.tsx` and `examples/frontend/src/app/examples/pages.generated.ts` are **generated** by `make extract` — never hand-edit them.

## Steps

Work through these in order. Skip steps the user said to skip. Commit at the end (memory: always commit without asking).

**Step 1 — Create the Django app.**

```bash
cd examples/backend && uv run ./manage.py startapp <app_name>
```

Then:
- Delete unneeded scaffolding (`views.py` can stay empty, `admin.py` and `tests.py` usually go — replace `tests.py` with a `tests/` package).
- Set `apps.py` `name = '<app_name>'` (no `examples.backend.` prefix — apps are imported flat).
- Write `models.py` only if the example needs DB models. Run `uv run ./manage.py makemigrations <app_name>` afterwards.

**Step 2 — Register the app in settings.**

Edit `examples/backend/backend/settings.py`: add `'<app_name>',` to `INSTALLED_APPS` (in the trailing group with the other example apps, not alphabetically — match existing order).

**Step 3 — Create `channels.py`.**

Subclass `ContextChannel`. Class name is PascalCase of the app name + `Channel` (e.g. `simple_model` → `SimpleModelChannel`). Use `rx.model`, `rx.state`, `@action` decorators as needed. Imports come from `rxdjango`:

```python
from rxdjango import ContextChannel, rx, action
```

If a serializer is needed, create `serializers.py` with a DRF `ModelSerializer` and reference it via `rx.model(YourSerializer())` in the channel. The serializer is auto-tracked for TS generation.

**Step 4 — Create `urls.py` with the websocket route.**

```python
from django.urls import path
from .channels import <PascalName>Channel

urls = []

websocket_urls = [
    path('ws/<app_name>/', <PascalName>Channel.as_asgi()),
]

urlpatterns = urls
```

`urls` stays empty unless the example needs HTTP views.

**Step 5 — Include in main urls.py.**

Edit `examples/backend/backend/urls.py`: import `from <app_name> import urls as <app_name>_urls` and append `<app_name>_urls` to the `APP_URLS` list. Keep ordering consistent with `INSTALLED_APPS`.

**Step 6 — Implement the example behavior.**

Fill in channel actions, models, serializers as the user described. Keep it minimal — examples illustrate one idea each.

**Step 7 — Run `makefrontend` to generate TS bindings.**

```bash
cd examples/backend && uv run ./manage.py makefrontend
```

This writes `examples/frontend/src/app/rx/<app_name>/<app_name>.channels.ts` (and `.models.ts` if `rx.model` is used). Verify the file exists and looks right.

If this fails, leave it, and tell user at the end that this failed.

**Step 8 — Create the frontend demo.**

Write `examples/frontend/src/app/examples/<app_name>/demo.tsx`. Export `<PascalName>Demo` (and a `default`). Import the generated channel from `../../rx/<app_name>/<app_name>.channels`. Use `useChannel(...)` plus the shared widgets from `../../components/demo` (`Sections`, `Button`, `TextInput`, `Row`, `Note`, etc. — read existing demos for the catalog).

Code style (from CLAUDE.md): in TSX, **split JSX elements across multiple lines** even short ones — children on their own line, never inlined with tags.

Do NOT create the `*Page.tsx` file — that's generated.

**Step 9 — Write `docs/examples/<app_name>.md`.**

Format:

```markdown
# <Title Case Name>

<one-paragraph description of what this example demonstrates>

```{rxdemo} <app_name>
```

## Backend

```{literalinclude} ../../examples/backend/<app_name>/channels.py
:language: python
```

## Frontend

```{literalinclude} ../../examples/frontend/src/app/examples/<app_name>/demo.tsx
:language: tsx
```
```

Add extra `## Section` + `literalinclude` blocks for models/serializers if they're central to the example.

**Step 10 — Add to `docs/examples/index.md`.**

Append `<app_name>` to the toctree. Order matches the order examples should appear in the site nav.

**Step 11 — Run `make extract` to regenerate React pages.**

```bash
make extract
```

This regenerates `examples/frontend/src/app/examples/<app_name>/<Pascal>Page.tsx` and updates `pages.generated.ts`. Both are `// @generated` — leave them alone.

**Step 12 — Write tests.**

Create `examples/backend/<app_name>/tests/__init__.py` (empty) plus:

- `test_makefrontend.py` — verifies the generated TS file contains the expected interface and that the channel imports the model type. Mirror `examples/backend/simple_model/tests/test_makefrontend.py`.

- `test_integration.py` — drives the channel from a Node-backed JS runtime via `RxIntegrationTestCase`. Set `app_label`, `channel`, `url`. Use `self.eval(...)`, `self.wait_for(...)`, `self.get_result(...)`. Mirror `examples/backend/simple_model/tests/test_integration.py`.

- `test_protocol.py` - same base harness as integration, with extra wiring to track all exchanged messages. Mirror `examples/backend/counter/tests/test_procol.py`.

- `test_e2e.py` — Playwright browser test via `RxE2ETestCase`. Use `self.goto_demo('examples/<app_name>')` and `expect(...)` assertions. Mirror `examples/backend/counter/tests/test_e2e.py`.

Do not run the suite. This task is preparing for development, not developing yet.

**Step 13 — Commit.**

Stage every new/modified file (Django app, settings, main urls, generated rx/, frontend demo, docs, index, generated pages, tests) and commit with a message like `feat: add <app_name> example`. Per saved feedback, commit without asking.

## Notes

- App names are snake_case throughout (Python module, doc slug, URL path). The frontend dir mirrors that. Component/class names are PascalCase.
- If you add an `rx.model` field, regenerating with `make extract` alone is **not** enough — `makefrontend` (step 7) must run first to refresh the TS bindings that the demo imports.
- If a step fails (e.g. test failure, TS generation error), fix the underlying issue rather than skipping. Never bypass hooks or weaken assertions to make things green.

## Constrainsts

- Do not edit any files in packages/ folder
