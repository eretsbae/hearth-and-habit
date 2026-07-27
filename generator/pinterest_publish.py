#!/usr/bin/env python3
"""Publish generated pin images to Pinterest, a few at a time.

Picks published posts that have a pin image but no pin yet, oldest first,
creates the pin on the board matching the post's pillar (creating that board
on first use), and records the pin id back into config/topics.yml so the same
post is never pinned twice.

Deliberately paced: Pinterest rewards steady daily activity and treats a
burst of dozens of pins from a new account as spam, so each run publishes a
small batch and the workflow runs daily.

Requires (GitHub Actions secrets):
    PINTEREST_APP_ID
    PINTEREST_APP_SECRET
    PINTEREST_TOKEN_PASSPHRASE
plus the committed .secrets/pinterest_token.enc from pinterest_auth.py.

Usage:
    python generator/pinterest_publish.py
    python generator/pinterest_publish.py --limit 5
    python generator/pinterest_publish.py --dry-run    # no API calls
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

import pinterest_client as pc  # noqa: E402
from make_pin import parse_front  # noqa: E402

SITE_CONFIG = ROOT / "config" / "site.yml"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"
POSTS_DIR = ROOT / "content" / "posts"
PINS_DIR = ROOT / "content" / "pins"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)


def pin_image_url(cfg: dict, slug: str) -> str:
    gh = cfg["github"]
    return (f"https://raw.githubusercontent.com/{gh['owner']}/{gh['repo']}/"
            f"{gh['branch']}/content/pins/{slug}.png")


def post_meta(slug: str) -> dict:
    """Frontmatter for a published slug, for the pin's title/description."""
    for path in POSTS_DIR.glob(f"*-{slug}.md"):
        return parse_front(path)
    return {}


def candidates(topics_data: dict) -> list[dict]:
    """Live posts that have a rendered pin but haven't been pinned yet,
    interleaved across pillars.

    Taken in file order the backlog is grouped by pillar, so a run would put
    its whole batch on one board. Round-robining means each run spreads
    across boards, which both looks like normal human activity and gives
    every board a steady trickle of fresh pins.
    """
    by_pillar: dict[str, list[dict]] = {}
    for t in topics_data.get("topics", []):
        slug = t.get("published_slug")
        if not slug or not t.get("blogger_url") or t.get("pinterest_pin_id"):
            continue
        if not (PINS_DIR / f"{slug}.png").exists():
            continue
        by_pillar.setdefault(t.get("pillar", ""), []).append(t)

    out, queues = [], list(by_pillar.values())
    while queues:
        for q in list(queues):
            out.append(q.pop(0))
            if not q:
                queues.remove(q)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3,
                    help="Max pins to create this run (default 3; paced on purpose)")
    ap.add_argument("--dry-run", action="store_true", help="List what would be pinned, no API calls")
    ap.add_argument("--mark-pinned", nargs="+", metavar="SLUG",
                    help="Record these slugs as already pinned by hand, so the "
                         "automation skips them and never double-posts")
    args = ap.parse_args()

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    if args.mark_pinned:
        wanted = set(args.mark_pinned)
        marked = []
        for t in topics_data["topics"]:
            if t.get("published_slug") in wanted:
                t["pinterest_pin_id"] = "manual"
                marked.append(t["published_slug"])
        missing = wanted - set(marked)
        if missing:
            raise SystemExit(f"ERROR: no published post found for: {', '.join(sorted(missing))}")
        save_yaml(TOPICS_CONFIG, topics_data)
        for slug in marked:
            print(f"marked as manually pinned: {slug}")
        return 0

    todo = candidates(topics_data)
    if not todo:
        print("Nothing to pin; every live post with a pin image is already on Pinterest.")
        return 0
    batch = todo[: args.limit]
    print(f"{len(todo)} post(s) awaiting a pin; publishing {len(batch)} this run.")

    if args.dry_run:
        for t in batch:
            slug = t["published_slug"]
            print(f"  [dry-run] {t['title']}")
            print(f"            board={pillars.get(t['pillar'], {}).get('name', '?')}")
            print(f"            image={pin_image_url(cfg, slug)}")
            print(f"            link={t['blogger_url']}")
        return 0

    app_id = os.environ["PINTEREST_APP_ID"]
    app_secret = os.environ["PINTEREST_APP_SECRET"]
    passphrase = os.environ["PINTEREST_TOKEN_PASSPHRASE"]

    stored = pc.load_tokens(passphrase)
    tokens = pc.refresh_access_token(app_id, app_secret, stored["refresh_token"])
    access_token = tokens["access_token"]
    if tokens.get("refresh_token") and tokens["refresh_token"] != stored["refresh_token"]:
        # Pinterest rotated it — persist or the next run authenticates with a dead token.
        pc.save_tokens({"refresh_token": tokens["refresh_token"]}, passphrase)
        print("Pinterest refresh token rotated; .secrets/pinterest_token.enc updated (commit it).")

    board_cache = {b["name"]: b["id"] for b in pc.list_boards(access_token)}

    pinned_any = False
    for topic in batch:
        slug = topic["published_slug"]
        pillar = pillars.get(topic["pillar"], {})
        board_name = pillar.get("name") or "Home & Living"
        board_id = pc.ensure_board(access_token, board_name,
                                   pillar.get("description", ""), board_cache)

        fm = post_meta(slug)
        title = fm.get("title") or topic["title"]
        description = (fm.get("description") or "").strip() or title

        print(f"Pinning: {title}")
        result = pc.create_pin(
            access_token, board_id, title, description,
            topic["blogger_url"], pin_image_url(cfg, slug),
        )
        topic["pinterest_pin_id"] = result.get("id", "")
        print(f"  -> pin {topic['pinterest_pin_id']} on '{board_name}'")
        pinned_any = True
        # Save after each pin: a mid-batch API error must not lose the record
        # of pins already created, or the next run would duplicate them.
        save_yaml(TOPICS_CONFIG, topics_data)

    if pinned_any:
        remaining = len(todo) - len(batch)
        print(f"Done. {remaining} post(s) still queued for future runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
