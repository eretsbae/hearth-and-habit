#!/usr/bin/env python3
"""Publish the static pages in content/pages/ to Blogger as Pages.

AdSense's "low value content" review looks hard at site completeness:
a live About, Contact, Privacy Policy, and Terms page is table stakes.
These have existed in the repo since the start but were never pushed to
Blogger — this script creates them (or updates them in place on re-run,
matched by title) via the Blogger Pages API.

Requires the same env vars as blogger_publish.py:
    GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN

Usage:
    python generator/blogger_pages.py
"""

from __future__ import annotations

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


def existing_pages(access_token: str, blog_id: str) -> dict[str, str]:
    """title -> pageId for pages already on the blog."""
    resp = requests.get(
        f"{API_BASE}/blogs/{blog_id}/pages",
        params={"fetchBodies": "false", "maxResults": 50},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return {p["title"]: p["id"] for p in resp.json().get("items", [])}


def main() -> int:
    cfg = load_yaml(SITE_CONFIG)
    access_token = get_access_token()
    blog_url = cfg["blogger"]["blog_url"].strip()
    blog_id = (cfg["blogger"].get("blog_id") or "").strip() or get_blog_id(access_token, blog_url)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    current = existing_pages(access_token, blog_id)

    for name in PAGE_FILES:
        path = PAGES_DIR / name
        if not path.exists():
            print(f"WARN: {path} missing; skipping")
            continue
        fm, body = parse_frontmatter(path)
        payload = {"title": fm["title"], "content": md_to_html(body)}

        page_id = current.get(fm["title"])
        if page_id:
            resp = requests.put(
                f"{API_BASE}/blogs/{blog_id}/pages/{page_id}",
                json={**payload, "id": page_id, "kind": "blogger#page"},
                headers=headers, timeout=30,
            )
            action = "updated"
        else:
            resp = requests.post(
                f"{API_BASE}/blogs/{blog_id}/pages",
                json={**payload, "kind": "blogger#page"},
                headers=headers, timeout=30,
            )
            action = "created"
        resp.raise_for_status()
        print(f"{action}: {fm['title']} -> {resp.json().get('url', '')}")

    print("\nDone. One manual step remains (2 min): Blogger -> Layout -> add the")
    print("'Pages' gadget (top nav or sidebar) and check the four pages, so")
    print("visitors and the AdSense reviewer can actually reach them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
