#!/usr/bin/env python3
"""Publish already-generated posts to Blogger via the Blogger API v3.

Scans config/topics.yml for topics with status "published" that don't yet
have a blogger_url recorded, finds their Markdown file in content/posts/,
converts it to HTML, rewrites local image paths to raw.githubusercontent.com
URLs (the post's images must already be pushed to GitHub — run this AFTER
committing and pushing content/), and creates the post on Blogger.

Requires these environment variables (GitHub Actions secrets):
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    GOOGLE_REFRESH_TOKEN

Usage:
    python generator/blogger_publish.py
    python generator/blogger_publish.py --draft   # create as drafts for review
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from build_site import parse_frontmatter, md_to_html  # noqa: E402

SITE_CONFIG = ROOT / "config" / "site.yml"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"
POSTS_DIR = ROOT / "content" / "posts"

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/blogger/v3"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)


def get_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_blog_id(access_token: str, blog_url: str) -> str:
    resp = requests.get(
        f"{API_BASE}/blogs/byurl",
        params={"url": blog_url},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def raw_asset_url(cfg: dict, relative_path: str) -> str:
    gh = cfg["github"]
    return f"https://raw.githubusercontent.com/{gh['owner']}/{gh['repo']}/{gh['branch']}/{relative_path.lstrip('/')}"


def rewrite_image_urls(cfg: dict, html: str) -> str:
    def repl(m: re.Match) -> str:
        return f'src="{raw_asset_url(cfg, "content" + m.group(1))}"'

    return re.sub(r'src="(/images/[^"]+)"', repl, html)


def hero_image_tag(cfg: dict, hero_image: str) -> str:
    if not hero_image:
        return ""
    url = raw_asset_url(cfg, "content" + hero_image)
    return (
        f'<img src="{url}" alt="" '
        f'style="width:100%;max-width:900px;border-radius:14px;'
        f'margin:0 0 24px;display:block;" /><br/>\n'
    )


def find_post_file(slug: str) -> Path | None:
    matches = list(POSTS_DIR.glob(f"*-{slug}.md"))
    return matches[0] if matches else None


def create_post(access_token: str, blog_id: str, title: str, html: str, labels: list[str], is_draft: bool) -> dict:
    payload = {"kind": "blogger#post", "title": title, "content": html, "labels": labels}
    resp = requests.post(
        f"{API_BASE}/blogs/{blog_id}/posts",
        params={"isDraft": "true" if is_draft else "false"},
        json=payload,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true", help="Create posts as drafts instead of publishing live")
    args = ap.parse_args()

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillar_by_slug = {p["slug"]: p for p in topics_data["pillars"]}

    to_publish = [
        t for t in topics_data["topics"]
        if t.get("status") == "published" and not t.get("blogger_url")
    ]
    if not to_publish:
        print("Nothing pending for Blogger; all published topics are already synced.")
        return 0

    blog_url = (cfg.get("blogger") or {}).get("blog_url", "").strip()
    if not blog_url:
        print("ERROR: config/site.yml -> blogger.blog_url is not set")
        return 1

    access_token = get_access_token()
    blog_id = (cfg["blogger"].get("blog_id") or "").strip() or get_blog_id(access_token, blog_url)

    published_any = False
    for topic in to_publish:
        slug = topic.get("published_slug")
        path = find_post_file(slug) if slug else None
        if not path:
            print(f"WARN: no post file found for '{topic['title']}' (slug={slug}); skipping")
            continue

        fm, body = parse_frontmatter(path)
        html = rewrite_image_urls(cfg, md_to_html(body))
        full_html = hero_image_tag(cfg, fm.get("hero_image", "")) + html

        pillar = pillar_by_slug.get(fm.get("pillar"), {})
        labels = list(dict.fromkeys([pillar.get("name", "")] + fm.get("tags", [])))[:20]
        labels = [l for l in labels if l]

        print(f"Publishing to Blogger: {fm['title']}")
        result = create_post(access_token, blog_id, fm["title"], full_html, labels, args.draft)
        topic["blogger_url"] = result.get("url", "")
        print(f"  -> {topic['blogger_url']}")
        published_any = True

    if published_any:
        save_yaml(TOPICS_CONFIG, topics_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
