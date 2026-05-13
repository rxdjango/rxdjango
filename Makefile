# Root orchestrator — docs are the source of truth for example pages.
#
# Flow:
#   docs/examples/*.md  -- tools/docgen -->  examples/frontend/src/app/examples/**/<Pascal>Page.tsx
#                                            + pages.generated.ts
#   site/               -- sphinx-build -->  site/_build/html
#   examples/frontend/  -- react-scripts -->  examples/frontend/build
#   `make site` stitches the React build into the Sphinx output under /examples/.

SHELL        := /bin/bash

PYTHON       ?= python3
NPM          ?= npm
UVRUN        ?= uv run
SPHINXBUILD  ?= $(UVRUN) sphinx-build

FRONTEND      = examples/frontend
BACKEND       = examples/backend
PID_FILE      = backend.pid
ENV_FILE      = .env
REACT_PACKAGE = packages/react
SITE          = site
SITE_BUILD    = $(SITE)/_build/html
FRONT_BUILD   = $(FRONTEND)/build
EXAMPLES_OUT  = $(SITE_BUILD)/react

.DEFAULT_GOAL := help

.PHONY: help extract react-package docs examples site dev check clean deploy

help:
	@echo "Targets:"
	@echo "  make extract   Generate React example pages from docs/examples/"
	@echo "  make react-package  Build @rxdjango/react -> $(REACT_PACKAGE)/dist"
	@echo "  make docs      Build the Sphinx site (HTML) -> $(SITE_BUILD)"
	@echo "  make examples  Build the React examples app -> $(FRONT_BUILD)"
	@echo "  make site      Build docs + examples and stitch into $(SITE_BUILD)"
	@echo "  make dev       Live-reload dev: sphinx-autobuild + react dev server"
	@echo "  make check     Run docgen + tsc --noEmit on the frontend"
	@echo "  make clean     Remove all build artifacts"
	@echo "  make deploy    Build site then restart the gunicorn backend"

extract:
	@$(PYTHON) tools/docgen/docgen.py

react-package:
	@if [ ! -x "$(REACT_PACKAGE)/node_modules/.bin/tsup" ]; then \
		$(NPM) --prefix $(REACT_PACKAGE) install; \
	fi
	@$(NPM) --prefix $(REACT_PACKAGE) run build

docs: extract
	@$(MAKE) -C $(SITE) html SPHINXBUILD="$(SPHINXBUILD)"

examples: extract react-package
	@$(NPM) --prefix $(FRONTEND) run build

site: docs examples
	@rm -rf $(EXAMPLES_OUT)
	@mkdir -p $(EXAMPLES_OUT)
	@cp -R $(FRONT_BUILD)/. $(EXAMPLES_OUT)/
	@echo "site: stitched examples into $(EXAMPLES_OUT)"

# Run docgen once, then sphinx-autobuild and the React dev server in parallel.
# Edits to docs/examples/*.md currently require re-running `make extract`
# (docgen --watch is not implemented yet).
dev: extract react-package
	@trap 'kill 0' INT TERM EXIT; \
	$(UVRUN) --with sphinx-autobuild sphinx-autobuild \
		-c $(SITE) docs $(SITE_BUILD) --port 8000 & \
	$(NPM) --prefix $(FRONTEND) start & \
	wait

check: extract react-package
	@$(FRONTEND)/node_modules/.bin/tsc -p $(FRONTEND) --noEmit

deploy: site
	@if [ -f $(PID_FILE) ]; then \
		OLD_PID=$$(cat $(PID_FILE)); \
		if kill -0 "$$OLD_PID" 2>/dev/null; then \
			echo "Stopping existing process (PID $$OLD_PID)..."; \
			kill "$$OLD_PID"; \
			sleep 1; \
		fi; \
		rm -f $(PID_FILE); \
	fi
	@if [ -f $(ENV_FILE) ]; then set -a && source $(ENV_FILE) && set +a; fi
	@cd $(BACKEND) && \
		../../.venv/bin/gunicorn backend.asgi:application \
		--bind 127.0.0.1:8000 \
		-w 1 \
		-k uvicorn.workers.UvicornWorker \
		--pid ../../$(PID_FILE) \
		--daemon
	@echo "Backend started (PID $$(cat $(PID_FILE)))"

clean:
	@$(MAKE) -C $(SITE) clean
	@rm -rf $(FRONT_BUILD)
