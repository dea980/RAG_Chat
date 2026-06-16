"""Category → next-step copy (CLAUDE.md refusal pattern).

The block-response UI requires the backend to attach an action list so the
user is never told "blocked, deal with it." Each entry is a single sentence
the user can read and act on. Operator can override per-category by editing
this file (next iteration: move to DB).
"""
from __future__ import annotations

from typing import Iterable

_CATEGORY_NEXT_STEPS: dict[str, list[str]] = {
    "대외비": [
        "이 문서의 열람 권한이 필요하면 관리자에게 공개 신청을 보내세요.",
        "당장 답변이 필요한 사안이면 본문에서 기밀 표현을 빼고 다시 질문해 주세요.",
    ],
    "PII": [
        "주민번호·전화번호 등 개인정보를 빼고 다시 질문해 주세요.",
        "정말 필요한 경우 보안팀 승인 절차를 거쳐 별도 채널로 요청하세요.",
    ],
    "욕설": [
        "정제된 표현으로 다시 시도해 주세요.",
        "사내 챗봇은 욕설 포함 문장을 LLM 으로 전달하지 않습니다.",
    ],
    "경쟁사": [
        "경쟁사 관련 정보는 영업 정책상 챗봇이 직접 답하지 않습니다.",
        "영업팀(slack #sales) 으로 문의해 주세요.",
    ],
}

_FALLBACK = [
    "운영자가 차단으로 분류한 표현입니다 — 표현을 바꿔 다시 시도하거나 관리자에게 문의해 주세요.",
]


def next_steps_for(categories: Iterable[str]) -> list[str]:
    """Compose the user-facing next-step list for a set of blocked categories.

    Categories appear in input order, but the output preserves dedup-stable
    order so the UI can render them top-to-bottom by severity expectations
    (`대외비` first when both present).
    """
    seen: set[str] = set()
    steps: list[str] = []
    for cat in categories:
        if not cat or cat in seen:
            continue
        seen.add(cat)
        for line in _CATEGORY_NEXT_STEPS.get(cat, _FALLBACK):
            if line not in steps:
                steps.append(line)
    if not steps:
        steps.extend(_FALLBACK)
    return steps
