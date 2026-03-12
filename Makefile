.PHONY: new preview build preview-deploy analytics analytics-sheets social-stats help

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

## Run analytics report: make analytics [PERIOD=30d] [SOURCE=both] [POST=/posts/foo/] [FORMAT=table] [CSV=1] [ALL_PATHS=1]
analytics:
	PYTHONPATH=. .venv/bin/python analytics/report.py \
		--source $(or $(SOURCE),both) \
		--period $(or $(PERIOD),30d) \
		--format $(or $(FORMAT),table) \
		$(if $(POST),--post $(POST)) \
		$(if $(CSV),--csv) \
		$(if $(LIMIT),--limit $(LIMIT)) \
		$(if $(ALL_PATHS),--all-paths)

## Push analytics to Google Sheet: make analytics-sheets [PERIOD=7d]
analytics-sheets:
	PYTHONPATH=. .venv/bin/python analytics/update_sheets.py \
		--period $(or $(PERIOD),7d)

## Launch dedicated Chrome for social analytics scraping
social-stats:
	@echo "Launching dedicated Chrome for social analytics..."
	@/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
		--remote-debugging-port=9222 \
		--user-data-dir=$(HOME)/.chrome-social-analytics &
	@sleep 3
	@curl -s http://127.0.0.1:9222/json/version > /dev/null 2>&1 \
		&& echo "✓ Chrome DevTools active on port 9222" \
		|| echo "✗ Chrome not responding on port 9222"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Verify you're logged into X, LinkedIn, Reddit, Substack"
	@echo "  2. Run /social-analytics-update in Claude Code"

## Show available commands
help:
	@grep -E '^##' Makefile | sed 's/## //'
