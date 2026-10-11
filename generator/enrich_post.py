#!/usr/bin/env python3
"""Rebuild already-published posts on a researched evidence base.

The 61 posts corrected on 2026-09-29 are accurate but mostly restate what every
other result says, which is what AdSense keeps rejecting as "low value". This
runs the same research stage as new posts (generator/research.py) on a live
post, rewrites it to deliver what the research found that typical articles
miss, and puts the result through the same quality gate. URL, slug, date and
hero image stay. The inline diagram is redrawn from the new text under the
same file name (the old pipe-freeze chart contradicted the corrected article),
the title may be tightened, and the post gets `updated` / `enriched` dates.

Nothing goes live from here: the changed Markdown reaches Blogger only when it
is merged to main by a person (sync-posts.yml).

Usage:
    python generator/enrich_post.py --slugs furnace-filter-basics
    python generator/enrich_post.py --next 3            # oldest not-yet-enriched posts
    python generator/enrich_post.py --next 1 --preview _preview   # write elsewhere
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path

import yaml

import generate_post as gp
import prompts
import research
from build_site import parse_frontmatter

IMAGE_LINE_RE = re.compile(r"^!\[[^\]]*\]\(/images/([^)\s]+)\)\s*$", re.M)


def post_files() -> list[Path]:
    return sorted(gp.POSTS_DIR.glob("*.md"))


def pick_posts(slugs: list[str] | None, n: int) -> list[Path]:
    files = post_files()
    if slugs:
        by_slug = {parse_frontmatter(f)[0].get("slug"): f for f in files}
        missing = [s for s in slugs if s not in by_slug]
        if missing:
            raise SystemExit(f"Unknown slug(s): {', '.join(missing)}")
        return [by_slug[s] for s in slugs]
    todo = [f for f in files if not parse_frontmatter(f)[0].get("enriched")]
    return todo[:n]  # file names start with the publish date: oldest first


def enrich_one(client, cfg: dict, topics_data: dict, path: Path, out_dir: Path | None) -> dict:
    fm, body = parse_frontmatter(path)
    slug = fm["slug"]
    pillars = {p["slug"]: p for p in topics_data["pillars"]}
    pillar = pillars[fm["pillar"]]
    print(f"Enriching: {fm['title']}  [{pillar['name']}]")

    dossier = research.run_research(client, cfg, fm["title"], pillar, existing_body=body)

    old_images = IMAGE_LINE_RE.findall(body)
    # Other posts only: a post must not be told to link to itself.
    self_url = next((t.get("blogger_url") for t in topics_data["topics"]
                     if t.get("published_slug") == slug), None)
    listing = "\n".join(l for l in gp.published_list(topics_data).splitlines()
                        if not (self_url and self_url in l))
    user = prompts.ENRICH_USER.format(
        title=fm["title"],
        pillar_name=pillar["name"],
        pillar_description=pillar["description"],
        published_titles=listing,
        facts_block=gp.facts_block(),
        dossier_block=research.dossier_block(dossier),
        body=body,
    )
    raw = gp.call_claude(client, cfg["generation"]["model"], prompts.ARTICLE_SYSTEM, user, effort="high")
    meta, new_body = gp.parse_article(raw)
    title = (meta.get("title") or "").strip() or fm["title"]

    published_titles = [t["title"] for t in topics_data["topics"]
                        if t.get("status") == "published" and t.get("published_slug") != slug]
    live_urls = {t["blogger_url"] for t in topics_data["topics"] if t.get("blogger_url")}
    new_body, passed, score, issues = gp.enforce_quality_gate(
        client, cfg, {"title": title}, new_body, pillar, published_titles, live_urls, dossier
    )
    result = {"slug": slug, "title": title, "old_title": fm["title"], "score": score, "passed": passed,
              "sources": len(dossier.get("sources") or {}), "issues": issues[:5]}
    if not passed and out_dir is None:
        print(f"  NOT CHANGED (quality gate failed, score={score}): {'; '.join(issues[:2])}")
        return result

    # Same file name as the old diagram, so the live post's image URL holds.
    images_dir = gp.IMAGES_DIR if out_dir is None else out_dir / "images"
    inline_name = old_images[0] if old_images else f"{slug}-inline.svg"
    if meta.get("inline_image_brief") and "[INLINE_IMAGE]" in new_body:
        svg = gp.generate_svg(client, cfg, meta["inline_image_brief"], title, diagram=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / inline_name).write_text(svg, encoding="utf-8")
        alt = gp.clean_alt(meta.get("inline_alt") or meta["inline_image_brief"])
        new_body = new_body.replace("[INLINE_IMAGE]", f"![{alt}](/images/{inline_name})", 1)
    new_body = new_body.replace("[INLINE_IMAGE]", "").strip()

    today = datetime.date.today().isoformat()
    fm["title"] = title
    desc = (meta.get("meta_description") or "").strip()
    if 100 <= len(desc) <= 170:
        fm["description"] = desc
    fm["updated"] = today
    fm["enriched"] = today
    text = f"---\n{yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()}\n---\n\n{new_body}\n"
    if out_dir is None:
        path.write_text(text, encoding="utf-8")
        gp.save_dossier(dossier, slug)
        print(f"  -> {path.relative_to(gp.ROOT)} (score={score}, sources={result['sources']})")
    else:
        (out_dir / "posts").mkdir(parents=True, exist_ok=True)
        (out_dir / "posts" / path.name).write_text(text, encoding="utf-8")
        gp.save_dossier(dossier, slug, out_dir / "research")
        print(f"  -> preview {path.name} (score={score}, passed={passed})")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*", help="Posts to enrich, by slug")
    ap.add_argument("--next", type=int, default=1, help="Without --slugs: this many oldest un-enriched posts")
    ap.add_argument("--preview", metavar="DIR", help="Write results into DIR instead of content/")
    ap.add_argument("--report", metavar="FILE", help="Write a JSON summary of the run here")
    args = ap.parse_args()

    from anthropic import Anthropic

    cfg = gp.load_yaml(gp.SITE_CONFIG)
    topics_data = gp.load_yaml(gp.TOPICS_CONFIG)
    client = Anthropic()
    out_dir = Path(args.preview) if args.preview else None

    results = []
    for path in pick_posts(args.slugs, args.next):
        try:
            results.append(enrich_one(client, cfg, topics_data, path, out_dir))
        except research.InsufficientEvidence as exc:
            print(f"  NOT CHANGED: {exc}")
            results.append({"slug": path.stem, "passed": False, "issues": [str(exc)]})
        except Exception as exc:  # API hiccup or malformed response: skip this post only
            print(f"  NOT CHANGED (error): {exc}")
            results.append({"slug": path.stem, "passed": False, "issues": [f"error: {exc}"]})

    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    changed = [r for r in results if r.get("passed")]
    print(f"Done: {len(changed)}/{len(results)} post(s) passed the gate.")
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
