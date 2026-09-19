#!/usr/bin/env python3
"""Close the bulk-CSV loop without a human touching git.

Until Pinterest grants Standard access, pins go up by uploading
bulk-upload/pinsNN.csv through Pinterest's content import (make_bulk_csv.py).
The recording half of that routine used to be manual: git pull, upload,
pinterest_publish.py --mark-pinned pinsNN, commit, push. Trial access can
*read* production, though (pinterest_client.py), so this script does the
recording instead:

  1. GET /v5/pins — every pin on the account.
  2. Match pins to posts that still await one, by the pin's link (path only,
     so a pin that still carries the old blogspot domain matches its post on
     the custom domain), falling back to the pin title.
  3. Record each match in config/topics.yml exactly as --mark-pinned would
     (pinterest_pin_id: manual — "manual" keeps make_bulk_csv.api_has_pinned()
     false, so the CSV era continues; the real id goes in
     pinterest_bulk_pin_id for the record).
  4. make_bulk_csv.auto_batch(): a fully recorded batch frees the next file,
     which is announced on the run summary and by KakaoTalk with its link.

Runs daily from pinterest-publish.yml after the API publish step, and the
workflow's commit step pushes topics.yml, the new CSV and any rotated tokens.
The only human step left is: tap the link, upload the file.

    python generator/pinterest_bulk_sync.py            # record + prepare next
    python generator/pinterest_bulk_sync.py --dry-run  # show matches, change nothing

Not configured (no Pinterest secrets) is not an error: the batch preparation
still runs, and the summary says the recording was skipped.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

import kakao_client  # noqa: E402
import make_bulk_csv  # noqa: E402
import pinterest_client as pc  # noqa: E402
from pinterest_publish import (  # noqa: E402
    TOPICS_CONFIG,
    candidates,
    load_yaml,
    post_meta,
    save_yaml,
    step_summary,
)

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def link_key(url: str | None) -> str:
    """Path of a URL, lowercased, without a trailing slash: the part of a
    post URL that survives the blogspot -> custom-domain move and any
    tracking parameters the importer might append."""
    if not url:
        return ""
    path = urlsplit(str(url).strip()).path.lower().rstrip("/")
    return path


def title_key(title: str | None) -> str:
    """Case-, punctuation- and whitespace-insensitive title, cut where the
    CSV cut it (Pinterest truncates titles at make_bulk_csv.TITLE_MAX)."""
    if not title:
        return ""
    t = _PUNCT.sub(" ", str(title)[: make_bulk_csv.TITLE_MAX].casefold())
    return _WS.sub(" ", t).strip()


def match_pins(topics: list[dict], pins: list[dict]) -> dict[str, dict]:
    """slug -> the pin that covers it, for topics that still await a pin.

    Link match first; a title match only when no pin carries a link that
    resolves to this post at all. Pins are newest first, and the first
    match wins, so a post pinned twice by accident is recorded against the
    newer pin either way.
    """
    by_link: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    for pin in pins:
        k = link_key(pin.get("link"))
        if k and k not in by_link:
            by_link[k] = pin
        k = title_key(pin.get("title"))
        if k and k not in by_title:
            by_title[k] = pin

    found: dict[str, dict] = {}
    for t in topics:
        slug = t["published_slug"]
        pin = by_link.get(link_key(t.get("blogger_url")))
        if pin is None:
            fm = post_meta(slug)
            pin = by_title.get(title_key(fm.get("title") or t.get("title")))
        if pin is not None:
            found[slug] = pin
    return found


def record(topics_data: dict, found: dict[str, dict]) -> list[dict]:
    """Stamp the matched topics the way --mark-pinned does. Returns them."""
    hit = []
    for t in topics_data.get("topics", []):
        pin = found.get(t.get("published_slug") or "")
        if pin is None or t.get("pinterest_pin_id"):
            continue
        t["pinterest_pin_id"] = "manual"
        if pin.get("id"):
            t["pinterest_bulk_pin_id"] = str(pin["id"])
        hit.append(t)
    return hit


def batch_status(topics_data: dict) -> dict[str, tuple[list[dict], list[dict]]]:
    """batch name -> (recorded posts, posts still awaiting a pin)."""
    out: dict[str, tuple[list[dict], list[dict]]] = {}
    for t in topics_data.get("topics", []):
        name = t.get("pinterest_batch")
        if not name:
            continue
        done, waiting = out.setdefault(str(name), ([], []))
        (done if t.get("pinterest_pin_id") else waiting).append(t)
    return out


def production_access_token() -> str | None:
    """None when the Pinterest secrets are absent (the daily run before the
    app was set up); the same loud-skip contract as pinterest_publish.py."""
    app_id = os.environ.get("PINTEREST_APP_ID", "").strip()
    app_secret = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    passphrase = os.environ.get("PINTEREST_TOKEN_PASSPHRASE", "").strip()
    if not (app_id and app_secret and passphrase and pc.TOKEN_FILE.exists()):
        return None
    stored = pc.load_tokens(passphrase)
    tokens = pc.refresh_access_token(app_id, app_secret, stored["refresh_token"])
    if tokens.get("refresh_token") and tokens["refresh_token"] != stored["refresh_token"]:
        pc.save_tokens({"refresh_token": tokens["refresh_token"]}, passphrase)
        print("Pinterest refresh token rotated; .secrets/pinterest_token.enc updated (commit it).")
    return tokens["access_token"]


def notify_recorded(hit: list[dict], status: dict[str, tuple[list[dict], list[dict]]]) -> None:
    """One KakaoTalk line per batch touched this run: closes the loop the
    upload opened, and names any row the importer dropped."""
    touched = sorted({str(t["pinterest_batch"]) for t in hit if t.get("pinterest_batch")})
    if not touched:
        return
    lines = []
    for name in touched:
        done, waiting = status[name]
        if waiting:
            lines.append(f"⚠️ {name}: {len(done)}/{len(done) + len(waiting)} 핀 확인, 미확인 "
                         + ", ".join(t["title"][:30] for t in waiting))
        else:
            lines.append(f"✅ {name}: {len(done)}핀 모두 확인, 기록 완료")
    cfg = load_yaml(make_bulk_csv.SITE_CONFIG)
    gh = cfg["github"]
    url = f"https://github.com/{gh['owner']}/{gh['repo']}/actions/workflows/pinterest-publish.yml"
    try:
        kakao_client.notify("📌 Pinterest 업로드 기록\n" + "\n".join(lines), url, "실행 기록 보기")
    except SystemExit as e:
        print(f"::warning::KakaoTalk alert failed: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Show which posts the account's pins cover; write nothing, "
                         "prepare no batch, send nothing")
    args = ap.parse_args()

    topics_data = load_yaml(TOPICS_CONFIG)
    # Every live post without a pin record, batched or not: a pin that exists
    # for an unbatched post is one the API must not create a second time.
    awaiting = candidates(topics_data)
    if not awaiting:
        print("Nothing awaits a pin; every live post with a pin image is recorded.")
    else:
        token = production_access_token()
        if token is None:
            summary = ("Pinterest not configured — cannot check for uploaded pins; "
                       f"{len(awaiting)} post(s) awaiting a record.")
            print(summary + " See docs/PINTEREST_SETUP.md.")
            print(f"::warning::{summary}")
            step_summary("## ⚠️ Pinterest 미설정 — 업로드된 핀을 확인하지 못했습니다\n\n"
                         "그동안은 `pinterest_publish.py --mark-pinned pinsNN`으로 직접 기록하세요.\n")
        else:
            try:
                pins = pc.list_pins(token)
            except SystemExit as e:
                # A Pinterest hiccup must not stop the batch preparation
                # below; the next daily run retries the read.
                print(f"::warning::could not read the account's pins: {e}")
                step_summary(f"## ⚠️ Pinterest 핀 목록 조회 실패\n\n```\n{e}\n```\n")
                pins = None
            if pins is not None:
                print(f"Pins on the account: {len(pins)}; posts awaiting a record: {len(awaiting)}")
                found = match_pins(awaiting, pins)
                for slug, pin in found.items():
                    print(f"  found: {slug}  <- pin {pin.get('id')} ({pin.get('link') or 'no link'})")
                if args.dry_run:
                    print(f"[dry-run] {len(found)} post(s) would be recorded; nothing written.")
                    return 0
                hit = record(topics_data, found)
                if hit:
                    save_yaml(TOPICS_CONFIG, topics_data)
                    status = batch_status(topics_data)
                    md = ["## ✅ Pinterest 업로드 확인 · 기록됨\n"]
                    for t in hit:
                        md.append(f"- {t['title']} (`{t.get('pinterest_batch') or 'no batch'}`)")
                    for name, (done, waiting) in sorted(status.items()):
                        if waiting and done:
                            md.append(f"\n⚠️ `{name}`: {len(waiting)}편이 아직 Pinterest에 보이지 않습니다 — "
                                      + ", ".join(t["title"] for t in waiting)
                                      + ". 가져오기가 그 행을 건너뛰었다면 낱개로 올리거나 "
                                      f"`--mark-pinned {name}`으로 기록하세요.")
                    step_summary("\n".join(md) + "\n")
                    for t in hit:
                        print(f"recorded: {t['published_slug']}")
                    notify_recorded(hit, status)
                else:
                    print("No new pins match a waiting post.")

    if args.dry_run:
        return 0
    print()
    make_bulk_csv.announce(make_bulk_csv.auto_batch())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
