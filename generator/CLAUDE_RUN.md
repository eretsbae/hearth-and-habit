# Scheduled post: instructions for the Claude Code session

You are the headless Claude Code session that `scripts/claude-publish.ps1` starts on Mon, Wed and
Fri evenings (KST). You research, write, verify and commit ONE new post for Hearth & Habit
(www.hearth-habit.com). GitHub Actions publishes it to Blogger later the same night. This replaced
the API pipeline (`generator/generate_post.py`) on 2026-10-11, when the API credit balance ran
out. Do not run `generate_post.py`, `enrich_post.py`, or anything else that calls the Anthropic API.

You start in a dedicated detached worktree (`.claude/worktrees/publish`) that was just reset to
`origin/main`. Work there, in the current directory, and never in the main checkout, where other
sessions may be editing. Change only these files:
- the new post
- its images
- its dossier
- `config/topics.yml`

`generator/claude_post.py` does the git work.

## The bar
AdSense rejected the site six times for "low value content". A post earns its place only if it
gives a reader specifics they won't get from the first search result, and if every specific traces
to a page you actually read. The 70 posts rewritten on 2026-10-11 meet this bar. Read one or two
before you write:
- `content/posts/2026-10-09-what-temperature-do-pipes-freeze-guide.md` with
  `data/research/what-temperature-do-pipes-freeze-guide.json`
- `content/posts/2026-06-29-furnace-filter-basics.md` with `data/research/furnace-filter-basics.json`

Editorial rules: follow `ARTICLE_SYSTEM` in `generator/prompts.py` exactly. The research method
and dossier shape are in `RESEARCH_SYSTEM` and `RESEARCH_USER`. The fact registry is
`config/facts.yml`: never contradict it, and you may cite its `source` URLs without fetching them.

## Steps

1. **Pick the topic.** Run
   `python generator/claude_post.py next`. It prints today's date, the topic (title, pillar), a
   structural angle to use, the target length, and the published posts with their URLs. Those URLs
   are the only internal links you may use.
   - If `refill_needed` is true, propose `refill_count` new topics. Follow the rules in
     `REFILL_SYSTEM` and `REFILL_USER` in `prompts.py`: specific long-tail questions inside the
     pillars, no duplicates, `season_months` where seasonal. Write them to a JSON file in your temp
     dir and run `python generator/claude_post.py add-topics <file>`.
   - If there is no topic, stop and report it.

2. **Research** with WebSearch and WebFetch:
   - Search the way a reader would and skim the top results. That is the consensus.
   - Find what those results miss, blur, or get wrong.
   - Check forum threads for the real questions people ask. Forums are never a source for facts.
   - WebFetch every page you will cite. A fact counts only if a page you fetched states it.
   - Source priority: government agencies, university extension services, standards and code
     bodies, insurer research, manufacturer manuals, and trade publications for cost ranges (say
     so).
   - Federal sites (FSIS, foodsafety.gov, parts of energy.gov) often block fetches. Use the
     registry value with its registry URL, or a state or extension page that states the same thing.
   - WebFetch often can't read PDFs. A small text-extraction script in your temp dir is fine.
   - Aim for 5–9 distinct authoritative pages and 6–15 evidence items.
   - If you can't reach 4 distinct sources and 6 evidence items, run
     `python generator/claude_post.py park --title "<title>" --reason "<why>"` and go back to step 1
     for the next topic. Try at most 2 topics, then stop and report.

3. **Write the dossier** to `data/research/<slug>.json`. Use the shape of the example dossiers:
   - fields: `reader_situation`, `direct_answer`, `consensus`, `gaps`, `evidence[]` (`claim`,
     `detail`, `source_url`, `source_title`), `real_questions`, `original_asset`, `cautions`,
     `sources` (an object mapping URL to title)
   - Every `evidence[].source_url` must also be in `sources`, and `sources` lists only URLs you
     fetched.
   - The slug is lowercase words joined with hyphens, at most 80 characters, unique among existing
     posts.

4. **Write the post** to `content/posts/<today>-<slug>.md`.
   - Frontmatter keys, in this order:
     - `title` (refine the topic wording if needed, but keep the intent)
     - `slug`
     - `date` (today, quoted)
     - `description` (150–160 characters)
     - `tags` (3–6)
     - `pillar` (the topic's pillar slug)
     - `hero_image: /images/<slug>-hero.svg`
     - `hero_alt` (max 140 characters)
     - `pin_hooks` (two Pinterest headlines, max 60 characters each, no unsupported number)
   - The body starts with the intro paragraph, with no title heading. The first sentence answers
     the question.
   - Follow the given angle. Spend most of the post on the dossier's gaps, and build its original
     asset (table, worked example with visible arithmetic, flow, or schedule).
   - Every number, threshold, spec, or cost must come from your evidence or the registry.
   - Attribute claims in plain words.
   - Include 2–4 internal links using exact URLs from step 1.
   - An FAQ is optional, as `## FAQ` with `### ` questions.
   - End with `## Sources`: 3–8 bullets in the form `- [Title](URL) — what it supports`, using only
     dossier sources or registry URLs. No other external links anywhere.

5. **Images.**
   - Hero: `content/images/<slug>-hero.svg`. Decorative, with no text. Follow `SVG_SYSTEM` in
     `prompts.py` for the palette, `viewBox="0 0 1200 630"`, and the full-canvas cream background.
   - Inline diagram (recommended): `content/images/<slug>-inline.svg`, following
     `SVG_DIAGRAM_SYSTEM`. It has 3–8 labels that state only what the article states. Place it in
     the body as `![alt](/images/<slug>-inline.svg)`.
   - No script, no external hrefs, no foreignObject.

6. **Independent verification.** Launch one subagent with fresh context. Tell it to check the post
   against the dossier and registry on these points and report each defect with the exact sentence:
   - every specific number or attributed claim is in the dossier evidence for that source, or in
     the registry
   - nothing contradicts `facts.yml`
   - the first sentence, tables, arithmetic, and FAQ agree, and table rows don't overlap
   - no unsafe procedure and no unsupported reassurance. Food safety is time and temperature.
   - each Sources bullet matches its dossier evidence

   Fix everything it reports by cutting or narrowing the text, never by inventing support. If a fix
   is substantial, verify again.

7. **Finalize.** Run
   `python generator/claude_post.py finalize --title "<exact topic title from step 1>" --slug <slug>`.
   It runs the same checks as `generator/check_post.py`, marks the topic published in
   `config/topics.yml`, commits only this post's files, and pushes to `main`. If it prints
   FINALIZE FAILED, fix the listed problems and run it again.

## Report
End with a short Korean summary of 5–8 lines covering:
- the topic and slug
- the number of distinct sources
- the main information gain
- defects the verifier found and how you fixed them
- the commit hash, or why nothing was committed

Make the last line exactly `RESULT: COMMITTED <slug>`, or `RESULT: NONE <reason>`.
