"""Build concept HTML pages from markdown notes.

Usage:
    python scripts/build_concepts.py
    python scripts/build_concepts.py --watch   # rebuild on change (optional)

Inputs:
    docs/concepts/*.md         — concept notes (frontmatter + body)
    docs/_layouts/concept.html — page template (Jinja2)
    docs/_layouts/index.html   — index template (Jinja2)

Output:
    docs/build/<slug>.html
    docs/build/index.html
"""
from __future__ import annotations

import argparse
import html
import re
import shlex
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import markdown as md_lib
    import yaml
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as e:
    sys.stderr.write(
        f"missing dep: {e.name}\n"
        "install:  pip install markdown jinja2 pyyaml\n"
    )
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "concepts"
LAYOUTS = ROOT / "docs" / "_layouts"
OUT = ROOT / "docs" / "build"

LEVEL_CLASS = {
    "입문": "beginner", "beginner": "beginner",
    "중급": "intermediate", "intermediate": "intermediate",
    "심화": "advanced", "advanced": "advanced",
}

BLOCK_RE = re.compile(
    r"^:::(?P<kind>\w+)(?P<args>[^\n]*)\n(?P<body>.*?)\n:::\s*$",
    re.MULTILINE | re.DOTALL,
)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
HEAD_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Concept:
    path: Path
    slug: str
    title: str
    category: str
    level: str
    order: int
    summary: str
    prerequisites: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    updated: str = ""
    body_md: str = ""

    @property
    def level_class(self) -> str:
        return LEVEL_CLASS.get(self.level, "beginner")


def parse_attrs(s: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in ATTR_RE.finditer(s)}


def slugify_heading(text: str) -> str:
    # numbered prefixes like "1 · " stripped, spaces -> dashes
    text = re.sub(r"^\d+\s*[·\-.]\s*", "", text).strip().lower()
    text = re.sub(r"[^\w\s\-가-힣]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text or "section"


def render_block(kind: str, args: str, inner_html: str) -> str:
    """Convert a :::block::: into final HTML. inner_html is already markdown-rendered."""
    attrs = parse_attrs(args)
    if kind == "definition":
        term = html.escape(attrs.get("term", "정의"))
        name = html.escape(attrs.get("name", ""))
        return (
            f'<div class="definition">'
            f'<div class="term">{term}</div>'
            f'<div class="name">{name}</div>'
            f"{inner_html}"
            f"</div>"
        )
    if kind == "analogy":
        title = html.escape(attrs.get("title", "비유"))
        return (
            f'<div class="analogy">'
            f"<h4>비유 — {title}</h4>"
            f"{inner_html}"
            f"</div>"
        )
    if kind == "callout":
        # variant is the first bare token in args (e.g., warn, ok, danger)
        bare = next((t for t in shlex.split(args) if "=" not in t), "")
        cls = "callout " + bare if bare else "callout"
        title = html.escape(attrs.get("title", ""))
        head = f"<h4>{title}</h4>" if title else ""
        return f'<div class="{cls}">{head}{inner_html}</div>'
    if kind == "qa":
        q = html.escape(attrs.get("q", "Q"))
        return (
            f'<div class="qa">'
            f'<div class="q">{q}</div>'
            f'<div class="a">{inner_html}</div>'
            f"</div>"
        )
    # fallback: render unknown block as plain div with class
    return f'<div class="block-{kind}">{inner_html}</div>'


def render_body(md_text: str, md: md_lib.Markdown) -> str:
    """Render markdown body, expanding :::custom::: blocks."""

    # Use placeholder substitution so block inner markdown is rendered cleanly.
    placeholders: dict[str, str] = {}

    def stash(match: re.Match) -> str:
        kind = match.group("kind")
        args = match.group("args")
        body = match.group("body").strip("\n")
        inner_html = md.reset().convert(body)
        token = f"@@BLOCK_{len(placeholders)}@@"
        placeholders[token] = render_block(kind, args, inner_html)
        return token

    stashed = BLOCK_RE.sub(stash, md_text)
    rendered = md.reset().convert(stashed)
    for token, html_block in placeholders.items():
        rendered = rendered.replace(f"<p>{token}</p>", html_block).replace(token, html_block)

    # add ids to h2 (matches sidebar TOC)
    def add_id(match: re.Match) -> str:
        text = match.group(1)
        return f'<h2 id="{slugify_heading(text)}">{text}</h2>'

    rendered = re.sub(r"<h2>(.*?)</h2>", add_id, rendered, flags=re.DOTALL)
    return rendered


def extract_toc(md_text: str) -> list[dict[str, str]]:
    out = []
    for m in HEAD_RE.finditer(md_text):
        text = m.group(1).strip()
        out.append({"id": slugify_heading(text), "text": text})
    return out


def load_concept(path: Path) -> Concept | None:
    if path.name.startswith("_"):
        return None
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        sys.stderr.write(f"skip (no frontmatter): {path.name}\n")
        return None
    _, fm, body = raw.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    return Concept(
        path=path,
        slug=meta.get("slug") or path.stem,
        title=meta.get("title", path.stem),
        category=meta.get("category", "기타"),
        level=meta.get("level", "입문"),
        order=int(meta.get("order", 100)),
        summary=meta.get("summary", ""),
        prerequisites=list(meta.get("prerequisites") or []),
        related=list(meta.get("related") or []),
        updated=str(meta.get("updated") or ""),
        body_md=body.lstrip("\n"),
    )


def resolve_links(slugs: list[str], by_slug: dict[str, Concept]) -> list[dict[str, str]]:
    out = []
    for s in slugs:
        c = by_slug.get(s)
        if c:
            out.append({"slug": c.slug, "title": c.title})
        else:
            out.append({"slug": s, "title": s})
    return out


def build():
    if not SRC.exists():
        sys.stderr.write(f"no source dir: {SRC}\n")
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(LAYOUTS)),
        autoescape=select_autoescape(["html"]),
    )
    concept_tpl = env.get_template("concept.html")
    index_tpl = env.get_template("index.html")
    md = md_lib.Markdown(extensions=["tables", "fenced_code", "sane_lists"])

    concepts: list[Concept] = []
    for p in sorted(SRC.glob("*.md")):
        c = load_concept(p)
        if c:
            concepts.append(c)

    by_slug = {c.slug: c for c in concepts}
    concepts.sort(key=lambda c: (c.category, c.order, c.title))

    # prev/next inside each category
    cat_buckets: dict[str, list[Concept]] = {}
    for c in concepts:
        cat_buckets.setdefault(c.category, []).append(c)

    written = []
    for cat, items in cat_buckets.items():
        for i, c in enumerate(items):
            prev_c = items[i - 1] if i > 0 else None
            next_c = items[i + 1] if i + 1 < len(items) else None
            body_html = render_body(c.body_md, md)
            ctx = {
                "title": c.title,
                "category": c.category,
                "level": c.level,
                "level_class": c.level_class,
                "summary": c.summary,
                "updated": c.updated,
                "prerequisites": resolve_links(c.prerequisites, by_slug),
                "related": resolve_links(c.related, by_slug),
                "toc": extract_toc(c.body_md),
                "body": body_html,
                "prev": {"slug": prev_c.slug, "title": prev_c.title} if prev_c else None,
                "next": {"slug": next_c.slug, "title": next_c.title} if next_c else None,
            }
            out_path = OUT / f"{c.slug}.html"
            out_path.write_text(concept_tpl.render(**ctx), encoding="utf-8")
            written.append(out_path.relative_to(ROOT))

    # index
    index_ctx_categories = []
    for cat, items in sorted(cat_buckets.items()):
        cards = [
            {
                "slug": c.slug,
                "title": c.title,
                "category": c.category,
                "level": c.level,
                "level_class": c.level_class,
                "summary": c.summary,
            }
            for c in items
        ]
        index_ctx_categories.append((cat, cards))
    (OUT / "index.html").write_text(
        index_tpl.render(categories=index_ctx_categories), encoding="utf-8"
    )
    written.append((OUT / "index.html").relative_to(ROOT))

    print(f"built {len(written)} files at {datetime.now():%H:%M:%S}")
    for w in written:
        print(f"  · {w}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="rebuild on file change")
    args = parser.parse_args()
    build()
    if args.watch:
        import time
        last = {p: p.stat().st_mtime for p in SRC.glob("*.md")}
        last.update({p: p.stat().st_mtime for p in LAYOUTS.glob("*.html")})
        print("watching for changes... (Ctrl-C to stop)")
        while True:
            time.sleep(1)
            changed = False
            cur = {p: p.stat().st_mtime for p in SRC.glob("*.md")}
            cur.update({p: p.stat().st_mtime for p in LAYOUTS.glob("*.html")})
            if cur != last:
                changed = True
                last = cur
            if changed:
                try:
                    build()
                except Exception as e:
                    print(f"build error: {e}")


if __name__ == "__main__":
    main()
