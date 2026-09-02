#!/usr/bin/env python3
"""Build Pinterest bulk-upload CSVs for posts that still need a pin.

Pinterest's business account has a "content import" bulk create tool that
takes a CSV of up to 200 pins, so the whole backlog can go up without the
API. That matters because the developer app has been pending trial access
for months and, until it is approved, the portal withholds the app secret
and pinterest_publish.py cannot authenticate at all (docs/PINTEREST_SETUP.md).

The pin images are already committed and served from raw.githubusercontent.com,
which is exactly the publicly-fetchable "Media URL" the importer wants, so
nothing needs uploading by hand.

Columns are Pinterest's, in their order:

    Title, Media URL, Pinterest board, Thumbnail, Description, Link,
    Publish date, Keywords

Two of those stay empty on purpose:

  * Thumbnail is the timestamp to grab a still from, so it applies to video
    pins only. Ours are images.
  * Publish date left blank publishes on upload. Rather than guess at the
    date format the importer expects, pace the backlog with --per-file and
    upload one file a day; a new account that dumps 30 pins at once reads
    as spam.

Upload at: Pinterest → Settings → 콘텐츠 가져오기 (Content import) → .csv 업로드

Usage:
    python generator/make_bulk_csv.py                  # every pending post, one file
    python generator/make_bulk_csv.py --per-file 4     # split into 4-pin daily batches
    python generator/make_bulk_csv.py --limit 12
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from pinterest_publish import (  # noqa: E402
    TOPICS_CONFIG,
    SITE_CONFIG,
    candidates,
    load_yaml,
    pin_image_url,
    post_meta,
)

COLUMNS = ["Title", "Media URL", "Pinterest board", "Thumbnail",
           "Description", "Link", "Publish date", "Keywords"]

# Pinterest truncates past these; do it here so the sheet shows what will
# actually appear on the pin.
TITLE_MAX = 100
DESC_MAX = 500
MAX_ROWS_PER_FILE = 200  # the importer's stated ceiling


def row_for(topic: dict, pillars: dict, cfg: dict) -> dict:
    slug = topic["published_slug"]
    fm = post_meta(slug)
    title = (fm.get("title") or topic["title"]).strip()
    description = (fm.get("description") or "").strip() or title
    keywords = ", ".join(str(t).strip() for t in (fm.get("tags") or []))
    return {
        "Title": title[:TITLE_MAX],
        "Media URL": pin_image_url(cfg, slug),
        "Pinterest board": pillars.get(topic["pillar"], {}).get("name", ""),
        "Thumbnail": "",
        "Description": description[:DESC_MAX],
        "Link": topic["blogger_url"],
        "Publish date": "",
        "Keywords": keywords,
    }


def write_csv(path: Path, rows: list[dict], bom: bool) -> None:
    # newline="" so the csv module controls line endings (it writes CRLF,
    # which is what the importer expects) instead of the platform doubling them.
    with open(path, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="bulk-upload",
                    help="Directory for the generated CSVs (default: bulk-upload/)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only include this many pending posts (default: all)")
    ap.add_argument("--per-file", type=int, default=0,
                    help="Split into files of this many rows, to upload one a day "
                         "(default: a single file)")
    ap.add_argument("--no-bom", action="store_true",
                    help="Write plain UTF-8. The default matches Excel's "
                         "'CSV UTF-8' (BOM), which is what Pinterest's docs ask for")
    args = ap.parse_args()

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    # Same selection and board round-robin the API path uses, so a run here
    # and a run there never disagree about what is still pending.
    todo = candidates(topics_data)
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("Nothing pending; every live post with a pin image is already pinned.")
        return 0

    rows = [row_for(t, pillars, cfg) for t in todo]
    chunk = args.per_file or len(rows)
    if chunk > MAX_ROWS_PER_FILE:
        raise SystemExit(f"ERROR: {chunk} rows exceeds Pinterest's {MAX_ROWS_PER_FILE}-pin "
                         f"limit per upload; pass --per-file {MAX_ROWS_PER_FILE} or less.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = [rows[i:i + chunk] for i in range(0, len(rows), chunk)]

    print(f"{len(rows)} pin(s) pending -> {len(batches)} file(s) in {out_dir}/\n")
    for n, batch in enumerate(batches, 1):
        name = "pins.csv" if len(batches) == 1 else f"pins-{n:02d}.csv"
        write_csv(out_dir / name, batch, bom=not args.no_bom)
        slugs = [t["published_slug"] for t in todo[(n - 1) * chunk:(n - 1) * chunk + len(batch)]]
        print(f"{name}  ({len(batch)} pins)")
        for r in batch:
            print(f"    {r['Pinterest board']:<28} {r['Title'][:52]}")
        # Recording is the step that keeps the API from re-posting these once
        # the app is finally approved, so hand over the exact command.
        print("  after uploading, record them:")
        print(f"    python generator/pinterest_publish.py --mark-pinned {' '.join(slugs)}\n")

    boards = sorted({r["Pinterest board"] for r in rows})
    print("These boards must already exist on Pinterest, public, named exactly:")
    for b in boards:
        print(f"  - {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
