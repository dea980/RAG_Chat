"""Build night-shift HTML reports from per-terminal markdown logs.

Usage:
    python backend/scripts/build_night_report.py                # render all + dashboard
    python backend/scripts/build_night_report.py --terminal T2  # one terminal + dashboard

Inputs:
    docs/sessions/night/<Tn>.work.md       — work log (frontmatter + body)
    docs/sessions/night/<Tn>.learning.md   — beginner learning doc (frontmatter + body)
    docs/_layouts/night_*.html             — jinja2 templates

Output:
    docs/reports/night/<Tn>.html
    docs/reports/night/<Tn>-learning.html
    docs/reports/night/index.html          — merged dashboard
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import markdown as md_lib
    import yaml
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as e:  # pragma: no cover
    sys.stderr.write(
        f"missing dep: {e.name}\n"
        "install:  pip install markdown jinja2 pyyaml\n"
    )
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent          # backend/
SRC = ROOT / "docs" / "sessions" / "night"
LAYOUTS = ROOT / "docs" / "_layouts"
OUT = ROOT / "docs" / "reports" / "night"

STATUS_CLASS = {
    "done": "done", "active": "active",
    "blocked": "blocked", "planned": "planned",
}

WORK_RE = re.compile(r"^(?P<tn>T\d+)\.work\.md$")


@dataclass
class NightDoc:
    terminal: str
    title: str
    status: str
    mission: str
    updated: str
    body_md: str


def parse_doc(path: Path) -> NightDoc | None:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        sys.stderr.write(f"skip (no frontmatter): {path.name}\n")
        return None
    _, fm, body = raw.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    return NightDoc(
        terminal=str(meta.get("terminal", path.stem.split(".")[0])),
        title=meta.get("title", path.stem),
        status=str(meta.get("status", "active")),
        mission=meta.get("mission", ""),
        updated=str(meta.get("updated", "")),
        body_md=body.lstrip("\n"),
    )


def render_md(body_md: str, md: md_lib.Markdown) -> str:
    return md.reset().convert(body_md)


def discover(src: Path) -> list[str]:
    """Terminal ids (T1, T2, …) that have a .work.md file, sorted."""
    tns = []
    for p in sorted(src.glob("*.work.md")):
        m = WORK_RE.match(p.name)
        if m:
            tns.append(m.group("tn"))
    return tns


def build(src: Path = SRC, out: Path = OUT, layouts: Path = LAYOUTS,
          terminal: str | None = None) -> list[Path]:
    if not src.exists():
        sys.stderr.write(f"no source dir: {src}\n")
        return []
    out.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(layouts)),
        autoescape=select_autoescape(["html"]),
    )
    report_tpl = env.get_template("night_report.html")
    learning_tpl = env.get_template("night_learning.html")
    index_tpl = env.get_template("night_index.html")
    md = md_lib.Markdown(extensions=["tables", "fenced_code", "sane_lists"])

    written: list[Path] = []
    summaries: list[dict] = []

    # Always scan every terminal so the dashboard is complete,
    # even when --terminal limits which per-page files get rewritten.
    for tn in discover(src):
        doc = parse_doc(src / f"{tn}.work.md")
        if not doc:
            continue
        summaries.append({
            "terminal": tn,
            "title": doc.title,
            "status": doc.status,
            "status_class": STATUS_CLASS.get(doc.status, "active"),
            "mission": doc.mission,
            "updated": doc.updated,
            "report": f"{tn}.html",
            "learning": f"{tn}-learning.html",
        })
        if terminal and tn != terminal:
            continue

        # work report
        (out / f"{tn}.html").write_text(
            report_tpl.render(
                doc=doc,
                body=render_md(doc.body_md, md),
                status_class=STATUS_CLASS.get(doc.status, "active"),
            ),
            encoding="utf-8",
        )
        written.append(out / f"{tn}.html")

        # learning report (optional)
        learn = src / f"{tn}.learning.md"
        if learn.exists():
            ldoc = parse_doc(learn)
            if ldoc:
                (out / f"{tn}-learning.html").write_text(
                    learning_tpl.render(
                        doc=ldoc,
                        body=render_md(ldoc.body_md, md),
                        status_class=STATUS_CLASS.get(ldoc.status, "active"),
                    ),
                    encoding="utf-8",
                )
                written.append(out / f"{tn}-learning.html")

    # dashboard — always rebuilt
    (out / "index.html").write_text(
        index_tpl.render(summaries=summaries, built=f"{datetime.now():%Y-%m-%d %H:%M}"),
        encoding="utf-8",
    )
    written.append(out / "index.html")
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", help="render only this terminal (e.g. T2)")
    args = parser.parse_args()
    written = build(terminal=args.terminal)
    print(f"built {len(written)} files at {datetime.now():%H:%M:%S}")
    for w in written:
        print(f"  · {w}")


if __name__ == "__main__":
    main()
