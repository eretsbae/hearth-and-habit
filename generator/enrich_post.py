#!/usr/bin/env python3
"""Rebuild already-published posts on a researched evidence base.

The 61 posts corrected on 2026-09-29 are accurate but mostly restate what every
other result says, which is what AdSense keeps rejecting as "low value". This
runs the same research stage as new posts (generator/research.py) on a live
post, rewrites it to deliver what the research found that typical articles
miss, and puts the result through the same quality gate. URL, title, slug,
date and images stay; the post gets `updated` / `enriched` dates.

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

IMAGE_LINE_RE = re.compile(r"^!\[[^\]]*\]\(/images/[^)]+\)\s*$", re.M)


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


def ensure_image(body: str, image_lines: list[str]) -> str:
    """Put back an inline diagram the rewrite dropped, before the 2nd section."""
    for line in image_lines:
        if line in body:
            continue
        heads = [m.start() for m in re.finditer(r"^## ", body, flags=re.M)]
        at = heads[1] if len(heads) > 1 else len(body)
        body = body[:at].rstrip() + f"\n\n{line}\n\n" + body[at:]
    return body


def enrich_one(client, cfg: dict, topics_data: dict, path: Path, out_dir: Path | None) -> dict:
    fm, body = parse_frontmatter(path)
    slug = fm["slug"]
    pillars = {p["slug"]: p for p in topics_data["pillars"]}
    pillar = pillars[fm["pillar"]]
    print(f"Enriching: {fm['title']}  [{pillar['name']}]")

    dossier = research.run_research(client, cfg, fm["title"], pillar, existing_body=body)

    image_lines = IMAGE_LINE_RE.findall(body)
    if image_lines:
        image_instruction = (
            f"this image line exactly once, unchanged, where it best fits: {image_lines[0].strip()}"
        )
    else:
        image_instruction = "no image lines (the hero image is added separately)."
    # Other posts only: a post must not be told to link to itself.
    self_url = next((t.get("blogger_url") for t in topics_data["topics"]
                     if t.get("published_slug") == slug), None)
    listing = "\n".join(l for l in gp.published_list(topics_data).splitlines()
                        if not (self_url and self_url in l))
    user = prompts.ENRICH_USER.format(
        title=fm["title"],
        pillar_name=pillar["name"],
        pillar_description=pillar["description"],
        image_instruction=image_instruction,
        published_titles=listing,
        facts_block=gp.facts_block(),
        dossier_block=research.dossier_block(dossier),
        body=body,
    )
    raw = gp.call_claude(client, cfg["generation"]["model"], prompts.ARTICLE_SYSTEM, user, effort="high")
    meta, new_body = gp.parse_article(raw)
    new_body = ensure_image(new_body, [l.strip() for l in image_lines])

    published_titles = [t["title"] for t in topics_data["topics"]
                        if t.get("status") == "published" and t.get("published_slug") != slug]
    live_urls = {t["blogger_url"] for t in topics_data["topics"] if t.get("blogger_url")}
    new_body, passed, score, issues = gp.enforce_quality_gate(
        client, cfg, {"title": fm["title"]}, new_body, pillar, published_titles, live_urls, dossier
    )
    new_body = ensure_image(new_body, [l.strip() for l in image_lines])
    result = {"slug": slug, "title": fm["title"], "score": score, "passed": passed,
              "sources": len(dossier.get("sources") or {}), "issues": issues[:5]}
    if not passed and out_dir is None:
        print(f"  NOT CHANGED (quality gate failed, score={score}): {'; '.join(issues[:2])}")
        return result

    today = datetime.date.today().isoformat()
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
