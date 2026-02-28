# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Local development server (includes drafts)
hugo server -D

# Production build
hugo --minify

# Create a new blog post
hugo new posts/my-post-name.md

# Create a new page
hugo new page-name.md

# Update the PaperMod theme submodule
git submodule update --remote --merge
```

The dev server runs at `http://localhost:1313`. The CI workflow pins Hugo at version `0.152.2` (extended).

## Architecture

**Hugo + PaperMod** static site deployed to GitHub Pages via `.github/workflows/hugo.yml` on every push to `main`.

- `hugo.yaml` — all site configuration: `baseURL`, nav menu, PaperMod params, taxonomies, privacy, markup
- `content/` — Markdown content; posts go in `content/posts/`, standalone pages at the root
- `themes/PaperMod/` — git submodule (do not edit files here)
- `layouts/` — theme overrides; any file here shadows the equivalent in `themes/PaperMod/layouts/`
- `static/` — copied verbatim to the build output root (e.g. `CNAME` for custom domain)
- `archetypes/default.md` — front matter template for `hugo new`

**Theme customization pattern**: Override theme templates by mirroring their path under `layouts/`. Currently `layouts/partials/extend_head.html` injects Cloudflare Web Analytics without touching the submodule.

**Deployment**: GitHub Actions builds with `--gc --minify` and deploys `./public` as a GitHub Pages artifact. The `baseURL` is set dynamically from the Pages environment during CI builds.

## Git Workflow

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
