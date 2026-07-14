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
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

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
    if not resp.ok:
        raise SystemExit(
            f"ERROR: Google token exchange failed ({resp.status_code}): {resp.text.strip()}\n"
            "If the error above says 'invalid_grant', the GOOGLE_REFRESH_TOKEN secret has\n"
            "expired or been revoked. Re-run generator/blogger_auth.py locally to mint a new\n"
            "refresh token and update the repository secret. See blogger/SETUP.md section B-5\n"
            "(publish the OAuth consent screen so tokens stop expiring after 7 days)."
        )
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


def hero_image_tag(cfg: dict, hero_image: str, alt: str = "") -> str:
    if not hero_image:
        return ""
    url = raw_asset_url(cfg, "content" + hero_image)
    alt_esc = (alt or "").replace('"', "&quot;")
    return (
        f'<img src="{url}" alt="{alt_esc}" '
        f'style="width:100%;max-width:900px;border-radius:14px;'
        f'margin:0 0 24px;display:block;" /><br/>\n'
    )


# ── Structured data (JSON-LD) ────────────────────────────────────────────────
# FAQPage + Article schema make posts eligible for rich results in Google
# Search (expandable Q&A, article thumbnails) — same ranking, higher CTR.

FAQ_HEADING_RE = re.compile(r"^##\s+.*\b(faq|frequently asked|common questions)\b", re.I)


def parse_faq(md_body: str) -> list[tuple[str, str]]:
    """Extract (question, answer) pairs from a '## FAQ'-style section where
    each question is an H3. Answers are the plain text until the next heading."""
    lines = md_body.splitlines()
    pairs: list[tuple[str, str]] = []
    in_faq = False
    question: str | None = None
    answer: list[str] = []

    def flush():
        nonlocal question, answer
        if question and answer:
            text = " ".join(l.strip() for l in answer if l.strip())
            text = re.sub(r"[*_`]|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", text)
            if text:
                pairs.append((question, text.strip()))
        question, answer = None, []

    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            flush()
            in_faq = bool(FAQ_HEADING_RE.match(line))
            continue
        if not in_faq:
            continue
        if line.startswith("### "):
            flush()
            question = line[4:].strip().rstrip("?") + "?"
        elif question is not None:
            answer.append(line)
    flush()
    return pairs


def json_ld_block(cfg: dict, fm: dict, hero_url: str, page_url: str, faq_pairs: list) -> str:
    graph: list[dict] = [
        {
            "@type": "Article",
            "headline": fm.get("title", ""),
            "description": fm.get("description", ""),
            "datePublished": str(fm.get("date", "")),
            "image": [hero_url] if hero_url else [],
            "author": {"@type": "Organization", "name": cfg.get("site_name", "Hearth & Habit")},
            "publisher": {"@type": "Organization", "name": cfg.get("site_name", "Hearth & Habit")},
            **({"mainEntityOfPage": page_url} if page_url else {}),
        }
    ]
    if len(faq_pairs) >= 2:
        graph.append(
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a},
                    }
                    for q, a in faq_pairs
                ],
            }
        )
    data = {"@context": "https://schema.org", "@graph": graph}
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False)
        + "</script>\n"
    )


def pillar_label_url(blog_url: str, pillar_name: str) -> str:
    return f"{blog_url.rstrip('/')}/search/label/{quote(pillar_name)}"


# Sentinels around the related-posts block so later runs can find and replace
# it in already-published posts (bidirectional linking: old posts learn about
# new ones instead of only new -> old).
RELATED_START = "<!-- hh:related -->"
RELATED_END = "<!-- /hh:related -->"
# The first publish batch (before sentinels existed) appended the block bare;
# it was always the last thing in the post, so replace from this marker on.
LEGACY_RELATED_MARKER = '<hr style="margin:40px 0 24px;border:none;border-top:1px solid #e4c7b2;" />'


def related_posts_html(
    topics_data: dict, pillar: dict, current_slug: str | None, blog_url: str, limit: int = 3
) -> str:
    """Internal links to other published posts in the same pillar, plus a
    link to the pillar's Blogger label archive. More pages/session and
    stronger topical-authority signal than a standalone post with no
    outbound links to the rest of the site.
    """
    if not pillar:
        return ""
    pillar_slug = pillar.get("slug")
    siblings = [
        t
        for t in topics_data.get("topics", [])
        if t.get("pillar") == pillar_slug
        and t.get("blogger_url")
        and t.get("published_slug") != current_slug
    ]
    items = "".join(
        f'<li style="margin:0 0 6px;"><a href="{t["blogger_url"]}">{t["title"]}</a></li>'
        for t in siblings[:limit]
    )
    hub_link = ""
    if blog_url:
        hub_url = pillar_label_url(blog_url, pillar.get("name", ""))
        hub_link = (
            f'<p style="margin:0 0 24px;"><a href="{hub_url}">'
            f'Browse all {pillar.get("name", "")} posts &rarr;</a></p>'
        )
    if not items and not hub_link:
        return ""
    section = '<hr style="margin:40px 0 24px;border:none;border-top:1px solid #e4c7b2;" />\n'
    if items:
        section += (
            f'<div style="margin:0 0 8px;font-weight:600;color:#2e2a24;">Keep reading</div>\n'
            f'<ul style="margin:0 0 16px;padding-left:20px;">{items}</ul>\n'
        )
    section += hub_link
    return f"{RELATED_START}\n{section}{RELATED_END}"


def replace_related_block(content: str, new_block: str) -> str:
    """Swap the related-posts block inside existing post HTML (sentinel-aware,
    with a fallback for the pre-sentinel format); append if absent."""
    start = content.find(RELATED_START)
    if start != -1:
        end = content.find(RELATED_END)
        tail = content[end + len(RELATED_END):] if end != -1 else ""
        return content[:start] + new_block + tail
    legacy = content.rfind(LEGACY_RELATED_MARKER)
    if legacy != -1:
        return content[:legacy] + new_block
    return content + "\n" + new_block


def blogger_post_path(blogger_url: str) -> str:
    return urlparse(blogger_url).path


def refresh_related_on_published(
    access_token: str, blog_id: str, blog_url: str, topics_data: dict,
    pillar_by_slug: dict, touched_pillars: set[str], skip_slugs: set[str],
) -> None:
    """After new posts go live, rewrite the related-posts block of the other
    live posts in the same pillars so old posts link forward to new ones."""
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    for topic in topics_data.get("topics", []):
        if (
            topic.get("pillar") not in touched_pillars
            or not topic.get("blogger_url")
            or topic.get("published_slug") in skip_slugs
        ):
            continue
        post_id = topic.get("blogger_post_id")
        if not post_id:
            resp = requests.get(
                f"{API_BASE}/blogs/{blog_id}/posts/bypath",
                params={"path": blogger_post_path(topic["blogger_url"])},
                headers=headers,
                timeout=30,
            )
            if not resp.ok:
                print(f"WARN: could not resolve post id for '{topic['title']}'; skipping refresh")
                continue
            post_id = resp.json()["id"]
            topic["blogger_post_id"] = post_id

        resp = requests.get(f"{API_BASE}/blogs/{blog_id}/posts/{post_id}", headers=headers, timeout=30)
        if not resp.ok:
            print(f"WARN: could not fetch post {post_id} for '{topic['title']}'; skipping refresh")
            continue
        content = resp.json().get("content", "")

        pillar = pillar_by_slug.get(topic["pillar"], {})
        block = related_posts_html(topics_data, pillar, topic.get("published_slug"), blog_url)
        if not block:
            continue
        updated = replace_related_block(content, block)
        if updated == content:
            continue
        resp = requests.patch(
            f"{API_BASE}/blogs/{blog_id}/posts/{post_id}",
            json={"content": updated},
            headers=headers,
            timeout=30,
        )
        if resp.ok:
            print(f"  refreshed related links on: {topic['title']}")
        else:
            print(f"WARN: failed to refresh '{topic['title']}' ({resp.status_code}): {resp.text[:200]}")


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
    ap.add_argument(
        "--check-auth",
        action="store_true",
        help="Only verify the Google credentials work (token exchange), then exit. "
        "Run before the Claude generation step so a dead refresh token fails the "
        "workflow before any generation cost is incurred.",
    )
    args = ap.parse_args()

    if args.check_auth:
        get_access_token()
        print("Blogger credentials OK (token exchange succeeded).")
        return 0

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
    touched_pillars: set[str] = set()
    new_slugs: set[str] = set()
    for topic in to_publish:
        slug = topic.get("published_slug")
        path = find_post_file(slug) if slug else None
        if not path:
            print(f"WARN: no post file found for '{topic['title']}' (slug={slug}); skipping")
            continue

        fm, body = parse_frontmatter(path)
        html = rewrite_image_urls(cfg, md_to_html(body))
        pillar = pillar_by_slug.get(fm.get("pillar"), {})
        hero_url = raw_asset_url(cfg, "content" + fm["hero_image"]) if fm.get("hero_image") else ""
        full_html = (
            json_ld_block(cfg, fm, hero_url, "", parse_faq(body))
            + hero_image_tag(cfg, fm.get("hero_image", ""), fm.get("hero_alt", fm.get("title", "")))
            + html
            + related_posts_html(topics_data, pillar, slug, blog_url)
        )

        labels = list(dict.fromkeys([pillar.get("name", "")] + fm.get("tags", [])))[:20]
        labels = [l for l in labels if l]

        print(f"Publishing to Blogger: {fm['title']}")
        result = create_post(access_token, blog_id, fm["title"], full_html, labels, args.draft)
        topic["blogger_url"] = result.get("url", "")
        if result.get("id"):
            topic["blogger_post_id"] = result["id"]
        print(f"  -> {topic['blogger_url']}")
        published_any = True
        touched_pillars.add(fm.get("pillar"))
        new_slugs.add(slug)

    if published_any:
        if not args.draft:
            refresh_related_on_published(
                access_token, blog_id, blog_url, topics_data,
                pillar_by_slug, touched_pillars, new_slugs,
            )
        save_yaml(TOPICS_CONFIG, topics_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
