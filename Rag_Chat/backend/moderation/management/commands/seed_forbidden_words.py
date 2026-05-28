"""Idempotent starter seed for ForbiddenWord (Phase A exit criterion).

운영자가 colocated 한 admin UI (C2) 에 처음 들어오면 비어있는 테이블 대신
사고가 가장 잦은 4 카테고리 (욕설 · 대외비 · PII · 경쟁사) 의 starter 규칙
이 보이도록 한다.

특성:
- `get_or_create` 로 중복 안 만듦.
- 운영자가 `is_active=False` 로 끈 규칙이나 `note` 를 단 규칙은 다시 덮지
  않음 (defaults 는 *최초 생성* 시점에만 적용).
- 새 단어는 starter 목록을 늘리고 다시 실행하면 추가됨.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from moderation.models import ForbiddenWord


_BLOCK, _MASK, _WARN = (
    ForbiddenWord.Severity.BLOCK,
    ForbiddenWord.Severity.MASK,
    ForbiddenWord.Severity.WARNING,
)
_BOTH, _IN, _OUT = (
    ForbiddenWord.Direction.BOTH,
    ForbiddenWord.Direction.INBOUND,
    ForbiddenWord.Direction.OUTBOUND,
)
_KW, _RE = (
    ForbiddenWord.PatternType.KW,
    ForbiddenWord.PatternType.RE,
)

# (word, category, severity, direction, mask_replacement, note, pattern_type)
STARTER: list[tuple[str, str, str, str, str, str, str]] = [
    # 대외비 — 내부 자료 유출 방지. 4경계 모두 차단.
    ("대외비", "대외비", _BLOCK, _BOTH, "[REDACTED]", "starter: 기밀 표지 자동 차단", _KW),
    ("기밀", "대외비", _BLOCK, _BOTH, "[REDACTED]", "starter: 기밀 표지 자동 차단", _KW),
    ("내부전용", "대외비", _BLOCK, _BOTH, "[REDACTED]", "starter", _KW),
    ("confidential", "대외비", _BLOCK, _BOTH, "[REDACTED]", "starter", _KW),

    # PII — 응답·검색 쪽으로 빠져나가는 것만 마스킹.
    ("주민번호", "PII", _MASK, _OUT, "[REDACTED]", "starter: PII 단어", _KW),
    ("전화번호", "PII", _MASK, _OUT, "[REDACTED]", "starter", _KW),
    ("카드번호", "PII", _MASK, _OUT, "[REDACTED]", "starter", _KW),
    ("이메일주소", "PII", _MASK, _OUT, "[REDACTED]", "starter", _KW),
    # C5 — regex 패턴으로 실제 번호 형식 자체를 잡는다.
    (r"\d{6}-\d{7}", "PII", _MASK, _OUT, "[주민번호REDACTED]", "starter regex: 주민등록번호 13자리", _RE),
    (r"\d{4}-\d{4}-\d{4}-\d{4}", "PII", _MASK, _OUT, "[카드번호REDACTED]", "starter regex: 카드 16자리", _RE),

    # 욕설 — 양방향 마스킹. 사내 챗봇 톤 유지.
    ("씨발", "욕설", _MASK, _BOTH, "[삐]", "starter: 사내 욕설 마스킹", _KW),
    ("개새끼", "욕설", _MASK, _BOTH, "[삐]", "starter", _KW),
    ("좆같", "욕설", _MASK, _BOTH, "[삐]", "starter", _KW),
    ("fuck", "욕설", _MASK, _BOTH, "[BEEP]", "starter", _KW),

    # 경쟁사 — 차단까지는 안 하고 WARN 으로 로그만 (운영자 검수용).
    ("competitor-a", "경쟁사", _WARN, _BOTH, "[REDACTED]", "starter: 경쟁사 언급 추적", _KW),
    ("competitor-b", "경쟁사", _WARN, _BOTH, "[REDACTED]", "starter", _KW),
    ("ChatGPT", "경쟁사", _WARN, _BOTH, "[REDACTED]", "starter: 외부 LLM 언급 추적", _KW),
    ("Claude", "경쟁사", _WARN, _BOTH, "[REDACTED]", "starter", _KW),
]


class Command(BaseCommand):
    help = "Seed starter ForbiddenWord rules (idempotent — operator edits preserved)."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for word, category, severity, direction, mask, note, pattern_type in STARTER:
            _, was_created = ForbiddenWord.objects.get_or_create(
                word=word,
                defaults={
                    "category": category,
                    "severity": severity,
                    "direction": direction,
                    "mask_replacement": mask,
                    "note": note,
                    "pattern_type": pattern_type,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1
        total = ForbiddenWord.objects.count()
        self.stdout.write(
            f"seed_forbidden_words: {created} created, {skipped} preserved (total={total})"
        )
