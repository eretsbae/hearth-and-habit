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
import re
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


def step_summary(markdown: str) -> None:
    """Append to the GitHub Actions run summary when running on a runner.

    A skipped run still reports as a green check, which is exactly how four
    weeks of no-op runs went unnoticed. Anything that makes a run a no-op
    belongs on the run's own page, not only in the step log nobody opens.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(markdown.rstrip() + "\n")


def pin_image_url(cfg: dict, slug: str) -> str:
    gh = cfg["github"]
    return (f"https://raw.githubusercontent.com/{gh['owner']}/{gh['repo']}/"
            f"{gh['branch']}/content/pins/{slug}.png")


def post_meta(slug: str) -> dict:
    """Frontmatter for a published slug, for the pin's title/description."""
    for path in POSTS_DIR.glob(f"*-{slug}.md"):
        return parse_front(path)
    return {}


_BATCH_NAME = re.compile(r"^pins-?(\d+)$", re.IGNORECASE)


def batch_name(n: int) -> str:
    return f"pins{n:02d}"


def expand_batches(args: list[str], topics_data: dict) -> set[str]:
    """Slugs from a --mark-pinned list where items may be batch names.

    make_bulk_csv.py stamps each post it writes into pinsNN.csv with
    pinterest_batch: pinsNN, so "uploaded pins10" is enough to record the
    whole file without copying four slugs around.
    """
    wanted: set[str] = set()
    for item in args:
        m = _BATCH_NAME.match(item)
        if not m:
            wanted.add(item)
            continue
        name = batch_name(int(m.group(1)))
        slugs = [t["published_slug"] for t in topics_data.get("topics", [])
                 if t.get("published_slug") and t.get("pinterest_batch") == name]
        if not slugs:
            raise SystemExit(f"ERROR: no posts are recorded under batch {name} "
                             "(config/topics.yml: pinterest_batch)")
        wanted.update(slugs)
    return wanted


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


def sandbox_access_token(app_id: str, app_secret: str, passphrase: str) -> str:
    """An access token the sandbox host accepts.

    Production tokens are rejected there, so: use PINTEREST_SANDBOX_TOKEN if
    set (the 30-day token the developer portal mints on the app page), else
    try the production refresh token against the sandbox token endpoint.
    Nothing is written to .secrets/ either way; the production token file
    must stay exactly as the daily workflow expects it.
    """
    direct = os.environ.get("PINTEREST_SANDBOX_TOKEN", "").strip()
    if direct:
        print("sandbox: using PINTEREST_SANDBOX_TOKEN")
        return direct
    stored = pc.load_tokens(passphrase)
    try:
        tokens = pc.refresh_access_token(app_id, app_secret, stored["refresh_token"], sandbox=True)
        print("sandbox: access token issued by api-sandbox.pinterest.com")
        return tokens["access_token"]
    except SystemExit as e:
        raise SystemExit(
            f"{e}\n\nThe sandbox would not issue a token from the production refresh token. "
            "Mint a sandbox token in the developer portal (My apps -> the app -> Manage -> "
            "generate sandbox/test token) and pass it as PINTEREST_SANDBOX_TOKEN:\n"
            '    $env:PINTEREST_SANDBOX_TOKEN = "<token>"    (PowerShell)\n'
            "then re-run with --sandbox."
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3,
                    help="Max pins to create this run (default 3; paced on purpose)")
    ap.add_argument("--dry-run", action="store_true", help="List what would be pinned, no API calls")
    ap.add_argument("--sandbox", action="store_true",
                    help="Create the pins on api-sandbox.pinterest.com instead of production. "
                         "Nothing reaches the real profile and nothing is recorded in "
                         "topics.yml; this is what Trial access allows and what the "
                         "Standard-access demo video is recorded against")
    ap.add_argument("--whoami", action="store_true",
                    help="Authenticate, print the Pinterest account this token belongs "
                         "to, and exit (proves the OAuth grant works)")
    ap.add_argument("--mark-pinned", nargs="+", metavar="SLUG|pinsNN",
                    help="Record these slugs as already pinned by hand, so the "
                         "automation skips them and never double-posts. A batch "
                         "name such as pins10 expands to every post make_bulk_csv.py "
                         "put in that file (config/topics.yml: pinterest_batch)")
    ap.add_argument("--unmark-pinned", nargs="+", metavar="SLUG",
                    help="Undo --mark-pinned, returning these slugs to the queue. "
                         "For when a batch was recorded before its upload actually "
                         "went through")
    args = ap.parse_args()

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    if args.mark_pinned or args.unmark_pinned:
        marking = bool(args.mark_pinned)
        wanted = expand_batches(args.mark_pinned or args.unmark_pinned, topics_data)
        hit, from_api = [], []
        for t in topics_data["topics"]:
            if t.get("published_slug") not in wanted:
                continue
            if marking:
                t["pinterest_pin_id"] = "manual"
            else:
                # Clearing a real pin id would have the next run create a
                # second pin for a post that already has one. Only bookkeeping
                # entries ("manual") are safe to undo here.
                if (t.get("pinterest_pin_id") or "manual") != "manual":
                    from_api.append(t["published_slug"])
                    continue
                t.pop("pinterest_pin_id", None)
            hit.append(t["published_slug"])
        missing = wanted - set(hit) - set(from_api)
        if missing:
            raise SystemExit(f"ERROR: no published post found for: {', '.join(sorted(missing))}")
        if from_api:
            raise SystemExit(
                "ERROR: these carry a real Pinterest pin id, not a manual record, so "
                f"clearing them would double-post: {', '.join(sorted(from_api))}. "
                "Delete the pin on Pinterest first if you really want it re-created.")
        save_yaml(TOPICS_CONFIG, topics_data)
        verb = "marked as manually pinned" if marking else "returned to the queue"
        for slug in hit:
            print(f"{verb}: {slug}")
        if marking:
            # Recording a batch is what frees the next one: write it now so the
            # uploader commits topics.yml and the next CSV together and never
            # waits on the daily workflow for a file. Lazy import: that module
            # imports this one.
            import make_bulk_csv
            print()
            make_bulk_csv.auto_batch()
        return 0

    if args.sandbox:
        pc.use_sandbox()
        print("=== SANDBOX MODE: api-sandbox.pinterest.com — pins are not published, "
              "nothing is recorded ===")

    todo = candidates(topics_data)
    # Posts sitting in a bulk CSV that has not been recorded yet are the
    # uploader's: pinning them here too would put them up twice the day the
    # app gets Standard access. They come back once --mark-pinned records
    # the batch (or the pinterest_batch lines are removed from topics.yml).
    held = [t for t in todo if t.get("pinterest_batch")]
    todo = [t for t in todo if not t.get("pinterest_batch")]
    if held and not args.whoami:
        names = sorted({str(t["pinterest_batch"]) for t in held})
        print(f"{len(held)} post(s) held back: in bulk batch {', '.join(names)} awaiting "
              "upload; record it with --mark-pinned, or drop its pinterest_batch lines "
              "in config/topics.yml to hand the posts to the API.")
    if not todo and not args.whoami:
        print("Nothing to pin; every live post with a pin image is already on Pinterest.")
        return 0
    batch = todo[: args.limit]
    if not args.whoami:
        print(f"{len(todo)} post(s) awaiting a pin; publishing {len(batch)} this run.")

    if args.dry_run:
        for t in batch:
            slug = t["published_slug"]
            print(f"  [dry-run] {t['title']}")
            print(f"            board={pillars.get(t['pillar'], {}).get('name', '?')}")
            print(f"            image={pin_image_url(cfg, slug)}")
            print(f"            link={t['blogger_url']}")
        return 0

    app_id = os.environ.get("PINTEREST_APP_ID", "").strip()
    app_secret = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    passphrase = os.environ.get("PINTEREST_TOKEN_PASSPHRASE", "").strip()

    # Skip without failing when the app isn't set up yet: this workflow is on
    # a daily cron and Pinterest apps sit in "trial access pending" for weeks,
    # so a hard error here is a daily failure notification for a state that is
    # expected. Skip loudly, though — the first version of this was silent, and
    # a month of green-but-no-op runs went unnoticed because a skipped run is
    # indistinguishable from a working one on the Actions list.
    sandbox_token = os.environ.get("PINTEREST_SANDBOX_TOKEN", "").strip()
    configured = app_id and app_secret and passphrase and pc.TOKEN_FILE.exists()
    # A portal-minted sandbox token is self-contained: no app secret, no
    # refresh, no token file. Demo runs should not need the production trio.
    if not configured and not (args.sandbox and sandbox_token):
        missing = [name for name, present in (
            ("PINTEREST_APP_ID", app_id),
            ("PINTEREST_APP_SECRET", app_secret),
            ("PINTEREST_TOKEN_PASSPHRASE", passphrase),
            (".secrets/pinterest_token.enc", pc.TOKEN_FILE.exists()),
        ) if not present]
        summary = (f"Pinterest not configured — skipping send; {len(todo)} post(s) "
                   f"waiting. Missing: {', '.join(missing)}.")
        print(summary + " See docs/PINTEREST_SETUP.md.")
        print(f"::warning::{summary}")
        step_summary(
            "## ⚠️ Pinterest 미설정 — 핀을 하나도 올리지 않았습니다\n\n"
            f"- 대기 중인 글: **{len(todo)}편**\n"
            "- 빠진 항목: " + ", ".join(f"`{m}`" for m in missing) + "\n"
            "- 설정 방법: `docs/PINTEREST_SETUP.md`\n\n"
            "앱이 아직 trial access 승인 대기 중이라면 이 상태가 정상입니다. "
            "그동안은 `bulk-upload/pinsNN.csv`(다음 단계에서 자동 생성)를 \"콘텐츠 가져오기\"로 올리고 "
            "`pinterest_publish.py --mark-pinned pinsNN` 으로 기록하세요.\n"
        )
        return 0

    if args.sandbox:
        access_token = sandbox_access_token(app_id, app_secret, passphrase)
    else:
        stored = pc.load_tokens(passphrase)
        tokens = pc.refresh_access_token(app_id, app_secret, stored["refresh_token"])
        access_token = tokens["access_token"]
        if tokens.get("refresh_token") and tokens["refresh_token"] != stored["refresh_token"]:
            # Pinterest rotated it — persist or the next run authenticates with a dead token.
            pc.save_tokens({"refresh_token": tokens["refresh_token"]}, passphrase)
            print("Pinterest refresh token rotated; .secrets/pinterest_token.enc updated (commit it).")

    if args.whoami:
        me = pc.get_user_account(access_token)
        print("Authenticated as:")
        for k in ("username", "account_type", "profile_image", "website_url", "id"):
            if me.get(k):
                print(f"  {k:<14} {me[k]}")
        return 0

    boards = pc.list_boards(access_token)
    print(f"Boards on this account: {len(boards)}")
    for b in boards:
        print(f"  - {b.get('name')}  (id {b.get('id')})")
    board_cache = pc.board_index(boards)

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
        try:
            result = pc.create_pin(
                access_token, board_id, title, description,
                topic["blogger_url"], pin_image_url(cfg, slug),
            )
        except pc.TrialAccessOnly as e:
            # Expected state until Pinterest grants Standard access. Same
            # loud-skip treatment as "not configured": a red run every day
            # would just be noise, but the summary must say nothing went up.
            summary = (f"Pinterest app has Trial access only, which cannot create "
                       f"production pins; {len(todo)} post(s) waiting. ({e})")
            print(summary)
            print(f"::warning::{summary}")
            step_summary(
                "## ⚠️ Pinterest Trial access — 핀을 올릴 수 없습니다\n\n"
                f"- 대기 중인 글: **{len(todo)}편**\n"
                "- Trial access는 sandbox에만 핀을 만들 수 있습니다(403 code 29). "
                "실제 게시에는 **Standard access**가 필요합니다: 개발자 포털 → 내 앱 → **업그레이드**.\n"
                "- 그동안은 `bulk-upload/pinsNN.csv`(다음 단계에서 자동 생성)를 \"콘텐츠 가져오기\"로 올리고 "
                "`pinterest_publish.py --mark-pinned pinsNN`으로 기록하세요.\n"
            )
            return 0
        if args.sandbox:
            # Sandbox pins never appear on the profile, so recording their ids
            # would wrongly retire the post from the production queue.
            print(f"  -> sandbox pin {result.get('id')} on '{board_name}' (board {board_id})")
            print(f"     link  {result.get('link')}")
            print(f"     title {result.get('title')}")
            continue
        topic["pinterest_pin_id"] = result.get("id", "")
        print(f"  -> pin {topic['pinterest_pin_id']} on '{board_name}'")
        pinned_any = True
        # Save after each pin: a mid-batch API error must not lose the record
        # of pins already created, or the next run would duplicate them.
        save_yaml(TOPICS_CONFIG, topics_data)

    if args.sandbox:
        print("Sandbox run complete; topics.yml untouched.")
        return 0
    if pinned_any:
        remaining = len(todo) - len(batch)
        print(f"Done. {remaining} post(s) still queued for future runs.")
        step_summary(
            f"## 📌 핀 {len(batch)}개 게시\n\n"
            + "".join(f"- {t['title']}\n" for t in batch)
            + f"\n남은 대기: **{remaining}편**\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
