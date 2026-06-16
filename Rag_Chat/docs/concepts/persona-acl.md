---
title: Persona ACL (역할 기반 접근 제어)
slug: persona-acl
category: Architecture
level: 중급
order: 50
summary: 같은 질문이라도 사용자 역할·페르소나에 따라 검색 가능한 문서를 다르게 — 그리고 어떤 chunk가 가려졌는지 가시화.
prerequisites: []
related: [moderation-4boundary]
updated: 2026-06-16
---

## 1 · 무엇인가

:::definition term="용어" name="Persona ACL"
사용자의 역할(USER/MANAGER/ADMIN) · 부서 · 페르소나(영업/지원/기획) × 문서의 namespace · confidentiality label 조합으로 **retrieval 단계**에서 chunk 를 drop/mask 하는 권한 제어. 응답이 아니라 *검색 결과* 를 거르는 게 핵심.
:::

본 단락 — 사내 RAG 의 진짜 어려움은 "같은 질문, 다른 답" 이다. 영업이 "다음 분기 OKR" 을 물으면 자기 부서 OKR 만, ADMIN 은 전사. 응답 시점에 마스킹하면 늦다 — LLM 이 이미 그 chunk 를 봤다. **검색 시점**에 후보에서 빼야 한다.

## 2 · 비유로 이해하기

:::analogy title="회사 문서고 출입증"
직원이 문서고에 들어가서 "마케팅 자료" 를 찾는다. 사서가 그 사람의 **출입증** 을 본다.

- 일반 직원 → "마케팅 공개 자료" 선반만 안내
- 매니저 → "마케팅 공개 + 부서 내부" 선반
- ADMIN → 전부

찾고 나서 응접실에서 "이건 보면 안 된다" 가리는 게 아니라, **선반 자체를 안 보여준다**. 차이가 크다. 가린 자료 옆에 "이 영역에 1건 더 있었지만 권한 없음" 표시가 붙는다 (무성 드롭 금지).
:::

## 3 · 왜 중요한가

- **응답 시점 마스킹 = too late** — LLM 이 본 컨텍스트는 사실상 유출. 모델은 잊지 않는다
- **무성 드롭 = 신뢰 파괴** — chunk 가 사라진 사실을 사용자가 모르면 답이 일관성 없어 보임. "왜 모를까?" → 시스템 신뢰 ↓
- **citation ribbon 의 짝꿍** — `[수정됨·N건]` 으로 가시화. 사용자는 *권한 부족* 인지 *데이터 부재* 인지 구분 가능

:::callout warn title="흔한 함정"
LLM 프롬프트에 "이 chunk 는 보지 마세요" 라고 쓰는 건 ACL 이 아니다. 모델은 그걸 무시하거나 다른 표현으로 흘릴 수 있다. 권한은 *코드 게이트* 여야 한다.
:::

## 4 · 우리 시스템에서의 의미

- 코드: [`backend/chat/persona.py`](../../backend/chat/persona.py), `chat/models.py:User.persona`, `chat/pipeline/modules.py` 의 ACL filter
- 데이터: `User.role`, `User.department` (FK), `User.persona` × `RagData.namespace`, `confidentiality_label`
- 통합 위치: dense retrieve → rerank → **ACL filter** → moderation:SEARCH → LLM
- 가시화: citation chip ribbon 옆 `[수정됨·N건]` (`backend/docs/learning/2026-05-28-acl-filter-wiring.md` §5)

ACL 정책 예 (영업 페르소나):

| namespace × label | USER (영업) | MANAGER (영업팀장) | ADMIN |
|---|---|---|---|
| `product` × `public` | ✅ | ✅ | ✅ |
| `product` × `internal` | ✅ | ✅ | ✅ |
| `sales` × `team-confidential` | ✅ (자기 팀) | ✅ (자기 팀) | ✅ |
| `hr` × `*` | ❌ | ❌ | ✅ |
| `legal` × `*` | ❌ | ❌ (배정 시 ⚪) | ✅ |

## 5 · 어떻게 측정·검증하나

- **eval set 확장** — 각 질문에 `expected_visible_chunks[persona]` 라벨. persona × 질문 매트릭스
- **policy regression test** — `tests/test_persona_acl.py` — 영업 USER 가 HR chunk 를 보면 fail
- **citation parity** — ADMIN 이 본 chunk 와 USER 가 본 chunk 의 difference 가 audit log 에 일치하는지

```python
# pytest 예
def test_sales_user_cannot_see_hr_chunks(client, sales_user, hr_chunk):
    client.force_login(sales_user)
    resp = client.post("/api/v1/triple/chat/", {"question": "연차 정책"})
    assert hr_chunk.id not in [c["id"] for c in resp.data["citations"]]
    assert resp.data["redacted_count"] >= 1
```

## 6 · FAQ

:::qa q="Q. PostgreSQL row-level security (RLS) 로 하면 안 되나?"
A. 할 수 있다. 우리 구현은 ORM 단계에서 거르는데, 대규모 namespace 가 늘면 RLS 가 더 안전. 트레이드오프: RLS 는 디버깅이 까다롭고 superuser 로 우회 가능.
:::

:::qa q="Q. Reranker 후에 거르면 reranker 점수 낭비 아닌가?"
A. 약간 낭비 맞다. 하지만 ACL 을 **이전 단계**(dense retrieve) 에서 SQL WHERE 절로 처리하면 더 좋다. 현 구현은 retrieve 시 WHERE 절 + rerank 후 한 번 더 검증 (defense-in-depth).
:::

:::qa q="Q. persona 가 바뀌면 (USER → MANAGER 승진) 캐시는?"
A. Redis 세션 TTL 이 짧다 (5분). DB persona 변경 후 다음 요청에서 fresh load. 즉시 반영이 필요하면 session invalidate 트리거.
:::

:::qa q="Q. 가린 chunk 가 0건이면 표시 안 하나?"
A. 안 한다. 0건일 때 표시하면 noise. 1건 이상일 때만 `[수정됨·N건]`.
:::

## 7 · 더 읽기

- [`backend/docs/learning/2026-05-29-persona-security-design.md`](../../backend/docs/learning/2026-05-29-persona-security-design.md) — 우리 설계 결정 narrative
- [`backend/docs/learning/2026-05-28-acl-filter-wiring.md`](../../backend/docs/learning/2026-05-28-acl-filter-wiring.md) — citation 가시화 구현 노트
- [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — DB 단계 대안
- [Notion: Permission for RAG](https://www.notion.so/blog/ai-knowledge-management) — SaaS 사례
