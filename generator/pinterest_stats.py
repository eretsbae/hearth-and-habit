#!/usr/bin/env python3
"""Snapshot the Pinterest account's last 28 days into data/pinterest_stats.json.

Pinterest is the site's main traffic bet besides search, and until now the
weekly report could not say whether it was working. This runs daily from
pinterest-publish.yml (after the pins go up) and keeps:

    {"updated": ..., "window": {"start": ..., "end": ...},
     "summary": {"IMPRESSION": n, "OUTBOUND_CLICK": n, "PIN_CLICK": n, "SAVE": n},
     "history": [{"date": ..., same four metrics for that 28-day window}, ...]}

weekly_report.py reads it. A failure here is a warning, never a failed run:
the pins matter more than the numbers about them.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

import pinterest_client as pc  # noqa: E402
from pinterest_bulk_sync import production_access_token  # noqa: E402

STATS_FILE = ROOT / "data" / "pinterest_stats.json"
METRICS = ("IMPRESSION", "OUTBOUND_CLICK", "PIN_CLICK", "SAVE")
HISTORY_DAYS = 120


def summarize(payload: dict) -> dict:
    """Sum the daily metrics of the "all" block (summary_metrics can lag a
    day behind the daily rows, so add the days up ourselves)."""
    block = payload.get("all") or {}
    totals = {m: 0 for m in METRICS}
    daily = block.get("daily_metrics") or []
    if daily:
        for day in daily:
            if day.get("data_status") not in (None, "READY"):
                continue
            for m in METRICS:
                totals[m] += int((day.get("metrics") or {}).get(m) or 0)
        return totals
    summary = block.get("summary_metrics") or {}
    return {m: int(summary.get(m) or 0) for m in METRICS}


def main() -> int:
    try:
        token = production_access_token()
        if token is None:
            print("::warning::Pinterest not configured; no stats snapshot.")
            return 0
        end = datetime.date.today() - datetime.timedelta(days=1)
        start = end - datetime.timedelta(days=27)
        payload = pc.account_analytics(token, start.isoformat(), end.isoformat(), ",".join(METRICS))
    except SystemExit as e:
        print(f"::warning::Pinterest stats skipped: {e}")
        return 0

    totals = summarize(payload)
    data = {}
    if STATS_FILE.exists():
        try:
            data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    history = [h for h in data.get("history", []) if h.get("date") != end.isoformat()]
    history.append({"date": end.isoformat(), **totals})
    data = {
        "updated": datetime.date.today().isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": totals,
        "history": history[-HISTORY_DAYS:],
    }
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Pinterest 28d ({start} .. {end}): " + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
