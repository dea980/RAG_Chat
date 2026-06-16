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
