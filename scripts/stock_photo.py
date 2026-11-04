"""Find and import an openly licensed stock photo as a post or page hero.

Why this exists (2026-10-13): all 148 images on the live site were flat SVG
illustrations, and the owner decided not to supply photos. Real, openly
licensed photos break that uniformity without inventing anything. Only
licenses that allow commercial reuse are accepted and every photo keeps its
attribution in the frontmatter (`hero_credit`, `hero_credit_url`,
`hero_license_url`), which the publisher renders as a caption.

Source: the Openverse API (https://api.openverse.org), no key needed. It
indexes Flickr, Wikimedia Commons and others and exposes the license per
result. `--source commons` queries the Wikimedia Commons API directly (added
2026-11-04 when the Openverse API stopped answering); results are normalised
to the same shape and ids look like `commons-<pageid>`.

Usage (run from the repo root):
    python scripts/stock_photo.py search "furnace filter" --n 8 --sheet .tmp/furnace.png
        -> prints numbered candidates and writes a contact sheet to look at
    python scripts/stock_photo.py fetch <openverse_id> --slug <slug>
        -> writes content/images/<slug>-hero.jpg (1200x675, centre crop) and
           prints the frontmatter lines to paste into the post or page
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT / "content" / "images"
CACHE = ROOT / ".tmp" / "openverse"
API = "https://api.openverse.org/v1/images/"
UA = "hearth-habit-stock-photo/1.0 (https://www.hearth-habit.com)"
ALLOWED_LICENSES = {"cc0", "pdm", "by", "by-sa"}
HERO_W, HERO_H = 1200, 675

LICENSE_LABEL = {"cc0": "CC0", "pdm": "Public Domain", "by": "CC BY", "by-sa": "CC BY-SA"}


def search(query: str, n: int) -> list[dict]:
    resp = requests.get(
        API,
        params={
            "q": query,
            "license": ",".join(sorted(ALLOWED_LICENSES)),
            "license_type": "commercial,modification",
            "mature": "false",
            "page_size": 20,
        },
        headers={"User-Agent": UA},
        timeout=30,
    )
    resp.raise_for_status()
    out = []
    for r in resp.json().get("results", []):
        # Openverse reports the size of the URL it indexed; anything under
        # 800 px wide would be upscaled into a blurry hero, so skip it.
        if r.get("license") not in ALLOWED_LICENSES or (r.get("width") or 0) < 800:
            continue
        out.append(r)
        if len(out) >= n:
            break
    CACHE.mkdir(parents=True, exist_ok=True)
    for r in out:
        (CACHE / f"{r['id']}.json").write_text(json.dumps(r), encoding="utf-8")
    return out


COMMONS = "https://commons.wikimedia.org/w/api.php"


def commons_license(short: str) -> tuple[str, str] | None:
    """Map Commons' LicenseShortName to (openverse-style license, version)."""
    t = short.strip().lower()
    if t in {"cc0", "cc0 1.0"}:
        return "cc0", "1.0"
    if t.startswith("public domain") or t == "pd":
        return "pdm", ""
    for key, code in (("cc by-sa ", "by-sa"), ("cc-by-sa-", "by-sa"), ("cc by ", "by"), ("cc-by-", "by")):
        if t.startswith(key):
            return code, t[len(key):].strip()
    return None


def search_commons(query: str, n: int) -> list[dict]:
    resp = requests.get(COMMONS, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{query} filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "iiurlwidth": 1600,
    }, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    pages = sorted((resp.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for pg in pages:
        info = (pg.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = commons_license((meta.get("LicenseShortName") or {}).get("value", ""))
        if not lic or (info.get("width") or 0) < 800 or info.get("mime", "image/jpeg") not in {"image/jpeg", "image/png"}:
            continue
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
        out.append({
            "id": f"commons-{pg['pageid']}", "title": pg.get("title", "").removeprefix("File:"),
            "url": info.get("thumburl") or info.get("url"), "width": info.get("width"), "height": info.get("height"),
            "license": lic[0], "license_version": lic[1], "creator": artist or None, "source": "wikimedia",
            "foreign_landing_url": info.get("descriptionurl"),
            "license_url": (meta.get("LicenseUrl") or {}).get("value", ""),
        })
        if len(out) >= n:
            break
    CACHE.mkdir(parents=True, exist_ok=True)
    for r in out:
        (CACHE / f"{r['id']}.json").write_text(json.dumps(r), encoding="utf-8")
    return out


def detail(image_id: str) -> dict:
    cached = CACHE / f"{image_id}.json"
    if cached.exists():  # a search already fetched it; spare the daily quota
        return json.loads(cached.read_text(encoding="utf-8"))
    resp = requests.get(f"{API}{image_id}/", headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def download(url: str) -> Image.Image:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def contact_sheet(results: list[dict], path: Path, cols: int = 4, cell: tuple[int, int] = (320, 200)) -> None:
    rows = (len(results) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell[0], rows * cell[1]), "white")
    draw = ImageDraw.Draw(sheet)
    for i, r in enumerate(results):
        try:
            im = download(r["url"])  # not the API thumbnail: that counts against the anon quota
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}] thumbnail failed: {exc}", file=sys.stderr)
            continue
        im.thumbnail((cell[0] - 8, cell[1] - 28))
        x, y = (i % cols) * cell[0] + 4, (i // cols) * cell[1] + 4
        sheet.paste(im, (x, y))
        draw.rectangle([x, y + cell[1] - 26, x + 40, y + cell[1] - 6], fill="black")
        draw.text((x + 6, y + cell[1] - 24), str(i), fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def crop_hero(im: Image.Image) -> Image.Image:
    w, h = im.size
    target = HERO_W / HERO_H
    out_w = min(HERO_W, w)
    out_h = round(out_w / target)
    if w / h > target:
        nw = int(h * target)
        left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target)
        top = (h - nh) // 2
        im = im.crop((0, top, w, top + nh))
    return im.resize((out_w, out_h), Image.LANCZOS)


def credit_fields(r: dict) -> dict:
    lic = LICENSE_LABEL.get(r["license"], r["license"].upper())
    ver = r.get("license_version") or ""
    lic_full = f"{lic} {ver}".strip() if r["license"] in {"by", "by-sa"} else lic
    creator = (r.get("creator") or "Unknown photographer").strip()
    source = {"flickr": "Flickr", "wikimedia": "Wikimedia Commons"}.get(r.get("source"), r.get("source") or "Openverse")
    return {
        "hero_credit": f"Photo: {creator} via {source} ({lic_full})",
        "hero_credit_url": r.get("foreign_landing_url") or r.get("creator_url") or "",
        "hero_license_url": r.get("license_url") or "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--n", type=int, default=8)
    s.add_argument("--sheet", type=Path)
    s.add_argument("--source", choices=["openverse", "commons"], default="openverse")
    f = sub.add_parser("fetch")
    f.add_argument("image_id")
    f.add_argument("--slug", required=True)
    f.add_argument("--name", help="file stem; defaults to <slug>-hero")
    args = ap.parse_args()

    if args.cmd == "search":
        results = (search_commons if args.source == "commons" else search)(args.query, args.n)
        for i, r in enumerate(results):
            print(f"[{i}] {r['id']} | {r.get('title') or '-'} | {r.get('creator') or '-'} | "
                  f"{r['license']} {r.get('license_version') or ''} | {r.get('source')} | "
                  f"{r.get('width')}x{r.get('height')}")
        if args.sheet and results:
            contact_sheet(results, args.sheet)
            print(f"sheet: {args.sheet}")
        return 0

    r = detail(args.image_id)
    if r.get("license") not in ALLOWED_LICENSES:
        print(f"refusing: license {r.get('license')} not allowed")
        return 1
    im = crop_hero(download(r["url"]))
    stem = args.name or f"{args.slug}-hero"
    out = IMAGES_DIR / f"{stem}.jpg"
    im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    fields = credit_fields(r)
    print(f"saved {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    print(f"hero_image: /images/{stem}.jpg")
    for k, v in fields.items():
        print(f"{k}: {json.dumps(v)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
