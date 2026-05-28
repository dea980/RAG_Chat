# C4 — ForbiddenWord starter seed (Phase A 잔여 criterion)

## 한 줄 요약
Phase A exit criteria 중 마지막 미해결 항목 — "ForbiddenWord.objects.count() ≥ 15" — 을 idempotent 한 `seed_forbidden_words` management 커맨드로 닫았다. 4 카테고리 (욕설·대외비·PII·경쟁사) 각 4개씩, 총 16개 starter rule.

## 비유
**새 아파트 입주 첫날의 기본 비치품.** 빈 부엌이 아니라 휴지 한 통, 수세미 한 개, 컵 두 개가 미리 있어야 곧바로 살 수 있다. 운영자가 admin UI 열었을 때 "어떤 단어를 등록해야 하지?" 라고 멍 때리지 않게 starter set 을 깔아둔다. 운영자가 그 starter 를 끄거나 메모를 달면 다음 `seed` 실행 시 **그 결정을 덮지 않는다**.

<div class="analogy">
<code>get_or_create</code> 의 정직한 특성 — defaults 는 <strong>최초 INSERT 때만</strong> 적용된다. 두 번째 실행에서 이미 row 가 있으면 defaults 는 무시되고 운영자가 손댄 값이 그대로 남는다. 이게 "idempotent + 운영자 우선" 의 핵심.
</div>

## 왜 이게 필요한가

| 항목 | 이전 | 이후 |
|---|---|---|
| Phase A exit criteria | 6/7 (seed 부재) | **7/7** ✅ |
| admin UI 첫 화면 | 빈 테이블 + "규칙 없음" | 4 카테고리 16개 starter, 즉시 의미 있는 표 |
| 신규 dev 환경 부팅 | 운영자가 매번 손으로 등록 | `python manage.py seed_forbidden_words` 한 줄 |
| 운영자 커스터마이즈 | 첫 INSERT 후 매 배포마다 덮어쓸 위험 | 두 번째 실행 시 보존 — `get_or_create` defaults 무시 |

## 핵심 코드

```python
# moderation/management/commands/seed_forbidden_words.py — 핵심 5줄
for word, category, severity, direction, mask, note in STARTER:
    _, was_created = ForbiddenWord.objects.get_or_create(
        word=word,                                # ← unique 키
        defaults={"category": category, "severity": severity,   # 최초 INSERT 때만 채워짐
                  "direction": direction, "mask_replacement": mask,
                  "note": note, "is_active": True},
    )
```

```python
# starter 분포 — 4 카테고리 × 4 단어
STARTER = [
    ("대외비", "대외비", BLOCK, BOTH, ...),      # 4 × 대외비 — 4경계 모두 BLOCK
    ("주민번호", "PII", MASK, OUTBOUND, ...),    # 4 × PII — 응답·검색 쪽 마스킹만
    ("씨발", "욕설", MASK, BOTH, ...),           # 4 × 욕설 — 양방향 마스킹
    ("competitor-a", "경쟁사", WARNING, BOTH),   # 4 × 경쟁사 — WARN (로그만)
]
```

severity·direction 선택 이유:
- **대외비 → BLOCK + BOTH**: 들어와도 안 되고 나가도 안 됨. 가장 단호.
- **PII → MASK + OUTBOUND**: 사용자가 자기 정보 물어볼 때 입력은 허용하되, LLM 응답이 PII 를 그대로 뱉으면 안 됨. 마스킹만.
- **욕설 → MASK + BOTH**: 사내 챗봇 톤 유지. 차단까지는 X.
- **경쟁사 → WARN + BOTH**: 차단·마스킹 없이 로그만. 영업팀 컨텍스트 추적용.

## 데이터 흐름

```
[새 dev 환경]
   ./manage.py migrate                 # B3·B6·B7 마이그레이션
   ./manage.py seed_test_users         # 7명 더미 사용자 (B3)
   ./manage.py seed_forbidden_words    # 16개 starter rules  ← C4 신규
        │
        ▼
   ForbiddenWord 테이블 = 16 rows
        │
        ▼
   4 경계가 즉시 의미 있게 작동:
   - chat 질문에 "대외비" → 403 BLOCK
   - chat 응답에 "주민번호" → MASK [REDACTED]
   - ingest 에 "기밀" → 스킵
   - retrieval 청크에 "Claude" 언급 → WARN log
        │
        ▼
   admin UI 첫 열기 → 비어있지 않음 → 운영자가 어떤 단어를 추가할지 감 잡음
```

## 확인 방법

```bash
cd Rag_Chat/backend

# 명령 자체 실행
venv/bin/python manage.py seed_forbidden_words
# → "seed_forbidden_words: 16 created, 0 preserved (total=16)"

# 두 번째 실행 — 운영자 편집 보존 확인
venv/bin/python manage.py seed_forbidden_words
# → "seed_forbidden_words: 0 created, 16 preserved (total=16)"

# 단위 테스트
venv/bin/python manage.py test moderation.tests.test_seed_forbidden_words -v 1
# → 5/5 OK
```

## 함정 — `get_or_create(defaults=...)` 의 모든 키워드

`defaults=` 에 넣은 값은 **최초 INSERT 때만** 적용된다. 두 번째 실행부터는 무시된다. 이게 "운영자 편집 보존" 동작의 비밀. 만약 starter 값을 *강제로 다시 적용*하고 싶다면 `update_or_create` 를 써야 하는데, 이는 운영자 의도를 짓밟는 패턴이라 staring point 단계에서는 부적절.

## 함정 — fixtures vs management command

Django 의 fixture (`python manage.py loaddata`) 도 비슷한 일을 한다. 하지만 fixture 는 idempotent 가 아님 — `loaddata` 는 PK 가 같으면 UPDATE 하고 운영자 편집을 덮어쓴다. starter set 처럼 운영자 후처리를 존중해야 하는 경우엔 management command + `get_or_create` 가 더 안전.

## 함정 — 욕설 starter 의 false positive

`씨발` 단어가 `씨발 진짜로` 같은 비욕설 표현 (예: 격앙된 강조) 에도 잡힐 수 있음. 그래서 `severity=MASK` 로 둠 — 차단 (`BLOCK`) 이 아니라 마스킹만. 운영자가 사후 검수하며 false positive 빈도 보고 BLOCK 으로 올릴지 결정.

## 연습 문제

1. **카테고리별 starter 수 늘리기**: 신규 입사자 환영에는 4 × 4 가 적당하지만, 3개월 운영 후 starter 를 4 × 10 (총 40 rule) 로 확장하려면? 힌트: STARTER 리스트 추가 + 같은 명령 다시 실행. 운영자가 새로 추가한 rule 은 안 건드림.

2. **CSV 입력**: starter 를 코드 안 STARTER 가 아니라 외부 CSV (`starter_words.csv`) 에서 읽도록 하려면? 힌트: `csv.DictReader` + 같은 `get_or_create` 루프. 운영자가 비-개발자라도 CSV 만 손볼 수 있어 dev 와 콘텐츠 분리 가능.

3. **`--force` 옵션**: 운영자가 "starter 값으로 되돌리고 싶다" 고 했을 때 `--force` 면 `update_or_create` 로 모드 변경하려면? 힌트: `parser.add_argument("--force", action="store_true")`. 평소엔 보존, --force 일 때만 덮어쓰기. **단, 이건 위험 액션** — 운영자가 의도하지 않은 변경을 만들 수 있어 prompt 확인 step 도 함께.
