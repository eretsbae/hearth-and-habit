#!/usr/bin/env python3
"""Generate Pinterest-ready pin images (1000x1500) for published posts.

Why this exists: the blog's hero art is a 1200x630 landscape SVG — the wrong
shape for Pinterest, which ranks 2:3 vertical images and expects readable
title text baked into the image. Pinterest is the fastest early traffic
channel for a home-and-living site because it does not care about domain
authority, and each pin is also a real crawlable inbound link — which is
exactly what this site lacks (Search Console: "Discovered - currently not
indexed").

Pins are rendered with Pillow only (no SVG rasterizer, no network), so this
runs identically on a laptop and on the Actions runner.

Usage:
    python generator/make_pin.py --all         # (re)render pins for every post
    python generator/make_pin.py --manifest    # rebuild content/pins/PINS.md
    python generator/make_pin.py --post content/posts/2026-07-27-foo.md
"""

from __future__ import annotations

import argparse
import io
import textwrap
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

try:  # rasterizes the post's hero illustration into the pin
    import cairosvg
except Exception:  # missing system cairo — fall back to the drawn motif
    cairosvg = None

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "content" / "posts"
PINS_DIR = ROOT / "content" / "pins"
IMAGES_DIR = ROOT / "content" / "images"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"

W, H = 1000, 1500

CREAM = "#F6EFE6"
CARD = "#FFFDF9"
TERRACOTTA = "#B85C38"
SAGE = "#5C6E58"
GOLD = "#D9A441"
CLAY = "#E4C7B2"
INK = "#2E2A24"

SERIF_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]
SANS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
SANS_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def fit_title(draw: ImageDraw.ImageDraw, title: str, max_w: int, max_h: int) -> tuple:
    """Largest serif size at which the title wraps inside the text box."""
    for size in range(74, 33, -2):
        font = load_font(SERIF_BOLD, size)
        # rough chars-per-line estimate, then verify precisely
        avg = draw.textlength("n", font=font) or 1
        wrapped = textwrap.wrap(title, width=max(12, int(max_w / avg)))
        if not wrapped or len(wrapped) > 6:
            continue
        line_h = int(size * 1.28)
        if max(draw.textlength(l, font=font) for l in wrapped) <= max_w and \
                len(wrapped) * line_h <= max_h:
            return font, wrapped, line_h
    font = load_font(SERIF_BOLD, 34)
    return font, textwrap.wrap(title, width=30)[:7], 44


ART_H = 560  # height of the illustration band at the top of the pin

# Chip color per pillar. Identical pins are a Pinterest liability — the feed
# rewards visually distinct ("fresh") images and its vision models use the
# artwork to categorize a pin — so the hero illustration below carries the
# real differentiation and this just reinforces it.
CHIP_COLORS = {
    "home-maintenance": TERRACOTTA,
    "cleaning-organization": SAGE,
    "energy-savings": "#A8752B",
    "kitchen-habits": "#9C4F30",
    "yard-outdoor": "#4A5A47",
}


def draw_motif(d: ImageDraw.ImageDraw) -> None:
    """Fallback art when the post has no hero SVG (or cairo is unavailable):
    an abstract roof/home motif in brand colors."""
    d.rectangle([0, 0, W, ART_H], fill=SAGE)
    d.polygon([(500, 150), (720, 380), (280, 380)], fill=CREAM)
    d.rectangle([380, 380, 620, 470], fill=CLAY)
    d.ellipse([110, 170, 230, 290], fill=GOLD)
    d.ellipse([800, 200, 900, 300], fill=TERRACOTTA)
    for i, x in enumerate(range(50, W, 150)):
        d.rectangle([x, 520 - (i % 3) * 10, x + 80, ART_H], fill="#4A5A47")


def hero_band(slug: str) -> Image.Image | None:
    """The post's own hero SVG, rasterized and cropped to the art band.

    Each post already has a unique Claude-drawn illustration; reusing it here
    is what makes every pin a distinct image instead of one template with
    swapped text.
    """
    svg = IMAGES_DIR / f"{slug}-hero.svg"
    if cairosvg is None or not svg.exists():
        return None
    try:
        # Render ~25% taller than the band, then crop back into it. The hero
        # SVGs carry generous negative space at the top; trimming it lets the
        # actual subject fill the thumbnail, which is what stops a scroll.
        png = cairosvg.svg2png(url=str(svg), output_height=int(ART_H * 1.25))
        art = Image.open(io.BytesIO(png)).convert("RGB")
    except Exception as e:
        print(f"  WARN: could not rasterize {svg.name} ({e}); using fallback motif")
        return None
    if art.width < W:
        art = art.resize((W, int(art.height * W / art.width)), Image.LANCZOS)
    left = max(0, (art.width - W) // 2)
    # Bias the vertical crop downward: these compositions put the subject in
    # the lower-middle and sky/wall in the upper third.
    top = int(max(0, art.height - ART_H) * 0.62)
    return art.crop((left, top, left + W, top + ART_H))


def render_pin(title: str, pillar_name: str, out_path: Path,
               slug: str = "", pillar_slug: str = "") -> None:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    art = hero_band(slug) if slug else None
    if art is not None:
        img.paste(art, (0, 0))
    else:
        draw_motif(d)

    # Title card overlaps the artwork slightly so the two read as one layout.
    card_top, card_bottom = ART_H - 40, 1290
    d.rounded_rectangle([56, card_top, W - 56, card_bottom], radius=28,
                        fill=CARD, outline=CLAY, width=3)

    # category chip
    chip_font = load_font(SANS_BOLD, 26)
    label = pillar_name.upper()
    tw = d.textlength(label, font=chip_font)
    d.rounded_rectangle([(W - tw) / 2 - 26, card_top + 44, (W + tw) / 2 + 26, card_top + 102],
                        radius=29, fill=CHIP_COLORS.get(pillar_slug, TERRACOTTA))
    d.text((W / 2, card_top + 73), label, font=chip_font, fill=CREAM, anchor="mm")

    # Title box stops well clear of the gold rule at card_bottom-150, so even a
    # six-line title can't collide with the wordmark block below it.
    box_top, box_bottom = card_top + 150, card_bottom - 190
    box_w, box_h = W - 200, box_bottom - box_top
    font, lines, line_h = fit_title(d, title, box_w, box_h)
    block_h = len(lines) * line_h
    y = box_top + max(0, (box_h - block_h) // 2)
    for line in lines:
        d.text((W / 2, y), line, font=font, fill=INK, anchor="ma")
        y += line_h

    # rule + wordmark inside the card
    d.rectangle([W / 2 - 70, card_bottom - 148, W / 2 + 70, card_bottom - 144], fill=GOLD)
    d.text((W / 2, card_bottom - 108), "HEARTH & HABIT",
           font=load_font(SANS_BOLD, 30), fill=SAGE, anchor="ma")
    d.text((W / 2, card_bottom - 64), "peterpb.blogspot.com",
           font=load_font(SANS, 24), fill="#8A8078", anchor="ma")

    # footer band
    d.rectangle([0, H - 160, W, H], fill=TERRACOTTA)
    d.text((W / 2, H - 80), "Practical home care, made simple.",
           font=load_font(SANS, 30), fill=CREAM, anchor="mm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, optimize=True)


def parse_front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, fm, _ = text.split("---", 2)
    return yaml.safe_load(fm) or {}


def pillar_names() -> dict:
    data = yaml.safe_load(TOPICS_CONFIG.read_text(encoding="utf-8"))
    return {p["slug"]: p["name"] for p in data["pillars"]}


def pin_for_post(path: Path, names: dict) -> Path | None:
    fm = parse_front(path)
    if not fm.get("title"):
        return None
    slug = fm.get("slug") or path.stem[11:]
    out = PINS_DIR / f"{slug}.png"
    render_pin(fm["title"], names.get(fm.get("pillar"), "Home & Living"), out,
               slug=slug, pillar_slug=fm.get("pillar", ""))
    return out


def build_manifest() -> int:
    """A copy-paste-ready pin queue: image, description, destination URL."""
    data = yaml.safe_load(TOPICS_CONFIG.read_text(encoding="utf-8"))
    by_slug = {t.get("published_slug"): t for t in data["topics"] if t.get("published_slug")}
    names = pillar_names()

    rows = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        fm = parse_front(path)
        slug = fm.get("slug") or path.stem[11:]
        topic = by_slug.get(slug)
        if not topic or not topic.get("blogger_url"):
            continue
        pin = PINS_DIR / f"{slug}.png"
        if not pin.exists():
            continue
        rows.append({
            "slug": slug,
            "title": fm["title"],
            "desc": (fm.get("description") or "").strip(),
            "pillar": names.get(fm.get("pillar"), ""),
            "url": topic["blogger_url"],
            "date": str(fm.get("date", "")),
            "auto_pinned": bool(topic.get("pinterest_pin_id")),
        })

    # Group by board: pinning is done board by board, so a date-ordered list
    # makes the manual pass jump around between boards for every item.
    by_board: dict[str, list[dict]] = {}
    for r in rows:
        by_board.setdefault(r["pillar"] or "기타", []).append(r)

    auto_done = sum(1 for r in rows if r["auto_pinned"])
    lines = [
        "# Pinterest 핀 큐",
        "",
        "이 파일은 자동 생성됩니다 (`generator/make_pin.py --manifest`). 수동 편집해도 다음 실행 때 덮어써집니다.",
        "",
        f"핀 {len(rows)}개 준비됨 · API 자동 게시 완료 {auto_done}개",
        "",
        "## 수동으로 올리는 법",
        "",
        "1. **이미지 위치**: 로컬 리포의 `content/pins/` 폴더 (최신화: `git pull`).",
        "   Windows 탐색기에서 그 폴더를 열어두고 작업하면 편합니다.",
        "2. **보드 먼저 생성** — 아래 소제목과 **똑같은 이름**으로 만드세요. 이름이 같아야",
        "   나중에 API 자동 게시가 켜졌을 때 기존 보드를 그대로 씁니다(중복 생성 방지).",
        "   보드는 반드시 **공개(비공개 해제)** 상태여야 검색에 노출됩니다.",
        "3. **핀 만들기**: Pinterest → 만들기 → 핀 만들기 → 이미지 끌어다 놓기 →",
        "   제목·설명·링크 붙여넣기 → 보드 선택 → 게시.",
        "4. **하루 3~5개씩** 나눠 올리세요. 신규 계정이 한 번에 몰아 올리면 스팸으로 취급됩니다.",
        "",
        "`[x]`로 표시된 항목은 API가 이미 자동 게시한 것이니 **수동으로 다시 올리지 마세요.**",
        "",
        "---",
        "",
    ]
    for board in sorted(by_board):
        items = by_board[board]
        lines += [f"## 보드: {board}", "", f"({len(items)}개)", ""]
        for r in items:
            mark = "x" if r["auto_pinned"] else " "
            lines += [
                f"- [{mark}] **{r['title']}**",
                f"  - 이미지: `content/pins/{r['slug']}.png`",
                f"  - 링크: {r['url']}",
                f"  - 설명: {r['desc']}",
                "",
            ]
    PINS_DIR.mkdir(parents=True, exist_ok=True)
    (PINS_DIR / "PINS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"manifest: {len(rows)} pins -> content/pins/PINS.md")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Render pins for every post")
    ap.add_argument("--post", help="Render a pin for one post markdown file")
    ap.add_argument("--manifest", action="store_true", help="Rebuild PINS.md only")
    args = ap.parse_args()

    if args.manifest and not (args.all or args.post):
        return build_manifest()

    names = pillar_names()
    if args.post:
        out = pin_for_post(Path(args.post), names)
        print(f"pin: {out}")
    elif args.all:
        made = 0
        for path in sorted(POSTS_DIR.glob("*.md")):
            if pin_for_post(path, names):
                made += 1
        print(f"rendered {made} pins")
    else:
        ap.error("pass --all, --post PATH, or --manifest")
    return build_manifest()


if __name__ == "__main__":
    raise SystemExit(main())
