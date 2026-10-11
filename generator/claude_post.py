#!/usr/bin/env python3
"""Bookkeeping for posts written by a Claude Code session (no API credits).

Since 2026-10-11 the scheduled post is researched and written by a headless
Claude Code session (scripts/claude-publish.ps1 -> generator/CLAUDE_RUN.md)
on the owner's plan, not by generate_post.py on API credits. The session does
the research and writing with its own tools; this script does the parts that
must be exact: picking the topic the same way generate_post.py does, keeping
topics.yml consistent, running the deterministic checks, and committing only
the post's own files.

Usage:
    python generator/claude_post.py next
    python generator/claude_post.py park --title "..." --reason "..."
    python generator/claude_post.py add-topics new_topics.json
    python generator/claude_post.py finalize --title "..." --slug my-slug [--no-push]

GitHub Actions (generate-and-publish.yml) publishes the committed post to
Blogger at its scheduled time.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import check_post
import generate_post as gp
from build_site import parse_frontmatter

IMG_RE = re.compile(r"!\[[^\]]*\]\(/images/([^)\s]+)\)")


def find_topic(topics_data: dict, title: str) -> dict:
    for t in topics_data["topics"]:
        if t["title"] == title:
            return t
    raise SystemExit(f"No topic titled {title!r} in config/topics.yml")


def cmd_next(_args) -> int:
    cfg = gp.load_yaml(gp.SITE_CONFIG)
    topics_data = gp.load_yaml(gp.TOPICS_CONFIG)
    topic = gp.pick_next_topic(topics_data)
    pending = [t for t in topics_data["topics"] if t["status"] == "pending"]
    published = [t for t in topics_data["topics"] if t.get("status") == "published"]
    threshold = cfg["generation"].get("refill_threshold", 5)
    out = {
        "today": datetime.date.today().isoformat(),
        "pending_count": len(pending),
        "refill_needed": len(pending) < threshold,
        "refill_count": cfg["generation"].get("refill_count", 10),
        "pillars": [{"slug": p["slug"], "name": p["name"], "description": p["description"]}
                    for p in topics_data["pillars"]],
    }
    if topic is not None:
        pillar = next(p for p in topics_data["pillars"] if p["slug"] == topic["pillar"])
        out["topic"] = {
            "title": topic["title"],
            "pillar": topic["pillar"],
            "pillar_name": pillar["name"],
            "pillar_description": pillar["description"],
        }
        out["angle_instruction"] = gp.pick_angle(len(published))
        out["target_words"] = cfg["generation"].get("target_words", 1400)
    out["published_posts"] = gp.published_list(topics_data).splitlines()
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_park(args) -> int:
    """Research could not support the topic: keep it out of the queue, the
    same verdict generate_post.py records for InsufficientEvidence."""
    topics_data = gp.load_yaml(gp.TOPICS_CONFIG)
    topic = find_topic(topics_data, args.title)
    topic["status"] = "needs_review"
    topic["quality_issues"] = [args.reason]
    gp.save_yaml(gp.TOPICS_CONFIG, topics_data)
    print(f"parked: {args.title}")
    return 0


def cmd_add_topics(args) -> int:
    """Same validation as generate_post.refill_topics: known pillar, no
    duplicate title, season_months only 1-12."""
    topics_data = gp.load_yaml(gp.TOPICS_CONFIG)
    new_topics = json.loads(Path(args.file).read_text(encoding="utf-8"))
    valid = {p["slug"] for p in topics_data["pillars"]}
    existing = {t["title"].lower() for t in topics_data["topics"]}
    added = 0
    for nt in new_topics:
        title = (nt.get("title") or "").strip()
        if nt.get("pillar") not in valid or not title or title.lower() in existing:
            print(f"skipped: {title!r}")
            continue
        entry = {"title": title, "pillar": nt["pillar"], "status": "pending"}
        months = [m for m in nt.get("season_months") or [] if isinstance(m, int) and 1 <= m <= 12]
        if months:
            entry["season_months"] = months
        topics_data["topics"].append(entry)
        existing.add(title.lower())
        added += 1
    gp.save_yaml(gp.TOPICS_CONFIG, topics_data)
    print(f"added {added} topic(s)")
    return 0


def git(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argv], cwd=gp.ROOT, capture_output=True, text=True)


def cmd_finalize(args) -> int:
    today = datetime.date.today().isoformat()
    post = gp.POSTS_DIR / f"{today}-{args.slug}.md"
    if not post.exists():
        raise SystemExit(f"Missing {post.relative_to(gp.ROOT)} (file name must be <today>-<slug>.md)")
    fm, body = parse_frontmatter(post)
    topics_data = gp.load_yaml(gp.TOPICS_CONFIG)
    topic = find_topic(topics_data, args.title)
    problems = []
    if fm.get("slug") != args.slug:
        problems.append(f"frontmatter slug {fm.get('slug')!r} != {args.slug!r}")
    if str(fm.get("date")) != today:
        problems.append(f"frontmatter date {fm.get('date')!r} != {today!r}")
    if fm.get("pillar") != topic["pillar"]:
        problems.append(f"frontmatter pillar {fm.get('pillar')!r} != topic pillar {topic['pillar']!r}")
    if topic.get("status") != "pending":
        problems.append(f"topic status is {topic.get('status')!r}, expected 'pending'")
    hero = str(fm.get("hero_image") or "")
    if not hero.startswith("/images/") or not (gp.IMAGES_DIR / hero[len("/images/"):]).exists():
        problems.append(f"hero image {hero!r} missing")
    cfg = gp.load_yaml(gp.SITE_CONFIG)
    live_urls = {t["blogger_url"] for t in topics_data["topics"] if t.get("blogger_url")}
    problems += check_post.check(args.slug, cfg, live_urls)
    if problems:
        print("FINALIZE FAILED")
        for p in problems:
            print(f"  - {p}")
        return 1

    topic["status"] = "published"
    topic["published_slug"] = args.slug
    topic["written_by"] = "claude-code"
    gp.save_yaml(gp.TOPICS_CONFIG, topics_data)
    print(f"marked published: {args.title}")

    paths = [post, gp.RESEARCH_DIR / f"{args.slug}.json", gp.TOPICS_CONFIG,
             gp.IMAGES_DIR / hero[len("/images/"):]]
    paths += [gp.IMAGES_DIR / name for name in IMG_RE.findall(body)]
    rel = sorted({str(p.relative_to(gp.ROOT)).replace("\\", "/") for p in paths})
    if args.no_push:
        print("no-push: would commit " + " ".join(rel))
        return 0
    for step in (["add", "--", *rel],
                 ["commit", "-m", f"content: add scheduled post ({today})\n\nWritten by a Claude Code session (generator/CLAUDE_RUN.md)."]):
        r = git(*step)
        if r.returncode != 0:
            print(f"git {step[0]} failed:\n{r.stdout}{r.stderr}")
            return 1
    for attempt in range(3):
        pull = git("pull", "--rebase", "--autostash", "origin", "main")
        push = git("push", "origin", "HEAD:main") if pull.returncode == 0 else pull
        if push.returncode == 0:
            print("pushed to main")
            return 0
        print(f"push attempt {attempt + 1} failed:\n{push.stdout}{push.stderr}")
    return 1


def main() -> int:
    # The Windows console defaults to cp949; titles carry em dashes.
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next")
    p = sub.add_parser("park")
    p.add_argument("--title", required=True)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("add-topics")
    p.add_argument("file")
    p = sub.add_parser("finalize")
    p.add_argument("--title", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    return {"next": cmd_next, "park": cmd_park, "add-topics": cmd_add_topics,
            "finalize": cmd_finalize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
