#!/usr/bin/env python3
"""Generate one (or more) blog posts with Claude and save them to content/posts.

Usage:
    ANTHROPIC_API_KEY=... python generator/generate_post.py
    python generator/generate_post.py --dry-run   # no API calls, uses canned fixtures

The script:
  1. Picks the next pending topic, rotating across pillars so no single
     category dominates (anti-drift).
  2. Asks Claude to write the article (strict editorial system prompt).
  3. Asks Claude to draw 1-2 flat SVG illustrations for the post.
  4. Writes the Markdown file + SVG assets, marks the topic as published.
  5. If the pending queue is low, asks Claude to refill it — but only with
     topics inside the fixed pillars, so the niche never drifts.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))

import prompts  # noqa: E402

SITE_CONFIG = ROOT / "config" / "site.yml"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"
POSTS_DIR = ROOT / "content" / "posts"
IMAGES_DIR = ROOT / "content" / "images"


# ── helpers ──────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-{2,}", "-", text).strip("-")[:80]


def sanitize_svg(svg: str) -> str:
    """Strip anything executable or external from a generated SVG."""
    match = re.search(r"<svg[\s\S]*</svg>", svg)
    if not match:
        raise ValueError("No <svg> element found in model output")
    svg = match.group(0)
    svg = re.sub(r"<script[\s\S]*?</script>", "", svg, flags=re.I)
    svg = re.sub(r"<foreignObject[\s\S]*?</foreignObject>", "", svg, flags=re.I)
    svg = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", svg, flags=re.I)
    svg = re.sub(r"\son\w+\s*=\s*'[^']*'", "", svg, flags=re.I)
    svg = re.sub(r"\s(?:xlink:)?href\s*=\s*\"(?!#)[^\"]*\"", "", svg, flags=re.I)
    return svg


def parse_article(raw: str) -> tuple[dict, str]:
    """Parse the ===META=== / ===BODY=== / ===END=== response format."""
    meta_m = re.search(r"===META===\s*([\s\S]*?)\s*===BODY===", raw)
    body_m = re.search(r"===BODY===\s*([\s\S]*?)\s*===END===", raw)
    if not meta_m or not body_m:
        raise ValueError("Model response missing META/BODY delimiters")
    meta = json.loads(meta_m.group(1))
    return meta, body_m.group(1).strip()


# ── topic selection (anti-drift rotation) ────────────────────────────────────

def pick_next_topic(topics_data: dict) -> dict | None:
    """Pick the pending topic from the pillar with the fewest published posts,
    so coverage stays balanced across the fixed pillars."""
    published_counts = {p["slug"]: 0 for p in topics_data["pillars"]}
    for t in topics_data["topics"]:
        if t["status"] == "published":
            published_counts[t["pillar"]] = published_counts.get(t["pillar"], 0) + 1

    pending = [t for t in topics_data["topics"] if t["status"] == "pending"]
    if not pending:
        return None
    pending.sort(key=lambda t: published_counts.get(t["pillar"], 0))
    return pending[0]


# ── Claude calls ─────────────────────────────────────────────────────────────

def call_claude(client, model: str, system: str, user: str, max_tokens: int = 8000) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def generate_article(client, cfg: dict, topic: dict, pillar: dict, published_titles: list[str]) -> tuple[dict, str]:
    user = prompts.ARTICLE_USER.format(
        title=topic["title"],
        pillar_name=pillar["name"],
        pillar_description=pillar["description"],
        target_words=cfg["generation"].get("target_words", 1400),
        published_titles="\n".join(f"- {t}" for t in published_titles) or "- (none yet)",
    )
    raw = call_claude(client, cfg["generation"]["model"], prompts.ARTICLE_SYSTEM, user)
    return parse_article(raw)


def generate_svg(client, cfg: dict, brief: str, title: str) -> str:
    user = prompts.SVG_USER.format(brief=brief, title=title)
    raw = call_claude(client, cfg["generation"]["model"], prompts.SVG_SYSTEM, user, max_tokens=6000)
    return sanitize_svg(raw)


def refill_topics(client, cfg: dict, topics_data: dict) -> int:
    pending = [t for t in topics_data["topics"] if t["status"] == "pending"]
    threshold = cfg["generation"].get("refill_threshold", 5)
    if len(pending) >= threshold:
        return 0

    pillars_block = "\n".join(
        f"- {p['slug']}: {p['name']} — {p['description']}" for p in topics_data["pillars"]
    )
    existing = "\n".join(f"- {t['title']}" for t in topics_data["topics"])
    user = prompts.REFILL_USER.format(
        count=cfg["generation"].get("refill_count", 10),
        pillars_block=pillars_block,
        existing_titles=existing,
    )
    raw = call_claude(client, cfg["generation"]["model"], prompts.REFILL_SYSTEM, user, max_tokens=2000)
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        print("WARN: refill response had no JSON array; skipping refill")
        return 0
    new_topics = json.loads(match.group(0))

    valid_slugs = {p["slug"] for p in topics_data["pillars"]}
    existing_titles = {t["title"].lower() for t in topics_data["topics"]}
    added = 0
    for nt in new_topics:
        if nt.get("pillar") in valid_slugs and nt.get("title", "").lower() not in existing_titles:
            topics_data["topics"].append(
                {"title": nt["title"], "pillar": nt["pillar"], "status": "pending"}
            )
            added += 1
    return added


# ── dry-run fixtures (for testing without an API key) ───────────────────────

DRY_META = {
    "title": "Dry Run: A Sample Generated Post",
    "slug": "dry-run-sample-post",
    "meta_description": "A locally generated sample post used to verify the pipeline works end to end without calling the Claude API.",
    "tags": ["sample", "pipeline"],
    "hero_image_brief": "a cozy house with a wrench",
    "inline_image_brief": None,
}
DRY_BODY = (
    "This is a **dry-run** article used to test the generation pipeline.\n\n"
    "## It has a heading\n\nAnd a short paragraph under it.\n\n"
    "- A list item\n- Another list item\n"
)
DRY_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">'
    '<rect width="1200" height="630" fill="#F6EFE6"/>'
    '<circle cx="600" cy="315" r="180" fill="#B85C38"/>'
    '<rect x="480" y="330" width="240" height="140" rx="12" fill="#5C6E58"/>'
    "</svg>"
)


# ── main ─────────────────────────────────────────────────────────────────────

def write_post(meta: dict, body: str, topic: dict, hero_svg: str, inline_svg: str | None) -> Path:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    slug = slugify(meta.get("slug") or meta["title"])
    date = datetime.date.today().isoformat()

    hero_name = f"{slug}-hero.svg"
    (IMAGES_DIR / hero_name).write_text(hero_svg, encoding="utf-8")

    if inline_svg:
        inline_name = f"{slug}-inline.svg"
        (IMAGES_DIR / inline_name).write_text(inline_svg, encoding="utf-8")
        body = body.replace(
            "[INLINE_IMAGE]",
            f"![Illustration](/images/{inline_name})",
        )
    else:
        body = body.replace("[INLINE_IMAGE]", "")

    frontmatter = {
        "title": meta["title"],
        "slug": slug,
        "date": date,
        "description": meta["meta_description"],
        "tags": meta.get("tags", []),
        "pillar": topic["pillar"],
        "hero_image": f"/images/{hero_name}",
    }
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    out = POSTS_DIR / f"{date}-{slug}.md"
    out.write_text(f"---\n{fm}\n---\n\n{body}\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Skip API calls; use fixtures")
    args = ap.parse_args()

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    client = None
    if not args.dry_run:
        from anthropic import Anthropic

        client = Anthropic()  # uses ANTHROPIC_API_KEY

    n_posts = 1 if args.dry_run else cfg["generation"].get("posts_per_run", 1)
    generated: list[Path] = []

    for _ in range(n_posts):
        topic = pick_next_topic(topics_data)
        if topic is None:
            print("No pending topics left; refill will run below.")
            break
        pillar = pillars[topic["pillar"]]
        published_titles = [
            t["title"] for t in topics_data["topics"] if t["status"] == "published"
        ]
        print(f"Generating: {topic['title']}  [{pillar['name']}]")

        if args.dry_run:
            meta, body = dict(DRY_META), DRY_BODY
            hero_svg, inline_svg = DRY_SVG, None
        else:
            meta, body = generate_article(client, cfg, topic, pillar, published_titles)
            hero_svg = generate_svg(client, cfg, meta["hero_image_brief"], meta["title"])
            inline_svg = None
            if meta.get("inline_image_brief") and "[INLINE_IMAGE]" in body:
                inline_svg = generate_svg(client, cfg, meta["inline_image_brief"], meta["title"])

        out = write_post(meta, body, topic, hero_svg, inline_svg)
        generated.append(out)
        print(f"  -> {out.relative_to(ROOT)}")

        topic["status"] = "published"
        topic["published_slug"] = slugify(meta.get("slug") or meta["title"])

    if not args.dry_run and client is not None:
        added = refill_topics(client, cfg, topics_data)
        if added:
            print(f"Refilled topic queue with {added} new on-niche topics.")

    if not args.dry_run:
        save_yaml(TOPICS_CONFIG, topics_data)

    if not generated:
        print("Nothing generated.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
