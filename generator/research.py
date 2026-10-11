"""Research stage: build a sourced dossier before anything is written.

AdSense rejected the site six times for "low value content". Writing from the
model's memory alone produced articles that restate what every other result
already says, with numbers nobody can trace (the frozen-pipes post cited an
ice-dam page for a 20°F threshold it never states). This stage searches and
reads real sources first, and everything downstream (writer, critic, link
check) is held to what it found.

The dossier's URLs are collected from the tool-result blocks the API returns,
not from the model's own text, so a URL the model invents can never pass as a
researched source.
"""

from __future__ import annotations

import json
import re

import prompts

MAX_CONTINUATIONS = 5


class InsufficientEvidence(ValueError):
    """Research ran but found too little traceable evidence to write from.
    A content verdict, not a transient error: retrying the same topic will
    not help, so the caller parks it instead."""


def research_tools(cfg: dict) -> list[dict]:
    rcfg = cfg["generation"].get("research", {})
    return [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": rcfg.get("max_searches", 8),
            "user_location": {"type": "approximate", "country": "US"},
        },
        {
            "type": "web_fetch_20260209",
            "name": "web_fetch",
            "max_uses": rcfg.get("max_fetches", 6),
            "max_content_tokens": rcfg.get("max_content_tokens", 20000),
        },
    ]


def normalize_url(url: str) -> str:
    """Matching key only: the model may drop "www." or a trailing slash when
    it copies a URL. Links keep the exact retrieved form."""
    url = url.strip().split("#", 1)[0].rstrip("/")
    m = re.match(r"(?i)^https?://(?:www\.)?([^/]+)(.*)$", url)
    return (m.group(1).lower() + m.group(2)) if m else url


def _collect_urls(node, found: dict[str, str]) -> None:
    """Every {url, title?} object nested anywhere in a tool-result block."""
    if isinstance(node, dict):
        url = node.get("url")
        if isinstance(url, str) and url.startswith("http"):
            found.setdefault(normalize_url(url), (url.split("#", 1)[0], node.get("title") or ""))
        for v in node.values():
            _collect_urls(v, found)
    elif isinstance(node, list):
        for v in node:
            _collect_urls(v, found)


def tool_result_urls(blocks) -> dict[str, tuple[str, str]]:
    """{matching key: (retrieved URL, title)}"""
    found: dict[str, tuple[str, str]] = {}
    for b in blocks:
        btype = getattr(b, "type", "")
        if btype.endswith("_tool_result"):
            _collect_urls(b.to_dict(), found)
    return found


def _final_text(blocks) -> str:
    return "".join(b.text for b in blocks if getattr(b, "type", "") == "text")


def parse_dossier(text: str) -> dict:
    m = re.search(r"===DOSSIER===\s*([\s\S]*?)\s*(?:===END===|$)", text)
    raw = m.group(1) if m else text
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("Research response had no JSON dossier")
    return json.loads(raw[start:end + 1])


def run_research(client, cfg: dict, title: str, pillar: dict, existing_body: str | None = None) -> dict:
    """Returns the dossier with "sources" = {url: title} actually retrieved,
    and evidence items whose source_url was not retrieved removed."""
    gcfg = cfg["generation"]
    rcfg = gcfg.get("research", {})
    model = rcfg.get("model") or gcfg["model"]
    if existing_body:
        existing = prompts.RESEARCH_EXISTING.format(body=existing_body)
    else:
        existing = ""
    user = prompts.RESEARCH_USER.format(
        title=title,
        pillar_name=pillar["name"],
        pillar_description=pillar["description"],
        existing_block=existing,
    )
    messages: list[dict] = [{"role": "user", "content": user}]
    all_blocks = []
    for _ in range(MAX_CONTINUATIONS):
        with client.messages.stream(
            model=model,
            max_tokens=32000,
            system=prompts.RESEARCH_SYSTEM,
            tools=research_tools(cfg),
            output_config={"effort": rcfg.get("effort", "high")},
            messages=messages,
        ) as stream:
            resp = stream.get_final_message()
        all_blocks.extend(resp.content)
        if resp.stop_reason == "refusal":
            raise ValueError(f"Research refused: {resp.stop_details}")
        if resp.stop_reason == "max_tokens":
            raise ValueError("Research truncated at max_tokens")
        if resp.stop_reason != "pause_turn":
            break
        # The server stopped its own tool loop mid-turn; send the turn back
        # unchanged and it resumes where it left off.
        messages.append({"role": "assistant", "content": resp.content})
    else:
        raise ValueError("Research still paused after max continuations")

    sources = tool_result_urls(all_blocks)
    print(f"    [research] model={model} retrieved_urls={len(sources)}")
    dossier = parse_dossier(_final_text(resp.content) or _final_text(all_blocks))

    kept, dropped = [], 0
    for item in dossier.get("evidence") or []:
        key = normalize_url(str(item.get("source_url") or ""))
        if key in sources:
            item["source_url"] = sources[key][0]
            kept.append(item)
        else:
            dropped += 1
    if dropped:
        print(f"    [research] dropped {dropped} evidence item(s) whose URL was never retrieved")
    dossier["evidence"] = kept
    dossier["sources"] = {}
    for e in kept:
        url, title = sources[normalize_url(e["source_url"])]
        dossier["sources"].setdefault(url, e.get("source_title") or title)
    min_ev = rcfg.get("min_evidence", 5)
    if len(kept) < min_ev:
        raise InsufficientEvidence(f"Research found only {len(kept)} traceable evidence items (need {min_ev})")
    return dossier


def dossier_block(dossier: dict) -> str:
    """The dossier as the writer/critic see it: compact, sources numbered."""
    lines = [f"Reader situation: {dossier.get('reader_situation', '')}",
             f"Direct answer: {dossier.get('direct_answer', '')}", ""]
    lines.append("What typical existing articles already say (do not just restate this):")
    lines += [f"- {c}" for c in dossier.get("consensus") or []]
    lines.append("")
    lines.append("Information gain — what those articles miss, blur, or get wrong (this article must deliver these):")
    lines += [f"- {g}" for g in dossier.get("gaps") or []]
    lines.append("")
    lines.append("Evidence (every specific number, threshold, spec, or cost in the article must come from here or the FACT REGISTRY):")
    for e in dossier.get("evidence") or []:
        lines.append(f"- {e.get('claim', '')} | {e.get('detail', '')} | source: {e['source_url']}")
    lines.append("")
    lines.append("Questions real people ask about this (answer the relevant ones in the body or FAQ):")
    lines += [f"- {q}" for q in dossier.get("real_questions") or []]
    asset = dossier.get("original_asset") or {}
    if asset:
        lines.append("")
        lines.append(f"Original asset to build ({asset.get('type', '')}): {asset.get('spec', '')}")
    cautions = dossier.get("cautions") or []
    if cautions:
        lines.append("")
        lines.append("Safety / code cautions:")
        lines += [f"- {c}" for c in cautions]
    lines.append("")
    lines.append("Citable sources (the ONLY non-registry URLs allowed in the article):")
    lines += [f"- {u} — {t}" for u, t in (dossier.get("sources") or {}).items()]
    return "\n".join(lines)
