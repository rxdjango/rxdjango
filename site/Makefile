SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = ../docs
BUILDDIR      = _build
CONFDIR       = .

.PHONY: help html clean

help:
	@echo "make html   - build HTML site into $(BUILDDIR)/html"
	@echo "make clean  - remove build artifacts"

html:
	@$(SPHINXBUILD) -c $(CONFDIR) $(SOURCEDIR) $(BUILDDIR)/html

clean:
	rm -rf $(BUILDDIR)
