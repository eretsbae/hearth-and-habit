#!/usr/bin/env python3
"""Per-post Google index state + 90-day search performance.

The Search Console "Pages" report only gives totals (71 indexed / 162 not as of
2026-11-04) and can't say *which* posts Google declined to index. This script
asks the URL Inspection API about every published post and joins the answer
with each URL's 90-day clicks/impressions, so pruning decisions rest on
Google's own verdict instead of guesses.

Writes data/index_status.json and docs/reports/index-status-YYYY-MM-DD.md.
Needs GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN with the
webmasters.readonly scope (the same token weekly_report.py uses). Read-only:
nothing on Blogger or Search Console is changed.
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blogger_publish import get_access_token, load_yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "config" / "topics.yml"
OUT_JSON = ROOT / "data" / "index_status.json"
REPORTS = ROOT / "docs" / "reports"
SITE = "sc-domain:hearth-habit.com"
INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
GSC = "https://www.googleapis.com/webmasters/v3"


def norm(url: str) -> str:
    p = urlsplit(url)
    return f"https://www.hearth-habit.com{p.path}"


def performance(headers: dict, today: datetime.date) -> dict[str, dict]:
    end = today - datetime.timedelta(days=3)
    start = end - datetime.timedelta(days=89)
    r = requests.post(
        f"{GSC}/sites/{requests.utils.quote(SITE, safe='')}/searchAnalytics/query",
        json={"startDate": start.isoformat(), "endDate": end.isoformat(),
              "dimensions": ["page"], "rowLimit": 1000},
        headers=headers, timeout=60,
    )
    r.raise_for_status()
    out: dict[str, dict] = {}
    for row in r.json().get("rows", []):
        key = norm(row["keys"][0])
        agg = out.setdefault(key, {"clicks": 0, "impressions": 0, "best_position": None})
        agg["clicks"] += int(row["clicks"])
        agg["impressions"] += int(row["impressions"])
        pos = round(row["position"], 1)
        if agg["best_position"] is None or pos < agg["best_position"]:
            agg["best_position"] = pos
    return out


def inspect(headers: dict, url: str) -> dict:
    for attempt in range(3):
        r = requests.post(INSPECT, json={"inspectionUrl": url, "siteUrl": SITE},
                          headers=headers, timeout=60)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        res = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
        return {
            "verdict": res.get("verdict"),
            "coverage": res.get("coverageState"),
            "last_crawl": res.get("lastCrawlTime"),
            "google_canonical": res.get("googleCanonical"),
        }
    return {"verdict": "ERROR", "coverage": "rate-limited"}


# 11-04 overhaul (prune, cornerstones, FAQ removal, stock heroes). AdSense
# submission gate: >= RECRAWL_GATE of live posts crawled on/after this date,
# so the reviewer and Google see the rewritten pages, not October copies.
OVERHAUL_DATE = "2026-11-04"
RECRAWL_GATE = 0.8


def main() -> int:
    today = datetime.date.today()
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    topics = load_yaml(TOPICS).get("topics", [])
    posts = [t for t in topics if t.get("status") == "published" and t.get("blogger_url")]
    perf = performance(headers, today)

    rows = []
    for t in posts:
        url = norm(t["blogger_url"])
        rec = {"slug": t.get("published_slug"), "title": t.get("title"),
               "pillar": t.get("pillar"), "url": url}
        rec.update(inspect(headers, url))
        rec.update(perf.get(url, {"clicks": 0, "impressions": 0, "best_position": None}))
        rows.append(rec)
        time.sleep(0.3)

    OUT_JSON.write_text(json.dumps({"date": today.isoformat(), "posts": rows},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    indexed = [r for r in rows if r.get("verdict") == "PASS"]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("coverage") or "?"] = counts.get(r.get("coverage") or "?", 0) + 1
    lines = [f"# 글별 색인 상태 — {today.isoformat()}", "",
             f"게시 글 {len(rows)}편 중 색인 {len(indexed)}편 (URL Inspection API, 속성 `{SITE}`).", "",
             "| 상태 | 글 수 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
    recrawled = sum(1 for r in rows if (r.get("last_crawl") or "") >= OVERHAUL_DATE)
    share = recrawled / len(rows) if rows else 0.0
    lines += ["", f"**개편({OVERHAUL_DATE}) 후 재크롤: {recrawled}/{len(rows)}편 ({share:.0%})** — "
              f"애드센스 제출 게이트 {RECRAWL_GATE:.0%} 이상: {'충족' if share >= RECRAWL_GATE else '미충족'}"]
    lines += ["", "| 글 | 필러 | 상태 | 마지막 크롤 | 90일 클릭 | 90일 노출 | 최고 순위 |",
              "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r.get("verdict") == "PASS", r["impressions"])):
        lines.append(f"| [{r['slug']}]({r['url']}) | {r['pillar']} | {r.get('coverage')} | "
                     f"{(r.get('last_crawl') or '-')[:10]} | {r['clicks']} | {r['impressions']} | {r['best_position'] or '-'} |")
    lines += ["", "자동 생성: `.github/workflows/index-status.yml` → `generator/index_status.py`."]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"index-status-{today.isoformat()}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(indexed)}/{len(rows)} indexed; recrawled since {OVERHAUL_DATE}: {recrawled}; {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
