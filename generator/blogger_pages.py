#!/usr/bin/env python3
"""Publish the static pages in content/pages/ to Blogger as Pages.

AdSense's "low value content" review looks hard at site completeness:
a live About, Contact, Privacy Policy, and Terms page is table stakes.
These have existed in the repo since the start but were never pushed to
Blogger — this script creates them (or updates them in place on re-run,
matched by title) via the Blogger Pages API.

The pages link to each other with root-relative Markdown links such as
``[contact page](/contact/)``. Those paths were written for the old static
site; Blogger serves pages at ``/p/<slug>.html`` and 404s on ``/contact/``.
So publishing runs in two phases: first make sure every page exists and
collect the URL Blogger actually assigned it, then upload each body with
its cross-links rewritten to those real URLs. Guessing ``/p/<slug>.html``
would usually work, but Blogger derives the slug from the title and adds
suffixes on collision, so the URL the API reports is the only safe source.

Requires the same env vars as blogger_publish.py:
    GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN

Usage:
    python generator/blogger_pages.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from blogger_publish import API_BASE, get_access_token, get_blog_id, load_yaml  # noqa: E402
from build_site import parse_frontmatter, md_to_html  # noqa: E402

SITE_CONFIG = ROOT / "config" / "site.yml"
PAGES_DIR = ROOT / "content" / "pages"

# Publish order = a sensible nav order if the user adds the Pages gadget.
PAGE_FILES = ["about.md", "contact.md", "privacy-policy.md", "terms.md"]

# Markdown link whose target is a root-relative path: ](/contact/) or ](/contact)
_ROOT_LINK = re.compile(r"\]\(/([a-z0-9-]+)/?\)")


def rewrite_page_links(markdown: str, slug_to_url: dict[str, str]) -> tuple[str, list[str]]:
    """Point root-relative links at the URLs Blogger assigned those pages.

    Returns the rewritten Markdown and the slugs it could not resolve, so a
    link to a page that is not in PAGE_FILES surfaces as a warning instead
    of quietly shipping as a 404.
    """
    unresolved: list[str] = []

    def swap(m: re.Match) -> str:
        slug = m.group(1)
        url = slug_to_url.get(slug)
        if not url:
            unresolved.append(slug)
            return m.group(0)
        return f"]({url})"

    return _ROOT_LINK.sub(swap, markdown), unresolved


def existing_pages(access_token: str, blog_id: str) -> dict[str, dict]:
    """title -> {"id", "url"} for pages already on the blog."""
    resp = requests.get(
        f"{API_BASE}/blogs/{blog_id}/pages",
        params={"fetchBodies": "false", "maxResults": 50},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return {p["title"]: {"id": p["id"], "url": p.get("url", "")}
            for p in resp.json().get("items", [])}


def load_pages() -> list[dict]:
    pages = []
    for name in PAGE_FILES:
        path = PAGES_DIR / name
        if not path.exists():
            print(f"WARN: {path} missing; skipping")
            continue
        fm, body = parse_frontmatter(path)
        pages.append({"title": fm["title"], "slug": fm.get("slug") or path.stem, "body": body})
    return pages


def main() -> int:
    cfg = load_yaml(SITE_CONFIG)
    access_token = get_access_token()
    blog_url = cfg["blogger"]["blog_url"].strip()
    blog_id = (cfg["blogger"].get("blog_id") or "").strip() or get_blog_id(access_token, blog_url)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    pages_api = f"{API_BASE}/blogs/{blog_id}/pages"

    pages = load_pages()
    current = existing_pages(access_token, blog_id)

    # Phase 1: every page must exist before any body is finalized, because
    # the bodies link to each other and we need Blogger's URL for each.
    for page in pages:
        if page["title"] in current:
            continue
        resp = requests.post(
            pages_api,
            json={"title": page["title"], "content": md_to_html(page["body"]),
                  "kind": "blogger#page"},
            headers=headers, timeout=30,
        )
        resp.raise_for_status()
        created = resp.json()
        current[page["title"]] = {"id": created["id"], "url": created.get("url", "")}
        print(f"created: {page['title']} -> {created.get('url', '')}")

    slug_to_url = {p["slug"]: current[p["title"]]["url"] for p in pages
                   if current.get(p["title"], {}).get("url")}

    # Phase 2: upload the final body for every page, cross-links resolved.
    for page in pages:
        markdown, unresolved = rewrite_page_links(page["body"], slug_to_url)
        for slug in unresolved:
            print(f"WARN: {page['slug']}: link to /{slug}/ has no matching page; left as-is")
        page_id = current[page["title"]]["id"]
        resp = requests.put(
            f"{pages_api}/{page_id}",
            json={"id": page_id, "title": page["title"], "content": md_to_html(markdown),
                  "kind": "blogger#page"},
            headers=headers, timeout=30,
        )
        resp.raise_for_status()
        print(f"updated: {page['title']} -> {resp.json().get('url', '')}")

    print("\nDone. One manual step remains (2 min): Blogger -> Layout -> add the")
    print("'Pages' gadget (top nav or sidebar) and check the four pages, so")
    print("visitors and the AdSense reviewer can actually reach them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
