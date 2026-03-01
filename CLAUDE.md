# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Local dev server (includes drafts)
make preview

# Production build
make build

# Create a new blog post (page bundle)
make new name=my-post-name

# Update the PaperMod theme submodule
git submodule update --remote --merge
```

Dev server: `http://localhost:1313`. CI pins Hugo `0.152.2` (extended).

## Architecture

**Hugo + PaperMod** static site deployed to **Firebase Hosting** (GCP project: `kaggle-on-gcp`) via `.github/workflows/hugo.yml` on every push to `main`. Custom domain: `lavinigam.com`.

- `hugo.yaml` — all site configuration: `baseURL`, nav menu, PaperMod params, taxonomies, privacy, markup
- `content/` — Markdown content; standalone pages at root, posts as page bundles (see below)
- `themes/PaperMod/` — git submodule (do not edit files here)
- `layouts/` — theme overrides; any file here shadows the equivalent in `themes/PaperMod/layouts/`
- `layouts/partials/structured-data/` — JSON-LD Schema.org partials (Article, Person, WebSite)
- `static/` — copied verbatim to the build output root (`llms.txt`, `robots.txt`)
- `archetypes/default.md` — front matter template for `hugo new`
- `firebase.json` — Firebase Hosting config (security headers, clean URLs, caching)
- `.firebaserc` — links repo to GCP project
- `Makefile` — convenience commands (`make new`, `make preview`, `make build`)

**Theme customization pattern**: Override theme templates by mirroring their path under `layouts/`. `layouts/partials/extend_head.html` injects JSON-LD structured data partials.

**Deployment**: GitHub Actions builds with `--gc --minify`, authenticates via Workload Identity Federation (keyless), and deploys to Firebase Hosting using `firebase deploy`. The `baseURL` is hardcoded to `https://lavinigam.com`.

## Content Structure

Posts are **page bundles** — a folder with `index.md` + its images:

```
content/posts/my-post-name/
  index.md        ← markdown content (MUST be index.md)
  cover.webp      ← cover/OG image
  diagram.png     ← inline images
```

Images are referenced by filename only: `![alt](diagram.png)`. Cover image in front matter: `cover.image: "cover.webp"`.

## Git Workflow

- `main` is branch-protected — all changes go through a PR with passing build check.
- **Never** add `Co-Authored-By: Claude ...` trailers to commit messages.
- Commit messages should be clean and authored solely under the user's identity.

## Content Front Matter

Posts support these PaperMod-specific fields beyond Hugo defaults:
```yaml
showToc: true
TocOpen: false
description: "..."
tags: ["tag1"]
categories: ["cat1"]
series: ["series1"]
```
