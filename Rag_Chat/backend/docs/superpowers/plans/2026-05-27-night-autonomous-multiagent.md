# Night Autonomous Multi-Agent + Wrap-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** While the user sleeps, each Claude CLI terminal autonomously works a mission from a shared `missions.md`, then on completion/STOP writes a work-report + beginner RAG-learning markdown that a jinja2 renderer turns into HTML plus a merged dashboard.

**Architecture:** Approach C (hybrid). Loop commands (`/nightwork`, `/wrapup`) live in `.claude/commands/` and write markdown into `backend/docs/sessions/night/`. A standalone Python renderer `backend/scripts/build_night_report.py` (sibling of existing `build_concepts.py`) reads that markdown + jinja2 templates in `backend/docs/_layouts/` and emits HTML into `backend/docs/reports/night/`. Agents never commit (vertical isolation); a `settings.local.json` allowlist keeps the overnight loop from stalling on permission prompts.

**Tech Stack:** Python 3.11, `markdown`, `jinja2`, `pyyaml` (already in repo), pytest + pytest-django (renderer test is plain pytest, no Django), Claude Code slash commands.

**Spec:** `backend/docs/superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md`

**Conventions for every commit step:** run from the repo working dir; `git add` ONLY the exact paths listed (the repo has unrelated uncommitted parallel work — never `git add -A`). Paths below are relative to `Rag_Chat/`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/docs/sessions/missions.md` | Shared task board — per-terminal goal, items, write-permission zones, done-criteria, STOP rule |
| `backend/docs/_layouts/night_base.html` | Base jinja2 template — `<style>` (reused from learning_journey.html) + page chrome |
| `backend/docs/_layouts/night_report.html` | Work-report template (extends base) |
| `backend/docs/_layouts/night_learning.html` | Beginner-learning template (extends base) |
| `backend/docs/_layouts/night_index.html` | Merged dashboard template (extends base) |
| `backend/scripts/build_night_report.py` | Renderer: night markdown → HTML + dashboard |
| `backend/scripts/test_build_night_report.py` | Renderer unit tests |
| `.claude/commands/nightwork.md` | `/nightwork <Tn>` — autonomous loop command |
| `.claude/commands/wrapup.md` | `/wrapup [<Tn>]` — manual wrap-up / HTML rebuild |
| `.claude/settings.local.json` | Add allow rules for unattended overnight run |
| `backend/docs/sessions/night/.gitkeep` | Keep the source dir present for the renderer |

---

## Task 1: Shared mission board (`missions.md`)

**Files:**
- Create: `backend/docs/sessions/missions.md`

- [ ] **Step 1: Create the mission board**

```markdown
# Night Missions — <YYYY-MM-DD>

> 야간 병렬 세션의 공유 임무판. 각 터미널은 시작 시 `/nightwork <Tn>` 로 자기 섹션만 읽는다.
> 핵심 규칙: **수직 격리** — 자기 전용 파일만 만들고, 공유 파일은 끝줄에 1줄 append + 출처 주석.
> 아무도 commit 하지 않는다. 사용자가 깨서 통합한다.

상태 범례 — ✅ done · 🟢 active · ⛔ blocked · ⏳ planned

## STOP 신호
`backend/docs/sessions/night/STOP` 파일을 만들면 모든 터미널이 다음 항목 시작 전 감지하여
즉시 wrap-up 한다. 새 세션 시작 전 사용자가 이 파일을 지운다.

---

## T1
- **목표**: <한 줄>
- **임무 항목**:
  - [ ] <항목 1>
  - [ ] <항목 2>
- **쓰기 권한 영역**:
  - 전용(자유 생성/수정): `<경로>`
  - 공유(끝줄 1줄 append + `# T1:` 주석): `<경로>`
  - 금지: 그 외 전부, `.env`, 다른 터미널 영역
- **완료 정의**: <무엇이 되면 done 인가 — 예: 테스트 통과 + work.md 작성>

## T2
- **목표**: <한 줄>
- **임무 항목**:
  - [ ] <항목 1>
- **쓰기 권한 영역**:
  - 전용: `<경로>`
  - 공유: `<경로>`
  - 금지: 그 외 전부
- **완료 정의**: <…>

## T3
- **목표**: <한 줄>
- **임무 항목**:
  - [ ] <항목 1>
- **쓰기 권한 영역**:
  - 전용: `<경로>`
  - 공유: `<경로>`
  - 금지: 그 외 전부
- **완료 정의**: <…>
```

- [ ] **Step 2: Commit**

```bash
git add backend/docs/sessions/missions.md
git commit -m "feat(night): add shared mission board template"
```

---

## Task 2: Jinja2 templates

The renderer test in Task 3 loads these from `backend/docs/_layouts/`, so they must exist first. Verification for this task is structural (valid templates that the Task 3 test will exercise).

**Files:**
- Create: `backend/docs/_layouts/night_base.html`
- Create: `backend/docs/_layouts/night_report.html`
- Create: `backend/docs/_layouts/night_learning.html`
- Create: `backend/docs/_layouts/night_index.html`

- [ ] **Step 1: Create `night_base.html`**

Create the file below. For the `<style>` body, copy the CSS **between** `<style>` and `</style>` from `backend/docs/reports/learning_journey.html` (lines 8–127) verbatim into the marked spot, then keep the night-specific additions that follow it.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{% block title %}야간 리포트{% endblock %}</title>
<style>
/* === BEGIN: paste learning_journey.html CSS (its lines 8–127) here verbatim === */
/* === END paste === */

/* night-specific additions */
.status-pill { display:inline-block; padding:2px 10px; border-radius:999px;
  font-size:13px; font-weight:600; }
.status-pill.done    { background:#dcfce7; color:#166534; }
.status-pill.active  { background:#dbeafe; color:#1e40af; }
.status-pill.blocked { background:#fee2e2; color:#991b1b; }
.status-pill.planned { background:#f3f4f6; color:#374151; }
.card { border:1px solid var(--border); border-radius:10px; padding:18px 20px; margin:14px 0; }
.card h3 { margin-top:0; }
.muted { color:var(--muted); font-size:14px; }
</style>
</head>
<body>
{% block content %}{% endblock %}
<footer class="muted" style="margin-top:60px; border-top:1px solid var(--border); padding-top:16px;">
  생성: {{ built|default('') }} · 야간 자율 멀티에이전트 wrap-up
</footer>
</body>
</html>
```

- [ ] **Step 2: Create `night_report.html`**

```html
{% extends "night_base.html" %}
{% block title %}{{ doc.terminal }} 작업 리포트 — {{ doc.title }}{% endblock %}
{% block content %}
<p class="muted"><a href="index.html">← 대시보드</a></p>
<h1>{{ doc.terminal }} · {{ doc.title }}</h1>
<p>
  <span class="status-pill {{ status_class }}">{{ doc.status }}</span>
  <span class="muted">업데이트 {{ doc.updated }}</span>
</p>
<p class="muted">임무: {{ doc.mission }}</p>
<p class="muted">👉 <a href="{{ doc.terminal }}-learning.html">이 작업으로 배우는 RAG 개념 →</a></p>
<hr>
{{ body|safe }}
{% endblock %}
```

- [ ] **Step 3: Create `night_learning.html`**

```html
{% extends "night_base.html" %}
{% block title %}{{ doc.terminal }} 학습 — {{ doc.title }}{% endblock %}
{% block content %}
<p class="muted"><a href="index.html">← 대시보드</a> · <a href="{{ doc.terminal }}.html">작업 리포트 →</a></p>
<h1>📚 {{ doc.title }}</h1>
<p class="muted">{{ doc.terminal }} · 임무: {{ doc.mission }} · 업데이트 {{ doc.updated }}</p>
<hr>
{{ body|safe }}
{% endblock %}
```

- [ ] **Step 4: Create `night_index.html`**

```html
{% extends "night_base.html" %}
{% block title %}야간 작업 대시보드{% endblock %}
{% block content %}
<h1>🌙 야간 작업 대시보드</h1>
<p class="muted">자는 동안 돌린 터미널별 작업 + 학습. 깼을 때 여기서 시작.</p>
{% if not summaries %}
<p class="muted">아직 완료된 터미널 없음.</p>
{% endif %}
{% for s in summaries %}
<div class="card">
  <h3>{{ s.terminal }} · {{ s.title }}
    <span class="status-pill {{ s.status_class }}">{{ s.status }}</span>
  </h3>
  <p class="muted">임무: {{ s.mission }} · 업데이트 {{ s.updated }}</p>
  <p><a href="{{ s.report }}">작업 리포트 →</a> · <a href="{{ s.learning }}">학습 문서 →</a></p>
</div>
{% endfor %}
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add backend/docs/_layouts/night_base.html backend/docs/_layouts/night_report.html backend/docs/_layouts/night_learning.html backend/docs/_layouts/night_index.html
git commit -m "feat(night): add jinja2 templates for report/learning/dashboard"
```

---

## Task 3: Renderer `build_night_report.py` (TDD)

**Files:**
- Create: `backend/scripts/build_night_report.py`
- Test: `backend/scripts/test_build_night_report.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/scripts/test_build_night_report.py`:

```python
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
LAYOUTS = SCRIPTS.parent / "docs" / "_layouts"

import build_night_report as bnr  # noqa: E402

WORK = """---
terminal: T1
title: OCR loader
status: done
mission: Phase 5 OCR loader
updated: 2026-05-27 23:00
---
## 한 일
- ocr.py 추가
"""

LEARNING = """---
terminal: T1
title: OCR loader 학습
status: done
mission: Phase 5 OCR loader
updated: 2026-05-27 23:00
---
## 왜 OCR 인가
이미지 속 글자를 텍스트로 바꾼다.
"""


def test_build_renders_report_learning_and_index(tmp_path):
    src = tmp_path / "night"; src.mkdir()
    out = tmp_path / "out"
    (src / "T1.work.md").write_text(WORK, encoding="utf-8")
    (src / "T1.learning.md").write_text(LEARNING, encoding="utf-8")

    written = bnr.build(src=src, out=out, layouts=LAYOUTS)

    names = {p.name for p in written}
    assert "T1.html" in names
    assert "T1-learning.html" in names
    assert "index.html" in names
    report = (out / "T1.html").read_text(encoding="utf-8")
    assert "OCR loader" in report
    assert "ocr.py" in report
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "T1" in index
    assert "done" in index


def test_terminal_filter_skips_others_but_keeps_dashboard(tmp_path):
    src = tmp_path / "night"; src.mkdir()
    out = tmp_path / "out"
    (src / "T1.work.md").write_text(WORK, encoding="utf-8")
    (src / "T2.work.md").write_text(WORK.replace("T1", "T2"), encoding="utf-8")

    written = bnr.build(src=src, out=out, layouts=LAYOUTS, terminal="T2")

    names = {p.name for p in written}
    assert "T2.html" in names
    assert "T1.html" not in names        # filtered out
    assert "index.html" in names         # dashboard still rebuilt
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "T1" in index and "T2" in index  # both still summarized


def test_missing_frontmatter_is_skipped(tmp_path):
    src = tmp_path / "night"; src.mkdir()
    out = tmp_path / "out"
    (src / "T1.work.md").write_text("no frontmatter here", encoding="utf-8")

    written = bnr.build(src=src, out=out, layouts=LAYOUTS)

    names = {p.name for p in written}
    assert "T1.html" not in names
    assert "index.html" in names         # empty dashboard still produced
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest scripts/test_build_night_report.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'build_night_report'`

- [ ] **Step 3: Implement the renderer**

Create `backend/scripts/build_night_report.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest scripts/test_build_night_report.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/build_night_report.py backend/scripts/test_build_night_report.py
git commit -m "feat(night): add markdown->HTML renderer with dashboard + tests"
```

---

## Task 4: `/nightwork` loop command

**Files:**
- Create: `.claude/commands/nightwork.md`

- [ ] **Step 1: Create the command**

```markdown
---
description: 야간 자율 루프 — missions.md 의 한 터미널 임무를 끝까지 수행 후 wrap-up
argument-hint: <Tn>  (예: T2)
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, TodoWrite, Skill
---

너는 야간 병렬 세션의 터미널 **$1** 이다. 사용자는 자고 있다. 혼자 끝까지 진행한다.

## 1. 임무 파악
`backend/docs/sessions/missions.md` 를 읽고 **## $1** 섹션만 본다.
- 목표 / 임무 항목 / 쓰기 권한 영역(전용·공유 1줄·금지) / 완료 정의 확인.
- 자기 영역 밖 파일은 **절대 수정 금지**. 공유 파일은 끝줄 append + `# $1:` 출처 주석만.

## 2. 알맞은 스킬 탐색 (필수)
작업 성격에 맞는 superpowers 스킬을 먼저 invoke 한다:
- 기능 구현 → test-driven-development
- 버그/오류 → systematic-debugging
- 도메인(프론트/문서 등) → 해당 스킬
1%라도 맞으면 쓴다.

## 3. 작업 루프
임무 항목을 하나씩 처리. **매 항목 시작 전** `backend/docs/sessions/night/STOP` 존재를 확인 →
있으면 즉시 4번으로 간다. 항목을 끝낼 때마다 `backend/docs/sessions/night/$1.work.md` 에 append
(없으면 아래 frontmatter 와 함께 생성):
- 무엇을 / 왜 / 어떻게 / 바뀐 파일 목록 / 테스트 결과

work.md frontmatter (최초 생성 시):
\`\`\`
---
terminal: $1
title: <임무 한 줄 제목>
status: active
mission: <missions.md 의 목표 한 줄>
updated: <YYYY-MM-DD HH:MM>
---
\`\`\`
막히면 `status: blocked` 로 바꾸고 막힌 이유를 본문에 적는다.

## 4. Wrap-up (임무 완료 또는 STOP 감지)
1. work.md 의 `status` 를 `done` 또는 `blocked` 로, `updated` 를 현재 시각으로 갱신.
2. `backend/docs/sessions/night/$1.learning.md` 작성 — **RAG 초보용**. 이번 작업이 건드린 개념을:
   - 비유로 설명 / "왜 필요한가" 섹션 / 끝에 연습문제 1–2개.
   - 톤은 `backend/docs/reports/learning_journey.html` 을 따른다.
   - frontmatter 는 work.md 와 같은 형식 (title 끝에 "학습").
3. HTML 생성: `python backend/scripts/build_night_report.py --terminal $1`
4. **commit 하지 않는다.** 자기 영역만 남기고 종료. 사용자가 깨서 통합한다.

## 5. 자기 페이스
한 번에 멈추지 말고 임무 완료까지 진행한다. 길어지면 `/loop` self-pace 로 감싸 이어가도 좋다.
```

- [ ] **Step 2: Verify the command is discoverable**

Run: `ls .claude/commands/nightwork.md`
Expected: path prints (file exists). In a Claude Code session `/nightwork` now autocompletes.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/nightwork.md
git commit -m "feat(night): add /nightwork autonomous loop command"
```

---

## Task 5: `/wrapup` command

**Files:**
- Create: `.claude/commands/wrapup.md`

- [ ] **Step 1: Create the command**

```markdown
---
description: 야간 작업 수동 마무리 — 학습 문서 생성 + HTML 재빌드
argument-hint: [<Tn>]  (생략 시 전체)
allowed-tools: Read, Edit, Write, Bash, Glob
---

야간 작업을 마무리하고 HTML 을 (재)생성한다.

대상: `$1` 이 있으면 그 터미널만, 없으면 `backend/docs/sessions/night/*.work.md` 전부.

각 대상에 대해:
1. `<Tn>.learning.md` 가 없으면 `<Tn>.work.md` 를 읽고 초보용 학습 문서를 작성
   (비유 + "왜" 섹션 + 연습문제, `learning_journey.html` 톤).
2. `<Tn>.work.md` 의 `status` / `updated` 정합성 확인.

마지막에 HTML 빌드:
- 특정 터미널: `python backend/scripts/build_night_report.py --terminal $1`
- 전체: `python backend/scripts/build_night_report.py`

commit 하지 않는다. 생성된 파일 경로를 출력한다.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/commands/wrapup.md
git commit -m "feat(night): add /wrapup manual wrap-up command"
```

---

## Task 6: Permissions for unattended run

**Files:**
- Modify: `.claude/settings.local.json`

- [ ] **Step 1: Replace the file with the expanded allowlist**

Current content has one allow entry. Replace the whole file with:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 -c \"import markdown, jinja2, yaml; print\\('deps:', markdown.__version__, jinja2.__version__, yaml.__version__\\)\")",
      "Bash(python backend/scripts/build_night_report.py:*)",
      "Bash(python3 backend/scripts/build_night_report.py:*)",
      "Bash(python -m pytest:*)",
      "Bash(python3 -m pytest:*)",
      "Bash(pytest:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git add:*)"
    ]
  }
}
```

Note: `git commit`, `git push`, `git reset`, `rm` are intentionally absent → they still prompt / are blocked, enforcing the no-commit isolation rule.

- [ ] **Step 2: Validate JSON**

Run: `python3 -c "import json; json.load(open('.claude/settings.local.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.local.json
git commit -m "chore(night): allowlist build/test/git-status for unattended loop"
```

---

## Task 7: Scaffold source dir + end-to-end verify

**Files:**
- Create: `backend/docs/sessions/night/.gitkeep`

- [ ] **Step 1: Keep the source dir present**

```bash
mkdir -p backend/docs/sessions/night
touch backend/docs/sessions/night/.gitkeep
```

- [ ] **Step 2: End-to-end render with a throwaway example**

Create `backend/docs/sessions/night/T0.work.md`:

```markdown
---
terminal: T0
title: 스모크 테스트
status: done
mission: 파이프라인 e2e 확인
updated: 2026-05-27 23:59
---
## 한 일
- 렌더러가 work.md 를 HTML 로 바꾸는지 확인.
```

Create `backend/docs/sessions/night/T0.learning.md`:

```markdown
---
terminal: T0
title: 스모크 테스트 학습
status: done
mission: 파이프라인 e2e 확인
updated: 2026-05-27 23:59
---
## 왜 정적 HTML 인가
서버 없이 브라우저로 바로 열어 본다. 비유: 사진을 인화해 책상에 둔다.
```

Run: `python backend/scripts/build_night_report.py`
Expected output lists `docs/reports/night/T0.html`, `T0-learning.html`, `index.html`.

- [ ] **Step 3: Confirm the output is real HTML**

Run: `python3 -c "h=open('backend/docs/reports/night/index.html').read(); assert 'T0' in h and '스모크' in h; print('dashboard ok')"`
Expected: `dashboard ok`

Open `backend/docs/reports/night/index.html` in a browser to eyeball the dashboard → T0 card links to report + learning.

- [ ] **Step 4: Remove the throwaway example, keep real output dir**

```bash
rm backend/docs/sessions/night/T0.work.md backend/docs/sessions/night/T0.learning.md
rm backend/docs/reports/night/T0.html backend/docs/reports/night/T0-learning.html
python backend/scripts/build_night_report.py   # rebuild empty dashboard
```

- [ ] **Step 5: Commit the scaffold**

```bash
git add backend/docs/sessions/night/.gitkeep
git commit -m "chore(night): scaffold night source dir"
```

---

## Done criteria

- `/nightwork <Tn>` and `/wrapup` appear in the Claude Code command list.
- `python backend/scripts/build_night_report.py` builds a dashboard from any `night/*.work.md`.
- `python -m pytest backend/scripts/test_build_night_report.py` is green.
- Overnight loop runs without permission prompts for build/test/git-status, and cannot commit.
- A user waking up opens `backend/docs/reports/night/index.html` and reaches each terminal's work report + beginner learning doc.

## How the user runs it (operator guide)

1. Fill in `backend/docs/sessions/missions.md` (T1/T2/T3 sections) before bed.
2. Open one terminal per mission; in each run `/nightwork T1` (T2, T3, …). Optionally wrap with `/loop /nightwork T1` for self-pacing.
3. To stop early: `touch backend/docs/sessions/night/STOP`.
4. On waking: open `backend/docs/reports/night/index.html`, review, then integrate + commit manually. Delete the `STOP` file before the next run.
