.PHONY: new preview build preview-deploy analytics help

## Create a new post (page bundle): make new name=my-post-title
new:
	@if [ -z "$(name)" ]; then \
		read -p "Post name (kebab-case, e.g. my-first-post): " name; \
		mkdir -p content/posts/$$name && \
		hugo new posts/$$name/index.md; \
	else \
		mkdir -p content/posts/$(name) && \
		hugo new posts/$(name)/index.md; \
	fi

## Start local dev server with drafts
preview:
	hugo server -D --navigateToChanged

## Production build
build:
	hugo --minify --gc

## Deploy a named preview channel to Firebase (manual staging)
preview-deploy:
	hugo --minify --gc && firebase hosting:channel:deploy preview-$(shell date +%Y%m%d) --expires 7d

## Run analytics report: make analytics [PERIOD=30d] [SOURCE=both] [POST=/posts/foo/] [FORMAT=table] [CSV=1]
analytics:
	PYTHONPATH=. .venv/bin/python analytics/report.py \
		--source $(or $(SOURCE),both) \
		--period $(or $(PERIOD),30d) \
		--format $(or $(FORMAT),table) \
		$(if $(POST),--post $(POST)) \
		$(if $(CSV),--csv) \
		$(if $(LIMIT),--limit $(LIMIT))

## Show available commands
help:
	@grep -E '^##' Makefile | sed 's/## //'
