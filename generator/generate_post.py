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
import research  # noqa: E402

SITE_CONFIG = ROOT / "config" / "site.yml"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"
FACTS_CONFIG = ROOT / "config" / "facts.yml"
POSTS_DIR = ROOT / "content" / "posts"
IMAGES_DIR = ROOT / "content" / "images"
RESEARCH_DIR = ROOT / "data" / "research"


# ── helpers ──────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)


def facts_block() -> str:
    """config/facts.yml rendered for the prompts: one line per fact + source."""
    if not FACTS_CONFIG.exists():
        return "- (none)"
    facts = (load_yaml(FACTS_CONFIG) or {}).get("facts", [])
    return "\n".join(f"- {f['fact']} Source: {f['source']}" for f in facts) or "- (none)"


def published_list(topics_data: dict) -> str:
    """Published posts as "- Title — URL" so the writer can link them for real
    (given titles only, it wrote "[Title](#)" placeholders that went live)."""
    lines = []
    for t in topics_data["topics"]:
        if t.get("status") != "published":
            continue
        url = t.get("blogger_url")
        lines.append(f"- {t['title']} — {url}" if url else f"- {t['title']}")
    return "\n".join(lines) or "- (none yet)"


def clean_alt(text: str, limit: int = 140) -> str:
    """Alt text trimmed on a word boundary. The old hard [:125] cut produced
    alts ending mid-word ("...on a concrete", "...risin") on 49 posts."""
    text = re.sub(r'[\[\]()"<>]', "", text or "").strip()
    text = re.sub(r"^(a |an )?(simple )?flat (editorial )?(illustration|diagram) (of|showing) ", "", text, flags=re.I)
    text = text[:1].upper() + text[1:]
    if len(text) <= limit:
        return text.rstrip(" .,;")
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-—")


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
    """Parse the ===META=== / ===BODY=== response format.

    ===END=== is treated as optional: in production, Claude reliably writes
    ===META=== and ===BODY=== but frequently omits the trailing ===END===
    marker once it's naturally done (stop_reason="end_turn", not truncation)
    — confirmed by diagnostics on real runs where all three markers were
    checked directly. Requiring it caused every real article to be rejected.
    Everything after ===BODY=== is the body; an ===END=== marker, if present
    anywhere after it, is stripped as a trailing sentinel rather than required.

    Tolerates the model wrapping its whole answer in a markdown code fence
    (```...```), which otherwise leaves the delimiters intact but can trip up
    a naive strip() elsewhere; re.search finds them regardless of wrapping.
    """
    text = raw.strip()
    fence_m = re.match(r"^```[a-zA-Z]*\n([\s\S]*)\n```$", text)
    if fence_m:
        text = fence_m.group(1)

    meta_m = re.search(r"===META===\s*([\s\S]*?)\s*===BODY===", text)
    if not meta_m:
        markers = {m: (m in text) for m in ("===META===", "===BODY===", "===END===")}
        head = text[:400].replace("\n", " ")
        tail = text[-400:].replace("\n", " ")
        raise ValueError(
            "Model response missing META/BODY delimiters. "
            f"length={len(text)} markers_found={markers}\n"
            f"HEAD: {head!r}\nTAIL: {tail!r}"
        )
    body_text = text[meta_m.end():]
    end_m = re.search(r"===END===\s*$", body_text)
    if end_m:
        body_text = body_text[:end_m.start()]
    body_text = body_text.strip()
    if not body_text:
        raise ValueError("Model response had an empty body after ===BODY===")
    meta = json.loads(meta_m.group(1))
    return meta, body_text


# ── quality gate: keep the site from reading as "scaled content abuse" ──────
#
# Google doesn't penalize AI authorship; it penalizes mass-produced content
# that's thin, templated, or adds no real value. Two independent checks run
# before anything is published: fast free regex checks, and an independent
# Claude "editor" pass scoring usefulness/originality/concreteness/accuracy/
# structure. If either flags issues, one revision round is attempted; if it
# still fails, the topic is parked as "needs_review" instead of being
# published, and the run moves on to the next topic.

FILLER_PHRASES = [
    "in today's fast-paced world",
    "in today's world",
    "in conclusion",
    "it is important to note",
    "as an ai",
    "as a language model",
    "in this blog post",
    "in this article we",
]


PLACEHOLDER_LINK_RE = re.compile(r"\]\((#|/)\)")
BRACKET_TITLE_RE = re.compile(r"(?<!!)\[([A-Z][^\]]{6,120})\](?!\()")
SITE_LINK_RE = re.compile(r"\]\((https?://(?:www\.)?hearth-habit\.com/[^)\s]+)\)")
SAFETY_TOPIC_RE = re.compile(
    r"\b(bleach|leftover|refreez|thaw|food poisoning|mold|mould|carbon monoxide|"
    r"breaker|gas leak|smoke alarm|smoke detector|water heater)\b", re.I)
TIC_LIMITS = {"genuinely": 1, "key takeaway": 1, "the good news": 1, "rule of thumb": 1}


MD_LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")


def registry_urls() -> set[str]:
    if not FACTS_CONFIG.exists():
        return set()
    facts = (load_yaml(FACTS_CONFIG) or {}).get("facts", [])
    return {research.normalize_url(f["source"]) for f in facts if f.get("source")}


def source_checks(cfg: dict, body: str, dossier: dict) -> list[str]:
    """A researched article may link outside the site only to pages the
    research stage actually retrieved, or to registry pages. This is what
    stops a confident-looking but invented citation from going live."""
    allowed = {research.normalize_url(u) for u in dossier.get("sources") or {}} | registry_urls()
    issues = []
    for url in MD_LINK_RE.findall(body):
        if re.match(r"https?://(?:www\.)?hearth-habit\.com/", url):
            continue
        if research.normalize_url(url) not in allowed:
            issues.append(f"Links to {url}, which is not one of the dossier's citable sources or a registry URL; remove it or use a listed source.")
    m = re.search(r"^## Sources\s*$([\s\S]*)", body, flags=re.M)
    cited = {research.normalize_url(u) for u in MD_LINK_RE.findall(m.group(1))} & allowed if m else set()
    min_sources = cfg["generation"].get("research", {}).get("min_sources", 3)
    if len(cited) < min_sources:
        issues.append(f'"## Sources" cites {len(cited)} allowed source(s); cite at least {min_sources} that the article actually relies on.')
    return issues


def programmatic_checks(
    cfg: dict, body: str, live_urls: set[str] | None = None, dossier: dict | None = None
) -> list[str]:
    """Fast, free, deterministic checks — run before spending an API call."""
    issues = []
    if dossier is not None:
        issues += source_checks(cfg, body, dossier)
    if PLACEHOLDER_LINK_RE.search(body):
        issues.append('Contains a placeholder link "(#)" or "(/)"; link the real post URL or remove the link.')
    for m in BRACKET_TITLE_RE.finditer(body):
        if m.group(1) != "INLINE_IMAGE":
            issues.append(f'"[{m.group(1)}]" looks like a post title in brackets without a URL; link it or rewrite.')
            break
    if live_urls is not None:
        for url in SITE_LINK_RE.findall(body):
            if url not in live_urls:
                issues.append(f"Links to {url}, which is not a live post URL on this site.")
    if SAFETY_TOPIC_RE.search(body) and "## Sources" not in body:
        issues.append('Safety-sensitive topic without a "## Sources" section citing registry URLs.')
    word_count = len(re.findall(r"\w+", body))
    min_words = cfg["generation"].get("quality_gate", {}).get("min_words", 700)
    if word_count < min_words:
        issues.append(f"Article is too thin ({word_count} words, minimum {min_words}); expand with concrete detail.")
    if len(re.findall(r"^##\s", body, flags=re.M)) < 2:
        issues.append("Fewer than 2 H2 sections; add clearer structure.")
    if re.search(r"\b\d{1,3}\.\d%", body):
        issues.append("Contains a suspiciously precise decimal statistic (e.g. '37.4%') — round to an honest range or remove it.")
    lowered = body.lower()
    for phrase in FILLER_PHRASES:
        if phrase in lowered:
            issues.append(f'Contains a banned filler/self-referential phrase: "{phrase}".')
    for phrase, limit in TIC_LIMITS.items():
        n = lowered.count(phrase)
        if n > limit:
            issues.append(f'Uses the site\'s overused phrase "{phrase}" {n} times; keep it to {limit} or fewer.')
    return issues


def quality_review(
    client, cfg: dict, meta: dict, body: str, pillar: dict, published_titles: list[str], dossier: dict
) -> dict:
    user = prompts.QUALITY_USER.format(
        title=meta["title"],
        pillar_name=pillar["name"],
        recent_titles="\n".join(f"- {t}" for t in published_titles) or "- (none yet)",
        facts_block=facts_block(),
        dossier_block=research.dossier_block(dossier),
        body=body,
    )
    gcfg = cfg["generation"]
    raw = call_claude(
        client, gcfg.get("critic_model") or gcfg["model"], prompts.QUALITY_SYSTEM, user,
        max_tokens=16000, effort="high",
    )
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {"score": 0, "pass": False, "issues": ["Quality reviewer returned no parseable JSON."]}
    try:
        verdict = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"score": 0, "pass": False, "issues": ["Quality reviewer returned invalid JSON."]}
    verdict.setdefault("issues", [])
    return verdict


def revise_article(client, cfg: dict, body: str, issues: list[str], dossier: dict) -> str:
    user = prompts.REVISE_USER.format(
        issues_block="\n".join(f"- {i}" for i in issues),
        dossier_block=research.dossier_block(dossier),
        facts_block=facts_block(),
        body=body,
    )
    revised = call_claude(client, cfg["generation"]["model"], prompts.REVISE_SYSTEM, user, effort="high")
    return revised.strip()


def enforce_quality_gate(
    client, cfg: dict, meta: dict, body: str, pillar: dict, published_titles: list[str],
    live_urls: set[str] | None = None, dossier: dict | None = None,
) -> tuple[str, bool, int | None, list[str]]:
    """Returns (possibly-revised body, passed, last_score, remaining_issues).

    Programmatic checks (thin content, fabricated-looking stats, banned
    phrases) are objective and always block. The critic's numeric score is
    the other hard gate — trusted over its own "pass" boolean, since in
    production the model has returned an internally inconsistent verdict
    (e.g. score=82 with pass=false) despite the prompt asking it to keep
    them in sync; a numeric threshold is a more reliable control signal than
    trusting the model to always self-report consistently. The critic's
    free-text "issues" are advisory once the score clears the bar — real
    editors ship pieces with a couple of minor notes; requiring the issues
    list to be literally empty on top of a passing score rejected every
    real article in production.
    """
    qcfg = cfg["generation"].get("quality_gate", {})
    if not qcfg.get("enabled", True):
        return body, True, None, []

    max_rounds = qcfg.get("max_revision_rounds", 2)
    min_score = qcfg.get("min_score", 75)

    score = None
    issues: list[str] = []
    for attempt in range(max_rounds + 1):
        prog_issues = programmatic_checks(cfg, body, live_urls, dossier)
        verdict = quality_review(client, cfg, meta, body, pillar, published_titles, dossier or {})
        score = verdict.get("score")
        crit_issues = [i for i in verdict.get("issues", []) if i]
        issues = prog_issues + crit_issues
        critic_ok = (score >= min_score) if score is not None else bool(verdict.get("pass"))
        passed = not prog_issues and critic_ok

        if passed:
            return body, True, score, crit_issues

        if attempt == max_rounds:
            return body, False, score, issues

        print(f"  quality gate: attempt {attempt + 1} failed (score={score}); revising...")
        for i in issues[:6]:
            print(f"    - {i[:200]}")
        body = revise_article(client, cfg, body, issues, dossier or {})

    return body, False, score, issues


# ── topic selection (anti-drift rotation) ────────────────────────────────────

def season_priority(topic: dict, today: datetime.date | None = None) -> int:
    """0 = in season window (publish now, ahead of peak search demand),
    1 = non-seasonal (anytime), 2 = out of season (hold until its window).

    A topic opts in with `season_months: [9, 10]` in topics.yml. The window is
    treated as "current or next month", so seasonal guides go live 4+ weeks
    before readers start searching for them.
    """
    months = topic.get("season_months")
    if not months:
        return 1
    today = today or datetime.date.today()
    window = {today.month, today.month % 12 + 1}
    return 0 if window & set(months) else 2


def pick_next_topic(topics_data: dict, today: datetime.date | None = None) -> dict | None:
    """Pick the pending topic from the pillar with the fewest published posts,
    so coverage stays balanced across the fixed pillars. Within that balance,
    in-season topics jump the queue and out-of-season ones wait."""
    published_counts = {p["slug"]: 0 for p in topics_data["pillars"]}
    for t in topics_data["topics"]:
        if t["status"] == "published":
            published_counts[t["pillar"]] = published_counts.get(t["pillar"], 0) + 1

    pending = [t for t in topics_data["topics"] if t["status"] == "pending"]
    if not pending:
        return None
    pending.sort(
        key=lambda t: (season_priority(t, today), published_counts.get(t["pillar"], 0))
    )
    return pending[0]


# ── Claude calls ─────────────────────────────────────────────────────────────

def call_claude(
    client, model: str, system: str, user: str, max_tokens: int = 32000, effort: str = "medium"
) -> str:
    # Thinking stays on (Claude Opus 5.5 rejects disabling it); depth is set by
    # effort instead. Thinking tokens count against max_tokens, which is why
    # the budget is far above the ~3K-word article itself — an earlier 12K
    # budget truncated drafts before the closing delimiter. Streaming keeps a
    # long request under the SDK's HTTP timeout.
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        resp = stream.get_final_message()
    if resp.stop_reason == "max_tokens":
        raise ValueError(
            f"Response truncated at max_tokens={max_tokens} (stop_reason=max_tokens). "
            "Increase max_tokens for this call."
        )
    if resp.stop_reason == "refusal":
        raise ValueError(f"Model declined the request: {resp.stop_details}")
    text = "".join(b.text for b in resp.content if b.type == "text")
    print(f"    [call_claude] model={model} effort={effort} stop_reason={resp.stop_reason} chars={len(text)}")
    return text


def pick_angle(published_count: int) -> str:
    _, instruction = prompts.CONTENT_ANGLES[published_count % len(prompts.CONTENT_ANGLES)]
    return instruction


def generate_article(
    client, cfg: dict, topic: dict, pillar: dict, published_listing: str, angle_instruction: str,
    dossier: dict,
) -> tuple[dict, str]:
    user = prompts.ARTICLE_USER.format(
        title=topic["title"],
        pillar_name=pillar["name"],
        pillar_description=pillar["description"],
        target_words=cfg["generation"].get("target_words", 1400),
        angle_instruction=angle_instruction,
        published_titles=published_listing,
        facts_block=facts_block(),
        dossier_block=research.dossier_block(dossier),
    )
    raw = call_claude(client, cfg["generation"]["model"], prompts.ARTICLE_SYSTEM, user, effort="high")
    return parse_article(raw)


def generate_svg(client, cfg: dict, brief: str, title: str, diagram: bool = False) -> str:
    """Hero art is decorative (no text). The inline image is an explanatory
    diagram with short labels: decorative inline art taught readers nothing
    and several were unreadable (a mushroom ring that looked like a spider)."""
    user = prompts.SVG_USER.format(brief=brief, title=title)
    system = prompts.SVG_DIAGRAM_SYSTEM if diagram else prompts.SVG_SYSTEM
    raw = call_claude(client, cfg["generation"]["model"], system, user, max_tokens=16000, effort="low")
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
    raw = call_claude(client, cfg["generation"]["model"], prompts.REFILL_SYSTEM, user, max_tokens=16000)
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
            entry = {"title": nt["title"], "pillar": nt["pillar"], "status": "pending"}
            months = [m for m in nt.get("season_months") or [] if isinstance(m, int) and 1 <= m <= 12]
            if months:
                entry["season_months"] = months
            topics_data["topics"].append(entry)
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

def save_dossier(dossier: dict, slug: str, research_dir: Path = RESEARCH_DIR) -> Path:
    """Kept next to the post so any claim can be traced to what research found."""
    research_dir.mkdir(parents=True, exist_ok=True)
    out = research_dir / f"{slug}.json"
    out.write_text(json.dumps(dossier, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def write_post(
    meta: dict, body: str, topic: dict, hero_svg: str, inline_svg: str | None,
    posts_dir: Path = POSTS_DIR, images_dir: Path = IMAGES_DIR,
) -> Path:
    posts_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(meta.get("slug") or meta["title"])
    date = datetime.date.today().isoformat()

    hero_name = f"{slug}-hero.svg"
    (images_dir / hero_name).write_text(hero_svg, encoding="utf-8")

    # Image alt text: the writer's dedicated alt fields, falling back to the
    # art-direction briefs. Descriptive alt is an image-SEO and accessibility
    # signal we get for free.
    hero_alt = clean_alt(meta.get("hero_alt") or meta.get("hero_image_brief") or meta["title"])
    inline_alt = clean_alt(meta.get("inline_alt") or meta.get("inline_image_brief") or meta["title"])

    if inline_svg:
        inline_name = f"{slug}-inline.svg"
        (images_dir / inline_name).write_text(inline_svg, encoding="utf-8")
        body = body.replace(
            "[INLINE_IMAGE]",
            f"![{inline_alt}](/images/{inline_name})",
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
        "hero_alt": hero_alt,
    }
    hooks = [h.strip() for h in meta.get("pin_hooks") or [] if isinstance(h, str) and h.strip()]
    if hooks:
        frontmatter["pin_hooks"] = hooks[:2]
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    out = posts_dir / f"{date}-{slug}.md"
    out.write_text(f"---\n{fm}\n---\n\n{body}\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Skip API calls; use fixtures")
    ap.add_argument("--preview", metavar="DIR",
                    help="Generate the next topic into DIR only; leave content/ and topics.yml untouched")
    args = ap.parse_args()
    preview = Path(args.preview) if args.preview else None

    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = {p["slug"]: p for p in topics_data["pillars"]}

    client = None
    if not args.dry_run:
        from anthropic import Anthropic

        client = Anthropic()  # uses ANTHROPIC_API_KEY

    n_posts = 1 if (args.dry_run or preview) else cfg["generation"].get("posts_per_run", 1)
    extra_attempts = cfg["generation"].get("quality_gate", {}).get("max_topic_attempts_extra", 3)
    max_attempts = n_posts + extra_attempts
    generated: list[Path] = []
    attempts = 0

    while len(generated) < n_posts and attempts < max_attempts:
        topic = pick_next_topic(topics_data)
        if topic is None:
            print("No pending topics left; refill will run below.")
            break
        attempts += 1
        pillar = pillars[topic["pillar"]]
        published_titles = [
            t["title"] for t in topics_data["topics"] if t.get("status") == "published"
        ]
        print(f"Generating: {topic['title']}  [{pillar['name']}]  (attempt {attempts}/{max_attempts})")

        if args.dry_run:
            meta, body = dict(DRY_META), DRY_BODY
            hero_svg, inline_svg = DRY_SVG, None
            score: int | None = None
        else:
            try:
                angle_instruction = pick_angle(len(published_titles))
                live_urls = {t["blogger_url"] for t in topics_data["topics"] if t.get("blogger_url")}
                dossier = research.run_research(client, cfg, topic["title"], pillar)
                meta, body = generate_article(
                    client, cfg, topic, pillar, published_list(topics_data), angle_instruction, dossier
                )
                body, passed, score, issues = enforce_quality_gate(
                    client, cfg, meta, body, pillar, published_titles, live_urls, dossier
                )
            except research.InsufficientEvidence as exc:
                topic["status"] = "needs_review"
                topic["quality_issues"] = [str(exc)]
                print(f"  SKIPPED (parked as needs_review): {exc}")
                continue
            except Exception as exc:  # malformed/unexpected model response, API hiccup, etc.
                # Leave the topic's status untouched (still "pending") so a future
                # scheduled run retries it automatically — this is a technical
                # generation failure, not a content-quality verdict, and it must
                # not take down the whole run (other topics may still succeed).
                print(f"  SKIPPED (generation error, will retry next run): {exc}")
                continue

            if not passed and preview:
                # Keep the failed draft so it can be inspected.
                (preview / "gate").mkdir(parents=True, exist_ok=True)
                (preview / "gate" / "failed-issues.json").write_text(
                    json.dumps({"score": score, "issues": issues}, indent=2), encoding="utf-8")
                print(f"  PREVIEW: quality gate failed (score={score}); writing the draft anyway")
            elif not passed:
                topic["status"] = "needs_review"
                topic["quality_score"] = score
                topic["quality_issues"] = issues[:5]
                print(f"  SKIPPED (quality gate failed, score={score}): {'; '.join(issues[:2]) or 'no details'}")
                continue

            try:
                hero_svg = generate_svg(client, cfg, meta["hero_image_brief"], meta["title"])
                inline_svg = None
                if meta.get("inline_image_brief") and "[INLINE_IMAGE]" in body:
                    inline_svg = generate_svg(
                        client, cfg, meta["inline_image_brief"], meta["title"], diagram=True
                    )
            except Exception as exc:
                print(f"  SKIPPED (image generation error, will retry next run): {exc}")
                continue

        if preview:
            out = write_post(meta, body, topic, hero_svg, inline_svg,
                             preview / "posts", preview / "images")
            if not args.dry_run:
                save_dossier(dossier, out.stem.split("-", 3)[-1], preview / "research")
            generated.append(out)
            print(f"  -> {out} (preview, score={score})")
            break
        out = write_post(meta, body, topic, hero_svg, inline_svg)
        if not args.dry_run:
            save_dossier(dossier, slugify(meta.get("slug") or meta["title"]))
        generated.append(out)
        print(f"  -> {out.relative_to(ROOT)}")

        topic["status"] = "published"
        topic["published_slug"] = slugify(meta.get("slug") or meta["title"])
        if not args.dry_run:
            topic["quality_score"] = score

    if not args.dry_run and client is not None and not preview:
        try:
            added = refill_topics(client, cfg, topics_data)
            if added:
                print(f"Refilled topic queue with {added} new on-niche topics.")
        except Exception as exc:
            print(f"WARN: topic refill failed, skipping this run: {exc}")

    if not args.dry_run and not preview:
        save_yaml(TOPICS_CONFIG, topics_data)

    if not generated:
        print("Nothing generated.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
