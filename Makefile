.PHONY: new preview build preview-deploy help

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

## Show available commands
help:
	@grep -E '^##' Makefile | sed 's/## //'
