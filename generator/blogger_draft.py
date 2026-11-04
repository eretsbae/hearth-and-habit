"""Take published posts off the live site by reverting them to Blogger drafts.

Pruning for the AdSense "low value content" review: thin or overlapping posts
leave the public site, but nothing is deleted — the post, its URL slug on
Blogger, and the repo files all stay, and ``--restore`` puts one back live.

State lives in config/topics.yml, like blogger_retire.py:

    - title: ...
      status: drafted            # was "published"
      published_slug: some-slug
      drafted_url: https://www.hearth-habit.com/2026/08/some-post.html
      draft_reason: not indexed, 0 impressions / 90 days
      blogger_post_id: '123'
      # drafted_at: 2026-11-05   <- written by this script once the API call succeeds

``blogger_url`` is removed when a topic is marked drafted (moved to
``drafted_url``). Every other script treats ``blogger_url`` as "live", so the
related-posts blocks, hub pages, content sync, Pinterest and reports all skip
drafted posts without further changes.

Usage:
    python generator/blogger_draft.py                 # revert every pending drafted topic
    python generator/blogger_draft.py --restore SLUG  # publish one back and restore its record
    python generator/blogger_draft.py --check         # list live posts whose body links to a drafted URL (no API)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from blogger_publish import (  # noqa: E402
    API_BASE,
    SITE_CONFIG,
    TOPICS_CONFIG,
    get_access_token,
    get_blog_id,
    load_yaml,
    refresh_related_on_published,
    save_yaml,
)

POSTS_DIR = ROOT / "content" / "posts"


def dangling_links(topics_data: dict) -> list[tuple[str, str]]:
    """(live post file, drafted path) pairs where a live post still links to a drafted post."""
    drafted = {urlparse(t["drafted_url"]).path for t in topics_data["topics"]
               if t.get("status") == "drafted" and t.get("drafted_url")}
    live = {t.get("published_slug") for t in topics_data["topics"]
            if t.get("status") == "published" and t.get("blogger_url")}
    out = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        slug = path.stem[11:]
        if slug not in live:
            continue
        text = path.read_text(encoding="utf-8")
        out += [(path.name, p) for p in sorted(drafted) if p in text]
    return out


def connect(cfg: dict) -> tuple[dict, str, str]:
    blog_url = (cfg.get("blogger") or {}).get("blog_url", "").strip()
    token = get_access_token()
    blog_id = (cfg["blogger"].get("blog_id") or "").strip() or get_blog_id(token, blog_url)
    return {"Authorization": f"Bearer {token}"}, token, blog_id


def revert_pending(cfg: dict, topics_data: dict, pillar_by_slug: dict) -> int:
    pending = [t for t in topics_data["topics"]
               if t.get("status") == "drafted" and t.get("blogger_post_id") and not t.get("drafted_at")]
    if not pending:
        print("Nothing to revert to draft.")
        return 0
    headers, token, blog_id = connect(cfg)
    touched: set[str] = set()
    failed = 0
    for topic in pending:
        resp = requests.post(f"{API_BASE}/blogs/{blog_id}/posts/{topic['blogger_post_id']}/revert",
                             headers=headers, timeout=30)
        if not resp.ok:
            failed += 1
            print(f"ERROR reverting '{topic['title']}' ({resp.status_code}): {resp.text[:200]}")
            continue
        print(f"reverted to draft: {topic['title']}")
        topic["drafted_at"] = date.today().isoformat()
        touched.add(topic.get("pillar", ""))
        save_yaml(TOPICS_CONFIG, topics_data)
    if touched:
        try:
            refresh_related_on_published(token, blog_id, cfg["blogger"].get("blog_url", ""),
                                         topics_data, pillar_by_slug, touched, set())
        except requests.exceptions.RequestException as e:
            print(f"WARN: related-links refresh failed, run 'blogger_publish.py --relink-all' later ({e})")
        save_yaml(TOPICS_CONFIG, topics_data)
    for name, path in dangling_links(topics_data):
        print(f"WARN: {name} still links to drafted {path}")
    return 1 if failed else 0


def restore(cfg: dict, topics_data: dict, pillar_by_slug: dict, slug: str) -> int:
    topic = next((t for t in topics_data["topics"]
                  if t.get("published_slug") == slug and t.get("status") == "drafted"), None)
    if not topic or not topic.get("blogger_post_id"):
        print(f"ERROR: no drafted topic with published_slug '{slug}'")
        return 1
    headers, token, blog_id = connect(cfg)
    resp = requests.post(f"{API_BASE}/blogs/{blog_id}/posts/{topic['blogger_post_id']}/publish",
                         headers=headers, timeout=30)
    if not resp.ok:
        print(f"ERROR publishing '{topic['title']}' ({resp.status_code}): {resp.text[:200]}")
        return 1
    topic["status"] = "published"
    topic["blogger_url"] = resp.json().get("url") or topic["drafted_url"]
    for key in ("drafted_url", "drafted_at", "draft_reason"):
        topic.pop(key, None)
    save_yaml(TOPICS_CONFIG, topics_data)
    print(f"restored: {topic['title']} -> {topic['blogger_url']}")
    refresh_related_on_published(token, blog_id, cfg["blogger"].get("blog_url", ""),
                                 topics_data, pillar_by_slug, {topic.get("pillar", "")}, set())
    save_yaml(TOPICS_CONFIG, topics_data)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", metavar="SLUG")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillar_by_slug = {p["slug"]: p for p in topics_data["pillars"]}

    bad = [t.get("published_slug") for t in topics_data["topics"]
           if t.get("status") == "drafted" and (t.get("blogger_url") or not t.get("drafted_url"))]
    if bad:
        print(f"ERROR: drafted topics must have drafted_url and no blogger_url: {bad}")
        return 1
    if args.check:
        links = dangling_links(topics_data)
        for name, path in links:
            print(f"{name} -> {path}")
        print(f"{len(links)} dangling link(s)")
        return 1 if links else 0
    if args.restore:
        return restore(cfg, topics_data, pillar_by_slug, args.restore)
    return revert_pending(cfg, topics_data, pillar_by_slug)


if __name__ == "__main__":
    raise SystemExit(main())
