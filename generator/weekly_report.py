#!/usr/bin/env python3
"""Weekly traffic report: Blogger pageviews → history → KakaoTalk.

What it does each run (weekly via GitHub Actions):
  1. Pulls blog pageview counts (7-day / 30-day / all-time) from the
     Blogger API v3 pageviews endpoint — same OAuth credentials as
     blogger_publish.py, no extra setup.
  2. Appends a snapshot to data/traffic_history.json (committed to the repo)
     and computes week-over-week deltas from the previous snapshot.
  3. Writes a full Korean report to docs/reports/weekly-YYYY-MM-DD.md.
  4. Sends a short KakaoTalk 나에게 보내기 summary with a link to the full
     report — if Kakao secrets are configured. Without them the report is
     still generated/committed and the run succeeds (the workflow prints a
     reminder), so traffic history accumulates from day one.

Required env (GitHub Actions secrets):
    GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN
Optional (enables KakaoTalk delivery):
    KAKAO_REST_API_KEY / KAKAO_TOKEN_PASSPHRASE (+ committed .secrets/kakao_token.enc)
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from blogger_publish import API_BASE, get_access_token, get_blog_id, load_yaml  # noqa: E402
import kakao_client  # noqa: E402

SITE_CONFIG = ROOT / "config" / "site.yml"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"
POSTS_DIR = ROOT / "content" / "posts"
HISTORY_FILE = ROOT / "data" / "traffic_history.json"
REPORTS_DIR = ROOT / "docs" / "reports"

RANGE_KEYS = {"SEVEN_DAYS": "pv_7d", "THIRTY_DAYS": "pv_30d", "ALL_TIME": "pv_all"}


def fetch_pageviews(access_token: str, blog_id: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/blogs/{blog_id}/pageviews",
        params=[("range", "7DAYS"), ("range", "30DAYS"), ("range", "all")],
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    out = {v: None for v in RANGE_KEYS.values()}
    for c in resp.json().get("counts", []):
        key = RANGE_KEYS.get(c.get("timeRange", ""))
        if key:
            out[key] = int(c.get("count", 0))
    return out


def content_stats(topics_data: dict, since: datetime.date) -> dict:
    topics = topics_data.get("topics", [])
    live = [t for t in topics if t.get("blogger_url")]
    new_this_week = []
    for t in live:
        slug = t.get("published_slug")
        if not slug:
            continue
        for p in POSTS_DIR.glob(f"*-{slug}.md"):
            try:
                post_date = datetime.date.fromisoformat(p.name[:10])
            except ValueError:
                continue
            if post_date >= since:
                new_this_week.append(t)
    return {
        "live_posts": len(live),
        "new_this_week": new_this_week,
        "pending": sum(1 for t in topics if t.get("status") == "pending"),
        "needs_review": sum(1 for t in topics if t.get("status") == "needs_review"),
        "unsynced": sum(1 for t in topics if t.get("status") == "published" and not t.get("blogger_url")),
    }


def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def fmt_delta(cur: int | None, prev: int | None) -> str:
    if cur is None or prev is None:
        return ""
    d = cur - prev
    return f" ({'+' if d >= 0 else ''}{d})"


def build_report_md(today: datetime.date, pv: dict, stats: dict, prev: dict | None) -> str:
    prev_pv = (prev or {}).get("pageviews", {})
    lines = [
        f"# 주간 트래픽 리포트 — {today.isoformat()}",
        "",
        "## 조회수 (Blogger 집계)",
        "",
        "| 구간 | 조회수 | 전주 대비 |",
        "|---|---|---|",
        f"| 최근 7일 | {pv['pv_7d']} | {fmt_delta(pv['pv_7d'], prev_pv.get('pv_7d')) or '—'} |",
        f"| 최근 30일 | {pv['pv_30d']} | {fmt_delta(pv['pv_30d'], prev_pv.get('pv_30d')) or '—'} |",
        f"| 누적 | {pv['pv_all']} | {fmt_delta(pv['pv_all'], prev_pv.get('pv_all')) or '—'} |",
        "",
        "## 콘텐츠 현황",
        "",
        f"- 발행 글: {stats['live_posts']}편 (이번 주 신규 {len(stats['new_this_week'])}편)",
        f"- 대기 주제: {stats['pending']}개 / 품질게이트 보류: {stats['needs_review']}개"
        + (f" / **미발행(인증 문제 등): {stats['unsynced']}편**" if stats["unsynced"] else ""),
    ]
    if stats["new_this_week"]:
        lines += ["", "### 이번 주 발행"]
        lines += [f"- [{t['title']}]({t['blogger_url']})" for t in stats["new_this_week"]]
    lines += [
        "",
        "---",
        "",
        "자동 생성: `.github/workflows/weekly-report.yml` → `generator/weekly_report.py`.",
        "조회수 이력 원본: `data/traffic_history.json`.",
    ]
    return "\n".join(lines) + "\n"


def build_kakao_text(today: datetime.date, pv: dict, stats: dict, prev: dict | None) -> str:
    prev_pv = (prev or {}).get("pageviews", {})
    return (
        f"📊 Hearth&Habit 주간 ({today.month}/{today.day})\n"
        f"조회수 7일: {pv['pv_7d']}{fmt_delta(pv['pv_7d'], prev_pv.get('pv_7d'))}\n"
        f"30일: {pv['pv_30d']} · 누적: {pv['pv_all']}\n"
        f"발행 {stats['live_posts']}편 (신규 {len(stats['new_this_week'])}) · 대기 {stats['pending']}"
        + (f"\n⚠️ 미발행 {stats['unsynced']}편" if stats["unsynced"] else "")
    )


def send_kakao(text: str, report_url: str) -> bool:
    rest_key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    passphrase = os.environ.get("KAKAO_TOKEN_PASSPHRASE", "").strip()
    if not rest_key or not passphrase or not kakao_client.TOKEN_FILE.exists():
        print("KakaoTalk not configured (KAKAO_REST_API_KEY / KAKAO_TOKEN_PASSPHRASE / "
              ".secrets/kakao_token.enc) — skipping send. See docs/KAKAO_REPORT.md.")
        return False
    stored = kakao_client.decrypt_token_file(passphrase)
    tokens = kakao_client.refresh_tokens(rest_key, stored["refresh_token"])
    if tokens.get("refresh_token"):
        # Kakao rotated the refresh token — persist it or delivery dies in ~30 days.
        kakao_client.encrypt_token_file({"refresh_token": tokens["refresh_token"]}, passphrase)
        print("Kakao refresh token rotated; .secrets/kakao_token.enc updated (commit it).")
    kakao_client.send_to_self(tokens["access_token"], text, report_url, "주간 리포트 보기")
    print("KakaoTalk report sent.")
    return True


def main() -> int:
    today = datetime.date.today()
    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)

    access_token = get_access_token()
    blog_url = cfg["blogger"]["blog_url"].strip()
    blog_id = (cfg["blogger"].get("blog_id") or "").strip() or get_blog_id(access_token, blog_url)

    pv = fetch_pageviews(access_token, blog_id)
    stats = content_stats(topics_data, since=today - datetime.timedelta(days=7))
    history = load_history()
    prev = history[-1] if history else None

    history.append({
        "date": today.isoformat(),
        "pageviews": pv,
        "live_posts": stats["live_posts"],
        "new_this_week": len(stats["new_this_week"]),
    })
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"weekly-{today.isoformat()}.md"
    report_path.write_text(build_report_md(today, pv, stats, prev), encoding="utf-8")
    print(f"Report written: {report_path.relative_to(ROOT)}")

    gh = cfg["github"]
    report_url = (
        f"https://github.com/{gh['owner']}/{gh['repo']}/blob/{gh['branch']}/"
        f"docs/reports/weekly-{today.isoformat()}.md"
    )
    text = build_kakao_text(today, pv, stats, prev)
    print("--- kakao text ---\n" + text + "\n------------------")
    send_kakao(text, report_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
