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
    python generator/make_bulk_csv.py --auto           # keep one batch waiting (see below)
    python generator/make_bulk_csv.py                  # every pending post, one file
    python generator/make_bulk_csv.py --per-file 4     # split into 4-pin daily batches
    python generator/make_bulk_csv.py --limit 12
    python generator/make_bulk_csv.py --per-file 4 --start 9   # force numbering

Files are numbered pinsNN.csv and the numbering continues from the highest
batch already in the output directory or recorded in config/topics.yml, so a
second run after more posts go live yields pins09, pins10, ... instead of
overwriting pins01 again. bulk-upload/ is committed, so the uploader only has
to git pull to get the next file.

--auto is what the daily pinterest-publish workflow runs, and what
pinterest_publish.py --mark-pinned runs right after recording a batch. It
keeps exactly one batch waiting for upload:

  * a batch is written to a CSV but not yet recorded  -> do nothing (or
    rebuild its CSV from topics.yml if the file is missing);
  * every batch is recorded and posts are still pending -> write the next
    pinsNN.csv with up to AUTO_BATCH_SIZE pins and stamp them;
  * the API has created a real pin (Standard access arrived) -> do nothing,
    the CSV era is over.

So until Pinterest grants Standard access the routine is: git pull, upload
bulk-upload/pinsNN.csv, --mark-pinned pinsNN, commit, push; the next file is
already there.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

from pinterest_publish import (  # noqa: E402
    TOPICS_CONFIG,
    SITE_CONFIG,
    batch_name,
    candidates,
    load_yaml,
    pin_image_url,
    post_meta,
    save_yaml,
    step_summary,
)

COLUMNS = ["Title", "Media URL", "Pinterest board", "Thumbnail",
           "Description", "Link", "Publish date", "Keywords"]

# Pinterest truncates past these; do it here so the sheet shows what will
# actually appear on the pin.
TITLE_MAX = 100
DESC_MAX = 500
MAX_ROWS_PER_FILE = 200  # the importer's stated ceiling
# One file a day, a few pins each, is what a young account absorbs without
# reading as spam; --auto never writes more than this in one file.
AUTO_BATCH_SIZE = 4
# Committed (not gitignored) so the next batch reaches the upload machine by
# git pull instead of having to be regenerated there.
BULK_DIR = ROOT / "bulk-upload"
# pins09.csv is the name the uploads were filed under; pins-09.csv is
# accepted too so an older run's files still count toward the numbering.
_BATCH_FILE = re.compile(r"^pins-?(\d+)\.csv$", re.IGNORECASE)


def next_batch_number(out_dir: Path, topics_data: dict) -> int:
    """1 + the highest batch seen so far, in out_dir or in config/topics.yml.

    The ledger in topics.yml is what makes the number stable across machines:
    bulk-upload/ is gitignored, so on a fresh clone the files alone would
    restart at pins01.
    """
    seen = [int(m.group(1)) for f in out_dir.glob("pins*.csv")
            if (m := _BATCH_FILE.match(f.name))]
    seen += [int(m.group(1)) for t in topics_data.get("topics", [])
             if (m := _BATCH_FILE.match(str(t.get("pinterest_batch", "")) + ".csv"))]
    return max(seen, default=0) + 1


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


def api_has_pinned(topics_data: dict) -> bool:
    """True once any pin was created through the API rather than by hand.

    That is the signal that Standard access arrived: from then on the daily
    workflow pins directly and a new CSV would only get posts pinned twice.
    """
    return any((t.get("pinterest_pin_id") or "manual") != "manual"
               for t in topics_data.get("topics", []))


def outstanding_batches(todo: list[dict]) -> dict[str, list[dict]]:
    """Batches written to a CSV but not yet recorded with --mark-pinned."""
    out: dict[str, list[dict]] = {}
    for t in todo:
        if t.get("pinterest_batch"):
            out.setdefault(str(t["pinterest_batch"]), []).append(t)
    return out


def auto_batch(out_dir: Path = BULK_DIR, per_file: int = AUTO_BATCH_SIZE,
               bom: bool = True) -> list[Path]:
    """Keep one CSV batch waiting for upload. Returns the files written.

    Safe to run any number of times: it writes only when nothing is waiting,
    and a batch stays "waiting" until pinterest_publish.py --mark-pinned
    records it, so a file is never generated on top of one still to upload.
    """
    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    if api_has_pinned(topics_data):
        print("The API has created pins already (Standard access); "
              "no more bulk CSVs will be generated.")
        return []

    todo = candidates(topics_data)
    written: list[Path] = []
    waiting = outstanding_batches(todo)
    if waiting:
        for name, members in sorted(waiting.items()):
            path = out_dir / f"{name}.csv"
            if path.exists():
                print(f"{name}.csv is waiting to be uploaded and recorded "
                      f"({len(members)} pins); nothing new generated.")
                continue
            # Assigned on another machine (or before bulk-upload/ was
            # committed): rebuild the same file from the ledger.
            out_dir.mkdir(parents=True, exist_ok=True)
            write_csv(path, [row_for(t, pillars, cfg) for t in members], bom)
            written.append(path)
            print(f"{name}.csv rebuilt from config/topics.yml ({len(members)} pins); "
                  f"upload it, then: python generator/pinterest_publish.py --mark-pinned {name}")
        return written

    if not todo:
        print("Nothing pending; every live post with a pin image is already pinned.")
        return []

    batch = todo[:per_file]
    stem = batch_name(next_batch_number(out_dir, topics_data))
    path = out_dir / f"{stem}.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(path, [row_for(t, pillars, cfg) for t in batch], bom)
    for t in batch:
        t["pinterest_batch"] = stem
    save_yaml(TOPICS_CONFIG, topics_data)
    written.append(path)
    print(f"{stem}.csv generated ({len(batch)} pins, {len(todo) - len(batch)} more pending):")
    for t in batch:
        print(f"    {pillars.get(t['pillar'], {}).get('name', ''):<28} {t['title'][:52]}")
    print(f"upload it, then: python generator/pinterest_publish.py --mark-pinned {stem}")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(BULK_DIR),
                    help="Directory for the generated CSVs (default: bulk-upload/)")
    ap.add_argument("--auto", action="store_true",
                    help="Keep one batch waiting for upload: write the next pinsNN.csv "
                         "only when every earlier batch is recorded, rebuild a recorded-"
                         "nowhere batch's missing file, and stop for good once the API "
                         "has pinned. Ignores --limit/--start/--include-assigned")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only include this many pending posts (default: all)")
    ap.add_argument("--per-file", type=int, default=0,
                    help="Split into files of this many rows, to upload one a day "
                         "(default: a single file)")
    ap.add_argument("--start", type=int, default=0,
                    help="Number the first file pins<START>.csv (default: continue "
                         "after the highest pinsNN.csv already in --out-dir)")
    ap.add_argument("--include-assigned", action="store_true",
                    help="Also include posts already written into an earlier "
                         "pinsNN.csv that has not been recorded as uploaded yet "
                         "(default: leave them to that file)")
    ap.add_argument("--no-bom", action="store_true",
                    help="Write plain UTF-8. The default matches Excel's "
                         "'CSV UTF-8' (BOM), which is what Pinterest's docs ask for")
    args = ap.parse_args()

    if args.auto:
        written = auto_batch(Path(args.out_dir), args.per_file or AUTO_BATCH_SIZE,
                             bom=not args.no_bom)
        if written:
            names = ", ".join(p.name for p in written)
            # Surface it on the Actions run page: a new file the uploader
            # never hears about is a batch that never goes up.
            print(f"::notice::bulk-upload/{names} ready — git pull, upload it via "
                  "Pinterest 콘텐츠 가져오기, then --mark-pinned")
            step_summary(
                "## 📌 Pinterest CSV 배치 준비됨\n\n"
                f"- `bulk-upload/{names}`\n"
                "- `git pull` → Pinterest 설정 → 콘텐츠 가져오기에 업로드 → 핀 생성 확인 → "
                "`python generator/pinterest_publish.py --mark-pinned pinsNN` → 커밋·푸시\n"
            )
        return 0

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    # Same selection and board round-robin the API path uses, so a run here
    # and a run there never disagree about what is still pending.
    todo = candidates(topics_data)
    if not args.include_assigned:
        # A post already sitting in pins10.csv on the uploader's disk must
        # not show up again in pins11.csv, or it gets pinned twice.
        todo = [t for t in todo if not t.get("pinterest_batch")]
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
    first = args.start or next_batch_number(out_dir, topics_data)

    print(f"{len(rows)} pin(s) pending -> {len(batches)} file(s) in {out_dir}/\n")
    for i, batch in enumerate(batches):
        stem = batch_name(first + i)
        name = f"{stem}.csv"
        write_csv(out_dir / name, batch, bom=not args.no_bom)
        members = todo[i * chunk:i * chunk + len(batch)]
        for t in members:
            t["pinterest_batch"] = stem
        print(f"{name}  ({len(batch)} pins)")
        for r in batch:
            print(f"    {r['Pinterest board']:<28} {r['Title'][:52]}")
        # Recording is the step that keeps the API from re-posting these once
        # the app is finally approved, so hand over the exact command.
        print("  after uploading, record them:")
        print(f"    python generator/pinterest_publish.py --mark-pinned {stem}\n")

    # The batch membership lives in topics.yml (committed) rather than only in
    # the gitignored CSV, so the upload can be recorded from any machine.
    save_yaml(TOPICS_CONFIG, topics_data)
    print(f"batch membership written to {TOPICS_CONFIG.relative_to(ROOT)} (commit it)\n")

    boards = sorted({r["Pinterest board"] for r in rows})
    print("These boards must already exist on Pinterest, public, named exactly:")
    for b in boards:
        print(f"  - {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
