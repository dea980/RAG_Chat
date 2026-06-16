---
title: 4-boundary Moderation (4경계 모더레이션)
slug: moderation-4boundary
category: Architecture
level: 중급
order: 55
summary: 업로드·질문·검색·답변 4개 지점에 같은 스키마의 라벨 기반 필터를 두고, 운영자가 코드 없이 튜닝하게 만드는 방어 구조.
prerequisites: []
related: [persona-acl]
updated: 2026-06-16
---

## 1 · 무엇인가

:::definition term="용어" name="4-boundary moderation"
RAG 파이프라인의 **데이터 수명주기 4 지점** (업로드 / 질문 / 검색 결과 / LLM 답변) 각각에 동일 스키마의 필터를 둔다. 규칙은 카테고리 × pattern_type(KW/RE) × scope ⊆ {4 경계} × severity(BLOCK/MASK/WARN) 로 표현되고, **운영자가 Admin UI 에서 직접 등록·테스트** 한다.
:::

본 단락 — "프롬프트 입구 한 번만 필터" 는 첫 분기에 죽는다. (1) 우회 (2) LLM 출력 누출 (3) 검색 결과 내 PII (4) 업로드된 문서 자체에 비밀. 4 지점 모두에서 같은 규칙을 적용해야 한 번 등록한 규칙이 전체 수명주기를 보호한다. 결정적으로 — **하드코딩 필터는 죽는다.** 운영팀이 코드 없이 튜닝 가능해야 한다.

## 2 · 비유로 이해하기

:::analogy title="회사 우편 시스템 4 검문소"
- **업로드** = 외부에서 사내 문서고로 들어오는 우편 (CSV/PDF 적재)
- **질문** = 직원이 문서고에 보내는 요청 메시지
- **검색** = 사서가 꺼낸 자료 (LLM 컨텍스트로 가기 전)
- **답변** = 사서가 직원에게 건네주는 답장

같은 "사내 기밀번호 + 외부 송신 금지" 규칙을 4 검문소가 다 들고 있다. 한 곳만 검문하면 → 다른 입구로 새거나, 사서가 자료에서 직접 베껴 답장에 적어 보낸다. **무성 폐기 금지** — 차단했으면 "여기서 1건 가렸음" 영수증을 남긴다. 직원은 자기 요청이 부분적으로 검열됐다는 사실을 안다.
:::

## 3 · 왜 중요한가

- **단일 경계 = 우회 1번이면 끝** — 4 경계는 동일 규칙을 4번 적용해 한 곳 우회해도 다음에서 잡힘
- **운영팀이 코드 PR 안 보내고 튜닝** — incident 발생 → 30 분 내 규칙 추가 → 실시간 테스트 → 활성화
- **audit 일관성** — 4 경계 모두 같은 ModerationLog 스키마. 사후 추적 (누가·언제·무엇·어떤 규칙·결과) 비용 ↓
- **citation 가시화** — 검색 단계 차단된 chunk 는 `[수정됨·N건]` 으로 사용자에게 보임 (`persona-acl` 와 동일 원칙)

:::callout warn title="흔한 함정"
"답변 단계에서만 거르면 되지" — LLM 이 본 chunk 는 학습되지 않아도 동일 세션에서 다른 표현으로 흘릴 수 있다. **검색 단계에서 차단** 해야 LLM 이 애초에 못 본다.
:::

## 4 · 우리 시스템에서의 의미

- 코드: [`backend/moderation/`](../../backend/moderation/) — `models.py`, `filter.py`, `permissions.py`, `views.py`
- Admin UI: [`/admin/moderation/`](http://localhost:8000/admin/moderation/) — 카테고리 · 패턴 · scope 체크박스 + **실시간 테스트 패널**
- 통합 hook 4 지점:
  - **업로드** — `chat/ingest/pipeline.py` 의 sink 직전
  - **질문** — `chat/views.py:ChatAPIView.post` 진입 직후
  - **검색** — retrieval + rerank 직후, persona ACL 와 같은 위치
  - **답변** — provider 응답 직후, persist 직전

규칙 스키마:

```python
class ModerationRule:
    category      = CharField()         # 욕설 · 대외비 · PII · 자체
    pattern_type  = CharField()         # KW (substring) | RE (regex)
    pattern       = CharField()
    scope         = CharField()         # 'upload,question,search,answer' 부분집합
    severity      = CharField()         # BLOCK / MASK / WARN
    is_active     = BooleanField()
    trigger_count = IntegerField()      # 운영 통계
```

severity → UI 매핑 (DESIGN.md 시그니쳐):

| severity | 의미 | UI |
|---|---|---|
| BLOCK | 차단 + 사용자에게 사유 + 다음 단계 안내 | warning border (빨강 배너 금지) |
| MASK | 텍스트 일부 `***` 로 치환 + citation 에 표기 | `[수정됨·N건]` chip |
| WARN | 통과시키되 사용자에게 알림 + log | info badge |

## 5 · 어떻게 측정·검증하나

- **trigger_count** — 운영자가 어떤 규칙이 살아있는지 확인 (Admin 카드)
- **false positive 검수** — `ModerationLog` 의 `WARN` 샘플링 → 운영자 검수 큐
- **실시간 테스트 패널** — 규칙 등록 전 샘플 입력으로 즉시 확인 (`backend/docs/learning/2026-05-28-b7c2-moderation-admin-ui.md` §3)
- **회귀 테스트** — `tests/test_moderation.py` 의 규칙 활성/비활성 토글로 baseline 유지

```python
# 실시간 테스트 패널 호출
POST /api/v1/moderation/rules/test/
{
    "rule_id": 42,
    "sample": "이번 분기 OKR 미달성 사유는...",
    "boundary": "answer"
}
→ { "matched": true, "action": "MASK", "preview": "이번 분기 *** 사유는..." }
```

## 6 · FAQ

:::qa q="Q. 4 경계 다 거치면 latency 안 쌓이나?"
A. 규칙 N 개, 입력 길이 M 자 → O(N·M) 최악. 실측 (60 규칙, 평균 입력 200 자): 4 경계 합산 +12 ms. 무시 가능. 규칙 1000 개 넘어가면 trie/aho-corasick 으로 교체.
:::

:::qa q="Q. KW (keyword) 와 RE (regex) 둘 다 필요한가?"
A. 필요. KW = 운영자가 단어 1개 등록 (가장 흔함). RE = "주민번호 형식" 같은 패턴. KW 만 두면 운영자가 regex 못 짜서 규칙 못 등록, RE 만 두면 단순 키워드도 regex 로 escape 해야 함.
:::

:::qa q="Q. 무성 드롭 정책의 근거는?"
A. 시스템 신뢰. 사용자가 답변 누락을 인지하지 못하면 "이 챗봇 모름" 으로 판단 → 다른 도구로 우회 → 정작 보안 효과 ↓. `[수정됨·N건]` 으로 *명시적 검열* 이라는 신호.
:::

:::qa q="Q. LLM 자체에 사전 학습된 정책이 있는데?"
A. LLM 정책 = 일반 위해 (욕설·성·폭력). 사내 모더레이션 = 도메인 (경쟁사명·내부 코드명·고객 PII). 둘은 직교. LLM 가드는 끌 수 없고, 우리 규칙은 운영자가 즉시 튜닝 가능.
:::

## 7 · 더 읽기

- [`backend/docs/features/moderation/learn.md`](../../backend/docs/features/moderation/learn.md) — Fasoo · MS Purview · Presidio 벤치마크 → 3-layer 결론
- [`backend/docs/learning/2026-05-28-b7c2-moderation-admin-ui.md`](../../backend/docs/learning/2026-05-28-b7c2-moderation-admin-ui.md) — 실시간 테스트 패널 구현 노트
- [Microsoft Presidio](https://microsoft.github.io/presidio/) — PII detection 오픈소스
- [NVIDIA NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) — LLM 출력 가드
