"""Persona × audience_tier ACL 매핑.

설계 문서: backend/docs/learning/2026-05-29-persona-security-design.md

retrieval / generation prompt / admin UI 가 공유하는 단일 진입점.
운영자 admin 으로 토글 가능해야 하므로 향후 DB-backed 으로 옮길 수 있게
함수 인터페이스 유지.
"""
from __future__ import annotations

from enum import Enum


class Persona(str, Enum):
    P1_RETAIL = "P1_RETAIL"        # 매장 직원
    P2_B2B = "P2_B2B"              # 기업 영업
    P3_HQ = "P3_HQ"                # 본사 마케팅/영업기획
    P4_OUTBOUND = "P4_OUTBOUND"    # 외판/콜센터


# persona × tier 접근 매트릭스 (작업 가설).
# 보안 설계 §4 매트릭스 참조. 운영자 admin 으로 추후 DB 이전 예정.
_TIERS_BY_PERSONA: dict[str, tuple[str, ...]] = {
    Persona.P1_RETAIL.value:   ("public", "retail", "carrier"),
    Persona.P2_B2B.value:      ("public", "retail", "b2b"),
    Persona.P3_HQ.value:       ("public", "retail", "b2b", "competitive", "carrier"),
    Persona.P4_OUTBOUND.value: ("public", "retail", "carrier"),
}

# 미인증/페르소나 미할당 — 가장 보수적 (public + retail 만).
_DEFAULT_TIERS = ("public", "retail")


def tiers_for_persona(persona: str | Persona | None) -> tuple[str, ...]:
    """페르소나 코드 → 접근 가능 audience_tier 튜플.

    None 또는 미등록 페르소나 → 가장 보수적 fallback.
    internal_only 는 어떤 페르소나에게도 반환되지 않는다 — corpus 에서 차단됨.
    """
    if persona is None:
        return _DEFAULT_TIERS
    key = persona.value if isinstance(persona, Persona) else str(persona)
    return _TIERS_BY_PERSONA.get(key, _DEFAULT_TIERS)


def chroma_filter_for_persona(persona: str | Persona | None) -> dict:
    """Chroma similarity_search 의 filter kwarg 형식."""
    return {"audience_tier": {"$in": list(tiers_for_persona(persona))}}


# persona 별 generation prompt 가이드. 답변 길이·톤·citation 형식 차별화.
# 설계: persona-security-design §5 "persona × feature 매트릭스"
_PERSONA_STYLE_GUIDE: dict[str, str] = {
    Persona.P1_RETAIL.value: (
        "**페르소나: P1 매장 직원** — 고객 응대 중 (30초 압박).\n"
        "- 답변 길이: 1~2 문장 최대.\n"
        "- 톤: 친근, 즉답.\n"
        "- 가격은 자급제·통신사 출고가 위주. 비교표는 짧게.\n"
        "- 기업 도입·B2B 정보 요청 시: \"B2B 영업팀에 문의 부탁드립니다\" 로 redirect.\n"
    ),
    Persona.P2_B2B.value: (
        "**페르소나: P2 B2B 영업** — 제안서 작성용. 시간 여유.\n"
        "- 답변 길이: 3~10 문장, 표·bullet 환영.\n"
        "- 톤: 격식, 전문, 근거 명시.\n"
        "- Knox·보안 인증·DeX 같은 기업 기능 강조.\n"
        "- 견적 단가 요청 시: \"공개 시작가 기준. 기업 견적은 별도 채널.\" 명시.\n"
    ),
    Persona.P3_HQ.value: (
        "**페르소나: P3 본사 마케팅/영업기획** — 분석·기획.\n"
        "- 답변 길이: 제한 없음. 표·수치 위주.\n"
        "- 톤: 데이터 중립, 출처·날짜 명시.\n"
        "- 경쟁사 비교 풀스펙 가능 (iPhone/Pixel/Xiaomi).\n"
    ),
    Persona.P4_OUTBOUND.value: (
        "**페르소나: P4 외판/콜센터** — 전화·방문, 음성 가능성.\n"
        "- 답변 길이: 1 문장.\n"
        "- 톤: 친근, 간결, 음성 친화 (마크다운·표 회피).\n"
        "- 통신사 가격·약정·결합 위주.\n"
        "- 보조금은 \"공시지원금 + 매장별 추가지원 가능\" 패턴.\n"
    ),
}

_DEFAULT_STYLE = (
    "**페르소나 미할당** — 가장 보수적 응답.\n"
    "- 답변 길이: 2~3 문장.\n"
    "- 공개 정보만. 가격·할인·기업 정보 추측 금지.\n"
)


def prompt_style_for_persona(persona: str | Persona | None) -> str:
    """페르소나 별 generation prompt 스타일 가이드 문자열."""
    if persona is None:
        return _DEFAULT_STYLE
    key = persona.value if isinstance(persona, Persona) else str(persona)
    return _PERSONA_STYLE_GUIDE.get(key, _DEFAULT_STYLE)


# 질문 의도 → audience_tier 추정 키워드. 권한 위반 시도 (EscalationAttempt)
# 탐지용. LLM 분류기로 대체 가능하지만 일단 비용 없는 규칙 기반.
_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "internal_only": (
        "마진", "마진율", "KPI", "견적 단가", "단가표", "인센티브",
        "성과급", "보조금표", "리베이트", "매장 실적",
    ),
    "b2b": (
        "Knox", "knox", "Knox Vault", "Knox Manage", "EAL", "KCMVP",
        "FIPS", "NIAP", "보안 인증", "기업 도입", "임대 계약",
        "대량 견적", "B2B", "b2b",
    ),
    "competitive": (
        "iPhone", "iphone", "아이폰", "Pixel", "픽셀", "Xiaomi", "샤오미",
        "Geekbench", "벤치마크", "시장 점유율", "경쟁사",
    ),
    "carrier": (
        "KT", "SKT", "LGU", "LG U+", "통신사", "약정", "결합 할인",
        "공시지원금", "월 납부", "가족결합",
    ),
}


def detect_query_intent_tiers(query: str) -> list[str]:
    """질문 텍스트에서 의도 tier 추정. 다중 매칭 가능.

    매칭 없으면 빈 리스트 → 일반 질문으로 간주. 매칭 있으면 권한 체크에 활용.
    """
    matched = []
    for tier, kws in _INTENT_KEYWORDS.items():
        if any(kw in query for kw in kws):
            matched.append(tier)
    return matched


def is_escalation(query: str, persona: str | Persona | None) -> tuple[bool, list[str], list[str]]:
    """권한 위반 시도 여부.

    Returns (escalated, detected_tiers, allowed_tiers).
    escalated = detected 중 allowed 외의 tier 가 있으면 True.
    """
    detected = detect_query_intent_tiers(query)
    allowed = list(tiers_for_persona(persona))
    out_of_scope = [t for t in detected if t not in allowed]
    return (bool(out_of_scope), detected, allowed)
