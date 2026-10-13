#!/usr/bin/env python3
"""Run the quality gate's deterministic checks on a post without any API call.

Same checks generate_post.py / enrich_post.py apply before the critic: thin
content, placeholder links, banned filler, and — when the post has a research
dossier in data/research/<slug>.json — that every outbound link is a dossier
source or a registry URL and that "## Sources" cites enough of them. Also
checks the dossier's shape and any inline SVG the post references.

Used when posts are rewritten outside the API pipeline (e.g. in a Claude Code
session), and handy before merging any hand edit.

Usage:
    python generator/check_post.py furnace-filter-basics [more slugs...]
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET

import generate_post as gp
import research
from build_site import parse_frontmatter

IMG_RE = re.compile(r"!\[[^\]]*\]\(/images/([^)\s]+)\)")


def dossier_issues(dossier: dict, cfg: dict) -> list[str]:
    issues = []
    rcfg = cfg["generation"].get("research", {})
    for key in ("direct_answer", "consensus", "gaps", "evidence", "sources"):
        if not dossier.get(key):
            issues.append(f"dossier: missing or empty '{key}'")
    sources = {research.normalize_url(u) for u in dossier.get("sources") or {}}
    for e in dossier.get("evidence") or []:
        if research.normalize_url(str(e.get("source_url", ""))) not in sources:
            issues.append(f"dossier: evidence source not in 'sources': {e.get('source_url')}")
    if len(dossier.get("evidence") or []) < rcfg.get("min_evidence", 6):
        issues.append(f"dossier: fewer than {rcfg.get('min_evidence', 6)} evidence items")
    if len(sources) < rcfg.get("min_distinct_sources", 4):
        issues.append(f"dossier: fewer than {rcfg.get('min_distinct_sources', 4)} distinct sources")
    return issues


def svg_issues(name: str) -> list[str]:
    path = gp.IMAGES_DIR / name
    if not path.exists():
        return [f"image /images/{name} does not exist"]
    text = path.read_text(encoding="utf-8")
    issues = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return [f"image {name}: not valid XML ({exc})"]
    if root.get("viewBox") != "0 0 1200 630":
        issues.append(f"image {name}: viewBox must be '0 0 1200 630'")
    if gp.sanitize_svg(text) != text.strip()[text.strip().find("<svg"):]:
        issues.append(f"image {name}: contains script/foreignObject/event handlers/external hrefs")
    return issues


def check(slug: str, cfg: dict, live_urls: set[str]) -> list[str]:
    matches = list(gp.POSTS_DIR.glob(f"*-{slug}.md"))
    if not matches:
        return [f"no post file for slug {slug}"]
    fm, body = parse_frontmatter(matches[0])
    dossier_path = gp.RESEARCH_DIR / f"{slug}.json"
    dossier = json.loads(dossier_path.read_text(encoding="utf-8")) if dossier_path.exists() else None
    issues = []
    if dossier is None:
        issues.append(f"no dossier at data/research/{slug}.json")
    else:
        issues += dossier_issues(dossier, cfg)
    issues += gp.programmatic_checks(cfg, body, live_urls, dossier)
    for name in IMG_RE.findall(body):
        issues += svg_issues(name)
    for key in ("title", "slug", "date", "description", "pillar", "hero_image"):
        if not fm.get(key):
            issues.append(f"frontmatter: missing '{key}'")
    if not 100 <= len(str(fm.get("description", ""))) <= 170:
        issues.append("frontmatter: description should be 100-170 characters")
    labels_path = gp.ROOT / "config" / "labels.yml"
    if labels_path.exists():
        taxonomy = gp.load_yaml(labels_path)["labels"]
        allowed = {label for labels in taxonomy.values() for label in labels}
        tags = list(fm.get("tags") or [])
        if not 1 <= len(tags) <= 4:
            issues.append("frontmatter: tags must list 1-4 labels from config/labels.yml")
        for tag in tags:
            if tag not in allowed:
                issues.append(f"frontmatter: tag '{tag}' is not in config/labels.yml")
    return issues


def main() -> int:
    cfg = gp.load_yaml(gp.SITE_CONFIG)
    topics = gp.load_yaml(gp.TOPICS_CONFIG)["topics"]
    live_urls = {t["blogger_url"] for t in topics if t.get("blogger_url")}
    failed = 0
    for slug in sys.argv[1:]:
        issues = check(slug, cfg, live_urls)
        if issues:
            failed += 1
            print(f"FAIL {slug}")
            for i in issues:
                print(f"  - {i}")
        else:
            print(f"PASS {slug}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
