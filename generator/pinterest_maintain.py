#!/usr/bin/env python3
"""Bring the pins already on Pinterest in line with the site as it is now.

The posts were rewritten, pruned and merged (2026-09 .. 2026-11), but a pin
is a copy taken on the day it was made: its title, description and link
never followed. This walks every pin on the account and, matching each pin
to its post by link path:

  * pin -> a post that was pruned (status drafted) or retired, and another
    live post genuinely answers the pin's question (RELINKS below, or the
    retired topic's redirect_to): point the pin at that post and say so in
    the description. The title stays, because it is printed on the pin's
    image and must keep matching it.
  * pin -> a pruned post with no such replacement: move the pin to a secret
    board ("Archived pins"). Nothing is deleted; moving it back is one
    board change.
  * pin -> a live post: title and description become the post's current
    title and meta description. A pin whose title is one of the post's
    pin_hooks keeps it (the hook is what its image says).

The image of an existing pin cannot be changed through the API; posts that
deserve a new picture get one new pin each from pinterest_publish.py's
refresh queue instead.

    python generator/pinterest_maintain.py            # dry run: report only
    python generator/pinterest_maintain.py --apply    # make the changes

Runs from .github/workflows/pinterest-maintain.yml (manual dispatch), which
holds the Pinterest secrets and commits the rotated token.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

import pinterest_client as pc  # noqa: E402
from make_pin import hook_text  # noqa: E402
from pinterest_bulk_sync import link_key, production_access_token  # noqa: E402
from pinterest_publish import (  # noqa: E402
    TOPICS_CONFIG,
    load_yaml,
    post_meta,
    save_yaml,
    step_summary,
)

ARCHIVE_BOARD = "Archived pins"

# Pruned post -> the live post that answers the same question. Each pair was
# checked against the target's body (2026-11-05): the target has a section
# that answers the pruned post's title, not just the same topic.
RELINKS = {
    "toilet-runs-few-seconds-then-stops": "fix-running-toilet-without-plumber",
    "why-basement-smells-musty-in-summer": "musty-smell-in-house-find-the-source",
    "why-does-my-closet-smell-musty": "musty-smell-in-house-find-the-source",
    "how-often-wash-bath-towels": "house-cleaning-schedule-by-room-frequency",
    "forgotten-home-maintenance-tasks-seasonal-checklist": "winter-home-prep-checklist-before-first-freeze",
    "closing-vents-unused-rooms-energy": "why-is-one-room-always-colder-than-rest",
    "do-you-need-to-clean-gutters-with-gutter-guards": "fall-yard-cleanup-checklist-before-winter",
    "last-mow-height-before-winter": "low-effort-lawn-care-bare-minimum",
    "how-to-store-produce-fridge-map": "why-greens-wilt-fast-how-to-store-them",
}


def norm(text: str | None) -> str:
    return " ".join(str(text or "").split()).casefold()


def old_urls(t: dict) -> list[str]:
    return [u for u in (t.get("blogger_url"), t.get("drafted_url"), t.get("retired_url")) if u]


def plan(topics_data: dict, pins: list[dict]) -> tuple[list[dict], list[dict]]:
    """(actions, unmatched pins). Each action: pin, slug, kind, fields."""
    topics = topics_data.get("topics", [])
    live = {t["published_slug"]: t for t in topics
            if t.get("status") == "published" and t.get("published_slug") and t.get("blogger_url")}
    by_path: dict[str, dict] = {}
    for t in topics:
        for u in old_urls(t):
            by_path.setdefault(link_key(u), t)

    actions, unmatched = [], []
    for pin in pins:
        t = by_path.get(link_key(pin.get("link")))
        if t is None:
            unmatched.append(pin)
            continue
        slug = t.get("published_slug")
        if t.get("status") == "published":
            # Pins made in the current design were written from the current
            # post; leave them alone.
            if pin.get("id") in (t.get("pinterest_refresh_pin_id"),) or (
                    t.get("pinterest_pin_design") and pin.get("id") == t.get("pinterest_pin_id")):
                continue
            fm = post_meta(slug)
            if not fm:
                continue
            hooks = {norm(hook_text(h)) for h in fm.get("pin_hooks") or []}
            fields = {}
            if norm(pin.get("title")) not in hooks and norm(pin.get("title")) != norm(fm["title"]):
                fields["title"] = fm["title"]
            desc = (fm.get("description") or "").strip()
            if desc and norm(pin.get("description")) != norm(desc):
                fields["description"] = desc
            if fields:
                actions.append({"pin": pin, "slug": slug, "kind": "retext", "fields": fields})
            continue

        target_slug = RELINKS.get(slug) or (t.get("redirect_to") if t.get("status") == "retired" else None)
        target = live.get(target_slug or "")
        if target:
            fm = post_meta(target_slug)
            desc = (f"Answered in our guide “{fm.get('title') or target['title']}”: "
                    f"{(fm.get('description') or '').strip()}").strip()
            fields = {}
            if link_key(pin.get("link")) != link_key(target["blogger_url"]):
                fields["link"] = target["blogger_url"]
            if norm(pin.get("description")) != norm(desc):
                fields["description"] = desc
            if fields:
                actions.append({"pin": pin, "slug": slug, "kind": "relink", "target": target_slug,
                                "fields": fields})
        elif t.get("status") == "drafted":
            actions.append({"pin": pin, "slug": slug, "kind": "archive", "fields": {}})
        else:
            unmatched.append(pin)
    return actions, unmatched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Make the changes (default: report only)")
    args = ap.parse_args()

    token = production_access_token()
    if token is None:
        print("::error::Pinterest secrets are not available to this run.")
        return 1

    topics_data = load_yaml(TOPICS_CONFIG)
    pins = pc.list_pins(token)
    boards = pc.list_boards(token)
    board_cache = pc.board_index(boards)
    archive_id = board_cache.get(pc.board_key(ARCHIVE_BOARD))
    already_archived = {p.get("id") for p in pins if archive_id and p.get("board_id") == archive_id}

    actions, unmatched = plan(topics_data, pins)
    actions = [a for a in actions if not (a["kind"] == "archive" and a["pin"].get("id") in already_archived)]
    print(f"{len(pins)} pins on the account; {len(actions)} to change; "
          f"{len(unmatched)} not linked to any known post.")

    counts = {"retext": 0, "relink": 0, "archive": 0}
    applied: set[int] = set()
    archive_blocked = None  # reason, when the secret board can't be made
    lines = []
    for i, a in enumerate(actions):
        pin = a["pin"]
        label = {"retext": "문구 갱신", "relink": f"재연결 → {a.get('target')}",
                 "archive": "보관 보드로 이동"}[a["kind"]]
        print(f"  [{a['kind']}] {pin.get('id')} {a['slug']}: {', '.join(a['fields']) or 'board'}")
        lines.append(f"- {label}: `{a['slug']}` (pin {pin.get('id')})")
        if not args.apply:
            continue
        fields = dict(a["fields"])
        if a["kind"] == "archive":
            if archive_blocked:
                continue
            if archive_id is None:
                try:
                    archive_id = pc.ensure_board(
                        token, ARCHIVE_BOARD,
                        "Pins whose articles were retired from the site. Kept, not deleted.",
                        board_cache, privacy="SECRET")
                except SystemExit as e:
                    # A secret board needs boards:write_secret; tokens issued
                    # before that scope was requested get 403 (code 29). Do
                    # the retext/relink work anyway and leave archiving for
                    # after a re-auth (python generator/pinterest_auth.py).
                    archive_blocked = str(e)
                    print(f"::warning::archive skipped: {e}")
                    continue
            fields["board_id"] = archive_id
        pc.update_pin(token, pin["id"], **fields)
        applied.add(i)
        counts[a["kind"]] += 1
        time.sleep(0.4)

    if args.apply:
        today = datetime.date.today().isoformat()
        by_slug = {t.get("published_slug"): t for t in topics_data.get("topics", [])}
        for i, a in enumerate(actions):
            if i not in applied:
                continue
            t = by_slug.get(a["slug"])
            if t is None:
                continue
            if a["kind"] == "relink":
                t["pinterest_relinked_to"] = a["target"]
            elif a["kind"] == "archive":
                t["pinterest_archived_at"] = today
        save_yaml(TOPICS_CONFIG, topics_data)

    for pin in unmatched:
        print(f"  [unmatched] {pin.get('id')} {pin.get('link') or '(no link)'} — {pin.get('title')}")

    head = "## 📌 Pinterest 정리 " + ("(적용)" if args.apply else "(점검만 — 변경 없음)")
    step_summary(
        f"{head}\n\n"
        f"- 계정의 핀: **{len(pins)}개**\n"
        f"- 변경 대상: 문구 갱신 {sum(a['kind'] == 'retext' for a in actions)} · "
        f"재연결 {sum(a['kind'] == 'relink' for a in actions)} · "
        f"보관 {sum(a['kind'] == 'archive' for a in actions)}\n"
        f"- 알 수 없는 링크의 핀: {len(unmatched)}개\n"
        + ("- ⚠️ 보관 이동 건너뜀: 토큰에 비밀 보드 권한 없음 — `python generator/pinterest_auth.py` 재인증 필요\n"
           if archive_blocked else "")
        + "\n" + "\n".join(lines[:200]) + "\n"
    )
    if args.apply:
        print(f"Applied: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
