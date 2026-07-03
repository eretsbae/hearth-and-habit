#!/usr/bin/env python3
"""Build the static site from content/ into _site/.

No API calls — pure static site generation with Jinja2 + Markdown.

    python generator/build_site.py
"""

from __future__ import annotations

import datetime
import re
import shutil
import xml.sax.saxutils as sax
from pathlib import Path

import markdown
import yaml
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
SITE_CONFIG = ROOT / "config" / "site.yml"
TOPICS_CONFIG = ROOT / "config" / "topics.yml"
POSTS_DIR = ROOT / "content" / "posts"
PAGES_DIR = ROOT / "content" / "pages"
IMAGES_DIR = ROOT / "content" / "images"
STATIC_DIR = ROOT / "static"
OUT = ROOT / "_site"

MD_EXTENSIONS = ["extra", "smarty", "toc"]


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$", text)
    if not m:
        raise ValueError(f"{path}: missing frontmatter")
    return yaml.safe_load(m.group(1)), m.group(2).strip()


def md_to_html(text: str) -> str:
    return markdown.markdown(text, extensions=MD_EXTENSIONS)


def reading_time(text: str) -> int:
    words = len(re.findall(r"\w+", text))
    return max(1, round(words / 220))


def site_url(cfg: dict) -> str:
    domain = (cfg.get("custom_domain") or "").strip()
    if domain:
        return f"https://{domain}"
    return cfg.get("fallback_url", "").rstrip("/")


def build() -> None:
    cfg = load_yaml(SITE_CONFIG)
    topics_data = load_yaml(TOPICS_CONFIG)
    pillars = topics_data["pillars"]
    pillar_by_slug = {p["slug"]: p for p in pillars}
    base_url = site_url(cfg)

    # GitHub Pages 프로젝트 사이트(username.github.io/repo)에서는 모든 내부
    # 링크에 /repo 프리픽스가 필요하다. 커스텀 도메인이면 prefix는 빈 문자열.
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    prefix = parsed.path.rstrip("/")

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    env.globals.update(site=cfg, base_url=base_url, origin=origin, prefix=prefix,
                       pillars=pillars, current_year=datetime.date.today().year)

    # ── collect posts ──
    posts = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        fm, body = parse_frontmatter(path)
        html = md_to_html(body)
        if prefix:
            html = html.replace('src="/images/', f'src="{prefix}/images/')
            html = html.replace('href="/', f'href="{prefix}/')
        fm["html"] = html
        fm["reading_time"] = reading_time(body)
        fm["url"] = f"{prefix}/posts/{fm['slug']}/"
        fm["hero_image"] = f"{prefix}{fm['hero_image']}"
        fm["pillar_name"] = pillar_by_slug.get(fm.get("pillar"), {}).get("name", "")
        fm["pillar_url"] = f"{prefix}/topics/{fm.get('pillar')}/"
        posts.append(fm)
    posts.sort(key=lambda p: str(p["date"]), reverse=True)

    # ── reset output dir ──
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    def render(template: str, out_path: str, **ctx) -> None:
        html = env.get_template(template).render(**ctx)
        dest = OUT / out_path.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")

    # ── index ──
    render("index.html", "index.html", posts=posts,
           page_title=cfg["site_name"], page_description=cfg["tagline"],
           canonical=f"{base_url}/")

    # ── posts ──
    for i, post in enumerate(posts):
        related = [p for p in posts if p is not post and p.get("pillar") == post.get("pillar")][:3]
        render("post.html", f"posts/{post['slug']}/index.html",
               post=post, related=related,
               page_title=f"{post['title']} — {cfg['site_name']}",
               page_description=post.get("description", ""),
               canonical=f"{origin}{post['url']}")

    # ── pillar (category) pages ──
    for pillar in pillars:
        p_posts = [p for p in posts if p.get("pillar") == pillar["slug"]]
        render("pillar.html", f"topics/{pillar['slug']}/index.html",
               pillar=pillar, posts=p_posts,
               page_title=f"{pillar['name']} — {cfg['site_name']}",
               page_description=pillar["description"],
               canonical=f"{base_url}/topics/{pillar['slug']}/")

    # ── static pages (about, privacy, etc.) ──
    pages = []
    for path in sorted(PAGES_DIR.glob("*.md")):
        fm, body = parse_frontmatter(path)
        fm["html"] = md_to_html(body)
        fm["url"] = f"/{fm['slug']}/"
        pages.append(fm)
        render("page.html", f"{fm['slug']}/index.html",
               page=fm,
               page_title=f"{fm['title']} — {cfg['site_name']}",
               page_description=fm.get("description", ""),
               canonical=f"{base_url}/{fm['slug']}/")

    # ── copy assets ──
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUT / "static")
    if IMAGES_DIR.exists():
        shutil.copytree(IMAGES_DIR, OUT / "images")

    # ── robots.txt / sitemap.xml / rss.xml ──
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8"
    )

    urls = [f"{base_url}/"]
    urls += [f"{origin}{p['url']}" for p in posts]
    urls += [f"{base_url}/topics/{p['slug']}/" for p in pillars]
    urls += [f"{base_url}{pg['url']}" for pg in pages]
    sitemap_entries = "\n".join(
        f"  <url><loc>{sax.escape(u)}</loc></url>" for u in urls
    )
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{sitemap_entries}\n</urlset>\n",
        encoding="utf-8",
    )

    items = []
    for p in posts[:20]:
        items.append(
            "  <item>\n"
            f"    <title>{sax.escape(p['title'])}</title>\n"
            f"    <link>{origin}{p['url']}</link>\n"
            f"    <guid>{origin}{p['url']}</guid>\n"
            f"    <pubDate>{datetime.datetime.combine(datetime.date.fromisoformat(str(p['date'])), datetime.time(12, 0)).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>\n"
            f"    <description>{sax.escape(p.get('description', ''))}</description>\n"
            "  </item>"
        )
    (OUT / "rss.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>\n'
        f"  <title>{sax.escape(cfg['site_name'])}</title>\n"
        f"  <link>{base_url}/</link>\n"
        f"  <description>{sax.escape(cfg['tagline'])}</description>\n"
        f"  <language>{cfg.get('language', 'en')}</language>\n"
        + "\n".join(items)
        + "\n</channel></rss>\n",
        encoding="utf-8",
    )

    # ── AdSense ads.txt ──
    pub_id = (cfg.get("adsense") or {}).get("publisher_id", "").strip()
    if pub_id:
        ads_id = pub_id.replace("ca-pub-", "pub-")
        (OUT / "ads.txt").write_text(
            f"google.com, {ads_id}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8"
        )

    # ── custom domain ──
    domain = (cfg.get("custom_domain") or "").strip()
    if domain:
        (OUT / "CNAME").write_text(domain + "\n", encoding="utf-8")

    # ── .nojekyll (serve files as-is) ──
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Built {len(posts)} posts, {len(pages)} pages, {len(pillars)} pillar pages -> {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
