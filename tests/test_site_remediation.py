#!/usr/bin/env python3
"""Regression test suite for lavinigam.com security, SEO/GEO, and tooling remediation.

Covers all 8 functional & security acceptance criteria:
  1. Firebase Hosting CSP & security headers (`firebase.json`)
  2. GEO AI crawler `robots.txt` consolidation & `static/robots.txt` removal
  3. `/talks/` dead YouTube card removal & healthy card preservation
  4. Fragment-safe, host-validated UTM link tagging across Markdown & shortcodes
  5. Single-encoded social share links in `comments.html`
  6. Valid, single-encoded `TechArticle`/`Article`, `BreadcrumbList`, & `FAQPage` JSON-LD
  7. `/about/` frontmatter & single-H1 cleanup
  8. Analytics CLI (`update_sheets.py`, `config.example.py`, `SKILL.md`) & `Makefile` parity

Run via:
    make test
"""

from __future__ import annotations

import html
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

REPO_ROOT = Path(__file__).resolve().parent.parent
UTM_HOSTS = ("agentskills.io", "cloud.google.com")
UTM_HOST_PATHS = (
    "google.github.io/adk",
    "github.com/google/adk",
    "github.com/lavinigam-gcp/build-with-adk",
)


def _find_hugo_bin() -> str:
    """Locate the Hugo extended binary."""
    env_bin = os.environ.get("HUGO_BIN")
    if env_bin and Path(env_bin).is_file():
        return env_bin
    which_bin = shutil.which("hugo")
    if which_bin:
        return which_bin
    local_bin = Path.home() / ".local" / "bin" / "hugo"
    if local_bin.is_file():
        return str(local_bin)
    raise RuntimeError("Hugo binary not found on PATH, HUGO_BIN, or ~/.local/bin/hugo")


def _parse_csp(csp_value: str) -> dict[str, list[str]]:
    """Parse a CSP header string into {directive: [sources...]}."""
    directives: dict[str, list[str]] = {}
    for raw_part in csp_value.split(";"):
        part = raw_part.strip()
        if not part:
            continue
        tokens = part.split()
        directives[tokens[0]] = tokens[1:]
    return directives


def _is_utm_target(url: str) -> bool:
    """Return True if url matches one of the configured outbound UTM target domains."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    host_path = f"{host}{parsed.path}"
    if any(host == h or host.endswith(f".{h}") for h in UTM_HOSTS):
        return True
    return any(host_path.startswith(hp) for hp in UTM_HOST_PATHS)


def _assert_no_double_encoded_strings(
    test: unittest.TestCase, obj: object, ctx: str
) -> None:
    """Recursively verify no JSON-LD string was double-JSON-encoded with outer quotes."""
    if isinstance(obj, str):
        test.assertFalse(
            len(obj) >= 2 and obj.startswith('"') and obj.endswith('"'),
            f"Double-JSON-encoded string in {ctx}: {obj!r}",
        )
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_no_double_encoded_strings(test, v, f"{ctx}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_double_encoded_strings(test, v, f"{ctx}[{i}]")


class SiteRemediationTest(unittest.TestCase):
    """End-to-end build and static/behavioral regression checks."""

    tmpdir: tempfile.TemporaryDirectory[str] | None
    public_dir: Path
    hugo_bin: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.hugo_bin = _find_hugo_bin()
        prebuilt = os.environ.get("HUGO_PUBLIC_DIR")
        if prebuilt:
            cls.tmpdir = None
            cls.public_dir = Path(prebuilt).resolve()
            if not cls.public_dir.is_dir():
                raise RuntimeError(f"HUGO_PUBLIC_DIR does not exist: {cls.public_dir}")
            return

        cls.tmpdir = tempfile.TemporaryDirectory(prefix="lavinigam_site_test_")
        tmp_path = Path(cls.tmpdir.name)
        cls.public_dir = tmp_path / "public"
        cache_dir = tmp_path / "hugo_cache"
        resource_dir = tmp_path / "hugo_resources"

        env = {
            **os.environ,
            "HUGO_CACHEDIR": str(cache_dir),
            "HUGO_RESOURCEDIR": str(resource_dir),
            "HUGO_ENVIRONMENT": "production",
            "TZ": "America/Los_Angeles",
        }
        proc = subprocess.run(
            [
                cls.hugo_bin,
                "--gc",
                "--minify",
                "--noBuildLock",
                "--baseURL",
                "https://lavinigam.com",
                "--destination",
                str(cls.public_dir),
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"Hugo production build failed (exit {proc.returncode}):\n"
                f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        if "WARN" in proc.stdout or "WARN" in proc.stderr:
            raise AssertionError(
                f"Hugo build emitted unexpected warnings:\n{proc.stdout}\n{proc.stderr}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.tmpdir is not None:
            cls.tmpdir.cleanup()

    # ------------------------------------------------------------------
    # 1. CSP & Security Headers (`firebase.json`)
    # ------------------------------------------------------------------
    def test_firebase_csp_and_security_headers(self) -> None:
        fb_config = json.loads((REPO_ROOT / "firebase.json").read_text(encoding="utf-8"))
        hosting = fb_config["hosting"]
        self.assertEqual(hosting.get("site"), "kaggle-on-gcp")

        global_headers: dict[str, str] = {}
        for block in hosting.get("headers", []):
            if block.get("source") == "**":
                for item in block.get("headers", []):
                    global_headers[item["key"]] = item["value"]

        self.assertEqual(global_headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(global_headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("max-age=31536000", global_headers.get("Strict-Transport-Security", ""))
        self.assertEqual(
            global_headers.get("Referrer-Policy"), "strict-origin-when-cross-origin"
        )
        for perm in ("geolocation=()", "microphone=()", "camera=()", "payment=()"):
            self.assertIn(perm, global_headers.get("Permissions-Policy", ""))

        csp = _parse_csp(global_headers["Content-Security-Policy"])
        self.assertEqual(csp.get("default-src"), ["'self'"])
        self.assertEqual(csp.get("base-uri"), ["'self'"])
        self.assertEqual(csp.get("object-src"), ["'none'"])
        self.assertEqual(csp.get("frame-ancestors"), ["'none'"])

        # Giscus comments requires script-src, style-src, and frame-src
        self.assertIn("https://giscus.app", csp.get("script-src", []))
        self.assertIn("https://giscus.app", csp.get("style-src", []))
        self.assertIn("https://giscus.app", csp.get("frame-src", []))

        # Regional GA4 collection endpoints
        connect_src = csp.get("connect-src", [])
        for endpoint in (
            "'self'",
            "https://www.google-analytics.com",
            "https://*.google-analytics.com",
            "https://analytics.google.com",
            "https://*.analytics.google.com",
            "https://www.googletagmanager.com",
        ):
            self.assertIn(endpoint, connect_src)

        # Ensure unsafe-eval is never permitted
        for directive, values in csp.items():
            self.assertNotIn("'unsafe-eval'", values, f"Unexpected unsafe-eval in {directive}")

    # ------------------------------------------------------------------
    # 2. GEO `robots.txt` consolidation
    # ------------------------------------------------------------------
    def test_robots_txt_geo_crawlers_and_no_static_shadow(self) -> None:
        self.assertFalse(
            (REPO_ROOT / "static" / "robots.txt").exists(),
            "static/robots.txt must be deleted so layouts/robots.txt is authoritative",
        )
        robots = (self.public_dir / "robots.txt").read_text(encoding="utf-8")
        for agent in (
            "*",
            "GPTBot",
            "PerplexityBot",
            "anthropic-ai",
            "Googlebot-Extended",
            "cohere-ai",
        ):
            self.assertRegex(
                robots,
                rf"User-agent:\s*{re.escape(agent)}\s+Allow:\s*/",
                f"Missing Allow: / block for {agent} in robots.txt",
            )
        self.assertIn("Sitemap: https://lavinigam.com/sitemap.xml", robots)

    # ------------------------------------------------------------------
    # 3. `/talks/` dead YouTube removal & healthy card preservation
    # ------------------------------------------------------------------
    def test_talks_page_removes_dead_videos_and_keeps_healthy_cards(self) -> None:
        talks_src = (REPO_ROOT / "content" / "talks.md").read_text(encoding="utf-8")
        expected_cards = len(re.findall(r'class=["\']talk-card["\']', talks_src))
        self.assertGreaterEqual(expected_cards, 9)

        talks_html = (self.public_dir / "talks" / "index.html").read_text(encoding="utf-8")
        for dead_id in ("8CWXUVjN8hc", "2EvAZB7EpII"):
            self.assertNotIn(dead_id, talks_html, f"Dead YouTube ID {dead_id} still on /talks/")

        cards = re.findall(
            r'<a[^>]*class=["\']?talk-card["\']?[^>]*>', talks_html
        )
        self.assertEqual(len(cards), expected_cards)
        for card_tag in cards:
            self.assertIn("noopener", card_tag)
            self.assertIn("noreferrer", card_tag)

    # ------------------------------------------------------------------
    # 4. Fragment-safe UTM link tagging & URL scheme safety
    # ------------------------------------------------------------------
    def test_utm_tagging_fragment_placement_and_shortcodes(self) -> None:
        utm_hrefs: list[tuple[str, str]] = []
        for html_file in sorted(self.public_dir.rglob("*.html")):
            rel = str(html_file.relative_to(self.public_dir))
            text = html_file.read_text(encoding="utf-8")
            for match in re.finditer(r'href=["\']([^"\']*utm_source=[^"\']*)["\']', text):
                raw_url = html.unescape(match.group(1))
                utm_hrefs.append((rel, raw_url))
                parsed = urllib.parse.urlsplit(raw_url)
                self.assertNotIn(
                    "utm_source=",
                    parsed.fragment,
                    f"UTM parameters placed after #fragment in {rel}: {raw_url}",
                )
                qs = urllib.parse.parse_qs(parsed.query)
                self.assertEqual(qs.get("utm_source"), ["lavinigam-blog"])
                self.assertEqual(qs.get("utm_medium"), ["blog"])
                self.assertTrue(
                    qs.get("utm_campaign") and qs["utm_campaign"][0],
                    f"Missing utm_campaign in {rel}: {raw_url}",
                )

        self.assertGreater(len(utm_hrefs), 20, "Expected UTM-tagged outbound links in posts")

        frag_urls = [u for _, u in utm_hrefs if "#" in u]
        self.assertGreaterEqual(len(frag_urls), 3)
        self.assertTrue(
            any(
                u.startswith("https://google.github.io/adk-docs/skills/?")
                and u.endswith("#inline-skills")
                for u in frag_urls
            ),
            f"Expected fragment-preserved #inline-skills link, got {frag_urls}",
        )

        # Verify button and card-link shortcodes pointing to UTM target hosts receive UTM tags
        part1 = html.unescape(
            (self.public_dir / "posts" / "adk-agent-skills-part1" / "index.html").read_text(
                encoding="utf-8"
            )
        )
        btn_hrefs = [
            u
            for u in re.findall(
                r'<a[^>]*class=["\'][^"\']*btn[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
                part1,
            )
            if _is_utm_target(u)
        ]
        card_hrefs = [
            u
            for u in re.findall(
                r'<a[^>]*class=["\']?card-link["\']?[^>]*href=["\']([^"\']+)["\']',
                part1,
            )
            if _is_utm_target(u)
        ]
        self.assertTrue(btn_hrefs and all("utm_source=lavinigam-blog" in u for u in btn_hrefs))
        self.assertTrue(card_hrefs and all("utm_source=lavinigam-blog" in u for u in card_hrefs))

        # Non-target external links (e.g., arxiv.org in design-patterns card-link) must NOT get UTM
        patterns_page = html.unescape(
            (self.public_dir / "posts" / "adk-skill-design-patterns" / "index.html").read_text(
                encoding="utf-8"
            )
        )
        arxiv_links = re.findall(r'href=["\']?(https://arxiv\.org[^"\'\s>]*)["\']?', patterns_page)
        self.assertTrue(arxiv_links)
        for u in arxiv_links:
            self.assertNotIn("utm_source=", u)

    def test_templates_do_not_bypass_url_or_html_escaping_unnecessarily(self) -> None:
        for rel_path in (
            "layouts/_default/_markup/render-link.html",
            "layouts/shortcodes/button.html",
            "layouts/shortcodes/card-link.html",
        ):
            src = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotIn(
                "safeURL",
                src,
                f"{rel_path} should rely on Go html/template contextual URL filtering instead of safeURL",
            )
        card_src = (REPO_ROOT / "layouts/shortcodes/card-link.html").read_text(encoding="utf-8")
        self.assertNotIn(
            "safeHTML",
            card_src,
            "card-link.html should use htmlUnescape rather than safeHTML for icon entities",
        )

    def test_utm_template_blocks_query_or_subdomain_spoofing_in_isolated_fixture(self) -> None:
        """Build a temporary synthetic fixture post to test adversarial URLs and shortcode edge cases."""
        with tempfile.TemporaryDirectory(prefix="hugo_edge_fixture_") as tmp:
            tmp_root = Path(tmp)
            content_dir = tmp_root / "content"
            (content_dir / "posts" / "edge-post").mkdir(parents=True)
            (content_dir / "posts" / "edge-post" / "index.md").write_text(
                r"""---
title: 'Edge "Quote" & <Tag> Test'
date: 2026-03-15T10:00:00Z
techArticle: true
tags: ["security", "quotes\"test"]
faq:
  - question: '"Quoted" question: Can </script><script>alert(1)</script> break JSON-LD?'
    answer: 'No, Go contextual escaping encodes < and > safely.'
---

- [Spoof Query](https://x.com/intent/tweet?url=https://cloud.google.com/docs)
- [Spoof Host](https://evil-agentskills.io/spec)
- [Valid Subdomain](https://console.cloud.google.com/vertex-ai#models)
- [Uppercase Scheme](HTTPS://agentskills.io/spec#upper)
- [Same Site Absolute](https://lavinigam.com/about/)
- [Existing Query + Frag](https://cloud.google.com/vertex-ai?hl=en#pricing)
- [Multi Hash](https://agentskills.io/spec#sec#sub)
- [Already Tagged](https://agentskills.io/spec?utm_source=custom#top)
- [JS Scheme Md](javascript:alert(1))

{{< button href="javascript:alert(1)" text="BadBtn" style=`outline" onclick="alert(1)` >}}
{{< card-link href="https://google.github.io/adk-docs/skills/#card-anchor" title="Card <Title>" description=`Desc & "quote"` icon="&#x1F4E6;" >}}
""",
                encoding="utf-8",
            )
            out_dir = tmp_root / "public"
            env = {
                **os.environ,
                "HUGO_CACHEDIR": str(tmp_root / "cache"),
                "HUGO_RESOURCEDIR": str(tmp_root / "resources"),
                "HUGO_ENVIRONMENT": "production",
            }
            proc = subprocess.run(
                [
                    self.hugo_bin,
                    "--noBuildLock",
                    "--baseURL",
                    "https://lavinigam.com",
                    "--contentDir",
                    str(content_dir),
                    "--destination",
                    str(out_dir),
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"{proc.stdout}\n{proc.stderr}")

            rendered = (out_dir / "posts" / "edge-post" / "index.html").read_text(encoding="utf-8")
            unescaped_hrefs = [
                html.unescape(m.group(1))
                for m in re.finditer(r'href=["\']([^"\']+)["\']', rendered)
            ]

            self.assertIn("https://x.com/intent/tweet?url=https://cloud.google.com/docs", unescaped_hrefs)
            self.assertIn("https://evil-agentskills.io/spec", unescaped_hrefs)
            self.assertIn(
                "https://console.cloud.google.com/vertex-ai?utm_campaign=edge-post&utm_medium=blog&utm_source=lavinigam-blog#models",
                unescaped_hrefs,
            )
            self.assertIn(
                "HTTPS://agentskills.io/spec?utm_campaign=edge-post&utm_medium=blog&utm_source=lavinigam-blog#upper",
                unescaped_hrefs,
            )
            # Same-site absolute URL should NOT open target="_blank"
            self.assertNotRegex(
                rendered,
                r'<a[^>]*href=["\']?https://lavinigam\.com/about/["\']?[^>]*target=',
            )
            self.assertIn(
                "https://cloud.google.com/vertex-ai?hl=en&utm_campaign=edge-post&utm_medium=blog&utm_source=lavinigam-blog#pricing",
                unescaped_hrefs,
            )
            self.assertIn(
                "https://agentskills.io/spec?utm_campaign=edge-post&utm_medium=blog&utm_source=lavinigam-blog#sec#sub",
                unescaped_hrefs,
            )
            self.assertIn("https://agentskills.io/spec?utm_source=custom#top", unescaped_hrefs)
            self.assertNotIn("javascript:alert(1)", rendered)
            self.assertNotIn("onclick=", rendered)
            self.assertIn("btn btn-primary", rendered)
            self.assertIn(
                "https://google.github.io/adk-docs/skills/?utm_campaign=edge-post&utm_medium=blog&utm_source=lavinigam-blog#card-anchor",
                unescaped_hrefs,
            )
            self.assertIn("📦", rendered)
            self.assertIn("Card &lt;Title&gt;", rendered)
            self.assertNotIn("</script><script>alert(1)", rendered)

            ld_blocks = re.findall(
                r'<script type=["\']?application/ld\+json["\']?>(.*?)</script>',
                rendered,
                re.S,
            )
            self.assertGreaterEqual(len(ld_blocks), 3)
            for idx, raw_ld in enumerate(ld_blocks):
                parsed_ld = json.loads(raw_ld)
                _assert_no_double_encoded_strings(self, parsed_ld, f"edge-post#{idx}")
                if parsed_ld.get("@type") == "TechArticle":
                    self.assertEqual(parsed_ld["headline"], 'Edge "Quote" & <Tag> Test')
                    self.assertIsInstance(parsed_ld["keywords"], list)
                    self.assertIn('quotes"test', parsed_ld["keywords"])

    # ------------------------------------------------------------------
    # 5. Single-encoded social share links (`comments.html`)
    # ------------------------------------------------------------------
    def test_social_share_links_are_single_encoded(self) -> None:
        for post_html in sorted((self.public_dir / "posts").glob("*/index.html")):
            text = post_html.read_text(encoding="utf-8")
            self.assertNotIn("%253A", text.upper(), f"Double-encoded colon in {post_html}")
            self.assertNotIn("%252F", text.upper(), f"Double-encoded slash in {post_html}")

            share_hrefs = re.findall(
                r'href=["\'](https://(?:x\.com/intent/tweet|www\.linkedin\.com/sharing/share-offsite/|www\.reddit\.com/submit|news\.ycombinator\.com/submitlink)[^"\']*)["\']',
                text,
            )
            self.assertEqual(len(share_hrefs), 4, f"Expected 4 social share links in {post_html}")
            for raw_href in share_hrefs:
                href = html.unescape(raw_href)
                qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
                url_param = (qs.get("url") or qs.get("u") or [""])[0]
                self.assertTrue(
                    url_param.startswith("https://lavinigam.com/posts/"),
                    f"Decoded share URL parameter malformed ({url_param!r}) in {href}",
                )
                if "linkedin.com" not in href:
                    title_param = (qs.get("text") or qs.get("title") or qs.get("t") or [""])[0]
                    self.assertTrue(
                        title_param
                        and "%3A" not in title_param.upper()
                        and "%2F" not in title_param.upper()
                        and "+" not in title_param,
                        f"Decoded share title parameter malformed ({title_param!r}) in {href}",
                    )

    # ------------------------------------------------------------------
    # 6. Structured Data (`article.html`, `breadcrumb.html`, `faq.html`)
    # ------------------------------------------------------------------
    def test_json_ld_valid_single_encoded_and_scoped_to_dated_posts(self) -> None:
        article_pages: list[str] = []
        iso_date_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")

        for html_file in sorted(self.public_dir.rglob("*.html")):
            rel = str(html_file.relative_to(self.public_dir))
            content = html_file.read_text(encoding="utf-8")
            self.assertNotIn("0001-01-01", content, f"Zero date leaked into {rel}")

            blocks = re.findall(
                r'<script type=["\']?application/ld\+json["\']?>(.*?)</script>',
                content,
                re.S,
            )
            for idx, raw_block in enumerate(blocks):
                data = json.loads(raw_block)
                schema_type = data.get("@type")
                _assert_no_double_encoded_strings(
                    self, data, f"{rel}#{idx}({schema_type})"
                )

                if schema_type in ("Article", "TechArticle"):
                    article_pages.append(rel)
                    self.assertTrue(
                        rel.startswith("posts/") and rel != "posts/index.html",
                        f"Article JSON-LD emitted on non-post page {rel}",
                    )
                    self.assertRegex(data["datePublished"], iso_date_re)
                    self.assertRegex(data["dateModified"], iso_date_re)
                    self.assertTrue(data["url"].startswith("https://lavinigam.com/posts/"))
                    self.assertIsInstance(
                        data.get("keywords"),
                        list,
                        f"Expected keywords JSON array in {rel}, got {type(data.get('keywords'))}",
                    )
                    if "image" in data:
                        img_url = data["image"]
                        self.assertTrue(img_url.startswith("https://lavinigam.com/"))
                        rel_img_path = img_url.removeprefix("https://lavinigam.com/")
                        self.assertTrue(
                            (self.public_dir / rel_img_path).is_file(),
                            f"JSON-LD image URL {img_url} in {rel} does not exist in built public/ dir",
                        )

                elif schema_type == "BreadcrumbList":
                    items = data.get("itemListElement", [])
                    self.assertGreaterEqual(
                        len(items),
                        2,
                        f"BreadcrumbList in {rel} must have >= 2 items per Schema.org",
                    )
                    for pos_idx, item in enumerate(items, start=1):
                        self.assertEqual(item.get("position"), pos_idx)
                        name = item.get("name", "")
                        self.assertTrue(
                            isinstance(name, str) and name.strip(),
                            f"Invalid BreadcrumbList item name in {rel}: {item!r}",
                        )
                        if "item" in item:
                            self.assertNotIn(
                                "lavinigam.com//",
                                item["item"],
                                f"Double-slash URL in BreadcrumbList of {rel}: {item!r}",
                            )

                elif schema_type == "FAQPage":
                    questions = data.get("mainEntity", [])
                    self.assertGreaterEqual(len(questions), 1)

        expected_posts = [
            p
            for p in (REPO_ROOT / "content" / "posts").glob("*/index.md")
            if not re.search(r"^draft:\s*true\b", p.read_text(encoding="utf-8"), re.M)
        ]
        self.assertGreaterEqual(len(expected_posts), 4)
        self.assertEqual(len(article_pages), len(expected_posts))

    # ------------------------------------------------------------------
    # 7. `/about/` frontmatter & single-H1 cleanup
    # ------------------------------------------------------------------
    def test_about_page_single_h1_and_clean_chrome(self) -> None:
        about_md = (REPO_ROOT / "content" / "about.md").read_text(encoding="utf-8")
        self.assertNotIn('layout: "about"', about_md)
        for required_line in ("showToc: false", "comments: false", "hideMeta: true"):
            self.assertIn(required_line, about_md)

        about_html = (self.public_dir / "about" / "index.html").read_text(encoding="utf-8")
        h1_matches = re.findall(r"<h1\b[^>]*>.*?</h1>", about_html, re.S)
        self.assertEqual(len(h1_matches), 1, f"Expected exactly 1 <h1> on /about/, got {h1_matches}")
        self.assertIn("<h2", about_html)
        self.assertNotIn("giscus.app", about_html)
        self.assertNotIn('class="post-meta"', about_html)
        self.assertNotIn("class=post-meta", about_html)
        self.assertNotIn("toc-sidebar", about_html)

    # ------------------------------------------------------------------
    # 8. Analytics CLI & `Makefile` parity
    # ------------------------------------------------------------------
    def test_analytics_cli_help_date_ranges_and_makefile_targets(self) -> None:
        help_proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "analytics" / "update_sheets.py"), "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            help_proc.returncode,
            0,
            f"update_sheets.py --help failed:\n{help_proc.stderr}",
        )
        for expected in ("14d", "21d", "28d", "YYYY-MM-DD:YYYY-MM-DD"):
            self.assertIn(expected, help_proc.stdout)

        spec = importlib.util.spec_from_file_location(
            "config_example", REPO_ROOT / "analytics" / "config.example.py"
        )
        assert spec and spec.loader
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        for preset in ("1d", "3d", "7d", "14d", "21d", "28d", "30d", "90d", "365d"):
            start, end = cfg.resolve_date_range(preset)
            self.assertRegex(start, r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(end, r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(
            cfg.resolve_date_range("2026-03-02:2026-11-20"),
            ("2026-03-02", "2026-11-20"),
        )

        skill_md = (
            REPO_ROOT / ".claude" / "skills" / "analytics-update-stats" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("sprint1-analytics", skill_md)
        self.assertIn("YYYY-MM-DD:YYYY-MM-DD", skill_md)
        self.assertIn("single, clean snapshot", skill_md)

        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("update-data", makefile)
        self.assertIn("google-chrome", makefile)
        self.assertIn("chromium", makefile)
        make_help = subprocess.run(
            ["make", "help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(make_help.returncode, 0, make_help.stderr)
        self.assertIn("update-data", make_help.stdout)
        self.assertNotIn("GA4 period:", make_help.stdout)


if __name__ == "__main__":
    unittest.main()
