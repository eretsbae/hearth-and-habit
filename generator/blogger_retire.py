"""Trash Blogger posts that config/topics.yml marks as retired.

State lives in topics.yml, not on the command line, so the repo is the record
of what was taken down and why:

    - title: ...
      status: retired            # was "published"
      published_slug: old-slug
      retired_url: https://www.hearth-habit.com/2026/08/old-post.html
      redirect_to: kept-slug     # the surviving post readers should land on
      blogger_post_id: '123'
      # retired_at: 2026-09-11   <- written by this script once the API call succeeds

For every such topic that still lacks ``retired_at``, the post is moved to the
Blogger trash (``useTrash=true`` — recoverable from the Blogger UI for 90 days,
not a hard delete). Then the related-posts block on the other live posts in
the same pillars is regenerated so nothing keeps linking to the trashed URL.

Blogger's API has no endpoint for custom redirects, so the 301 from the old
path to ``redirect_to`` must be added by hand: Blogger → Settings → Errors and
redirects → Custom redirects. The script prints the exact from/to pairs.
"""

from __future__ import annotations

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


def main() -> int:
    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillar_by_slug = {p["slug"]: p for p in topics_data["pillars"]}
    by_slug = {t.get("published_slug"): t for t in topics_data["topics"] if t.get("published_slug")}

    pending = [
        t for t in topics_data["topics"]
        if t.get("status") == "retired" and t.get("blogger_post_id") and not t.get("retired_at")
    ]
    already = [t for t in topics_data["topics"] if t.get("status") == "retired" and t.get("retired_at")]
    if not pending:
        print(f"Nothing to retire ({len(already)} already retired).")
        return 0

    blog_url = (cfg.get("blogger") or {}).get("blog_url", "").strip()
    access_token = get_access_token()
    blog_id = (cfg["blogger"].get("blog_id") or "").strip() or get_blog_id(access_token, blog_url)
    headers = {"Authorization": f"Bearer {access_token}"}

    touched: set[str] = set()
    redirects: list[tuple[str, str]] = []
    for topic in pending:
        post_id = topic["blogger_post_id"]
        resp = requests.delete(
            f"{API_BASE}/blogs/{blog_id}/posts/{post_id}",
            params={"useTrash": "true"},
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 404:
            print(f"already gone on Blogger: {topic['title']}")
        elif not resp.ok:
            print(f"ERROR trashing '{topic['title']}' ({resp.status_code}): {resp.text[:200]}")
            # Leave retired_at unset so the next run retries this one; the
            # ones already trashed above keep their record via the save below.
            continue
        else:
            print(f"trashed: {topic['title']}")
        topic["retired_at"] = date.today().isoformat()
        touched.add(topic.get("pillar", ""))
        target = by_slug.get(topic.get("redirect_to") or "")
        if topic.get("retired_url") and target and target.get("blogger_url"):
            redirects.append((urlparse(topic["retired_url"]).path, urlparse(target["blogger_url"]).path))
        # Save after each post so a failure mid-loop never re-trashes or
        # forgets one that already went through.
        save_yaml(TOPICS_CONFIG, topics_data)

    if touched:
        # Retired topics have no blogger_url, so related_posts_html already
        # excludes them; this pass rewrites the surviving posts' blocks.
        try:
            refresh_related_on_published(
                access_token, blog_id, blog_url, topics_data, pillar_by_slug, touched, set()
            )
        except requests.exceptions.RequestException as e:
            print(f"WARN: related-links refresh failed, run 'blogger_publish.py --relink-all' later ({e})")
        save_yaml(TOPICS_CONFIG, topics_data)

    if redirects:
        print("\nAdd these in Blogger -> Settings -> Errors and redirects -> Custom redirects (Permanent = ON):")
        for src, dst in redirects:
            print(f"  {src}  ->  {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
