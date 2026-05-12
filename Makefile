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

FRONTEND      = examples/frontend
SITE          = site
SITE_BUILD    = $(SITE)/_build/html
FRONT_BUILD   = $(FRONTEND)/build
EXAMPLES_OUT  = $(SITE_BUILD)/examples

.DEFAULT_GOAL := help

.PHONY: help extract docs examples site dev check clean

help:
	@echo "Targets:"
	@echo "  make extract   Generate React example pages from docs/examples/"
	@echo "  make docs      Build the Sphinx site (HTML) -> $(SITE_BUILD)"
	@echo "  make examples  Build the React examples app -> $(FRONT_BUILD)"
	@echo "  make site      Build docs + examples and stitch into $(SITE_BUILD)"
	@echo "  make dev       Live-reload dev: sphinx-autobuild + react dev server"
	@echo "  make check     Run docgen + tsc --noEmit on the frontend"
	@echo "  make clean     Remove all build artifacts"

extract:
	@$(PYTHON) tools/docgen/docgen.py

docs: extract
	@$(MAKE) -C $(SITE) html

examples: extract
	@$(NPM) --prefix $(FRONTEND) run build

site: docs examples
	@rm -rf $(EXAMPLES_OUT)
	@mkdir -p $(EXAMPLES_OUT)
	@cp -R $(FRONT_BUILD)/. $(EXAMPLES_OUT)/
	@echo "site: stitched examples into $(EXAMPLES_OUT)"

# Run docgen once, then sphinx-autobuild and the React dev server in parallel.
# Edits to docs/examples/*.md currently require re-running `make extract`
# (docgen --watch is not implemented yet).
dev: extract
	@trap 'kill 0' INT TERM EXIT; \
	$(UVRUN) --with sphinx-autobuild sphinx-autobuild \
		-c $(SITE) docs/examples $(SITE_BUILD) --port 8000 & \
	$(NPM) --prefix $(FRONTEND) start & \
	wait

check: extract
	@$(FRONTEND)/node_modules/.bin/tsc -p $(FRONTEND) --noEmit

clean:
	@$(MAKE) -C $(SITE) clean
	@rm -rf $(FRONT_BUILD)
