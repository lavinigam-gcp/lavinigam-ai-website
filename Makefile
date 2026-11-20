.PHONY: new preview build test preview-deploy analytics analytics-sheets social-stats update-data help

PYTHON ?= .venv/bin/python
SPRINT_START ?= 2026-03-02

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
	hugo --gc --minify --baseURL "https://lavinigam.com"

## Run hermetic build, security, and SEO/GEO regression tests
test:
	python3 -m unittest discover -s tests -v

## Deploy a named preview channel to Firebase (manual staging)
preview-deploy:
	$(MAKE) build && firebase hosting:channel:deploy preview-$(shell date +%Y%m%d) --expires 7d

## Run analytics report: make analytics [PERIOD=30d] [SOURCE=both] [POST=/posts/foo/] [FORMAT=table] [CSV=1] [ALL_PATHS=1]
analytics:
	PYTHONPATH=. $(PYTHON) -m analytics.report \
		--source $(or $(SOURCE),both) \
		--period $(or $(PERIOD),30d) \
		--format $(or $(FORMAT),table) \
		$(if $(POST),--post $(POST)) \
		$(if $(CSV),--csv) \
		$(if $(LIMIT),--limit $(LIMIT)) \
		$(if $(ALL_PATHS),--all-paths)

## Push analytics to Google Sheet: make analytics-sheets [PERIOD=7d]
analytics-sheets:
	PYTHONPATH=. $(PYTHON) -m analytics.update_sheets \
		--period $(or $(PERIOD),7d)

## Launch dedicated Chrome for social analytics scraping (macOS & Linux)
social-stats:
	@echo "Launching dedicated Chrome for social analytics..."
	@CHROME_BIN=""; \
	if [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then \
		CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; \
	elif command -v google-chrome >/dev/null 2>&1; then \
		CHROME_BIN="$$(command -v google-chrome)"; \
	elif command -v google-chrome-stable >/dev/null 2>&1; then \
		CHROME_BIN="$$(command -v google-chrome-stable)"; \
	elif command -v chromium >/dev/null 2>&1; then \
		CHROME_BIN="$$(command -v chromium)"; \
	elif command -v chromium-browser >/dev/null 2>&1; then \
		CHROME_BIN="$$(command -v chromium-browser)"; \
	fi; \
	if [ -z "$$CHROME_BIN" ]; then \
		echo "✗ Chrome/Chromium binary not found"; exit 1; \
	fi; \
	"$$CHROME_BIN" \
		--remote-debugging-port=9222 \
		--user-data-dir="$(HOME)/.chrome-social-analytics" >/dev/null 2>&1 &
	@sleep 3
	@curl -s --noproxy '*' http://127.0.0.1:9222/json/version > /dev/null 2>&1 \
		&& echo "✓ Chrome DevTools active on port 9222" \
		|| { echo "✗ Chrome not responding on port 9222"; exit 1; }
	@echo ""
	@echo "Next steps:"
	@echo "  1. Verify you're logged into X, LinkedIn, Reddit, Substack"
	@echo "  2. Run /social-analytics-update in Claude Code"

## Update all dashboard data (GA4 + Chrome for social scraping): make update-data [SPRINT_START=2026-03-02]
# GA4 period defaults to SPRINT_START through today; run /update-data after this completes
update-data: social-stats
	@PERIOD="$(SPRINT_START):$$(date +%Y-%m-%d)"; \
	echo "Updating GA4 analytics for $$PERIOD..."; \
	$(MAKE) analytics-sheets PERIOD="$$PERIOD"
	@echo ""
	@echo "═══════════════════════════════════════════════"
	@echo "  Step 1: ✓ GA4 analytics pushed to sheet"
	@echo "  Step 2: ✓ Chrome launched for social scraping"
	@echo "  Step 3: Run /update-data in Claude Code now"
	@echo "═══════════════════════════════════════════════"

## Show available commands
help:
	@grep -E '^##' Makefile | sed 's/## //'
