# Learning Notes — Index

> 작업 완료마다 남기는 학습 문서 (CLAUDE.md 규칙). 주니어 개발자가 읽고 이해할 수 있도록 비유 + 코드 + 데이터 흐름 + 연습 문제.
>
> 같은 토픽 내에서는 시간 순. 새 노트 추가 시 본 인덱스에 한 줄 추가.

---

## Auth · RBAC (B 시리즈)

| 날짜 | 노트 | 다룬 것 |
|---|---|---|
| 2026-05-28 | [b1-abstract-base-user](2026-05-28-b1-abstract-base-user.md) | `AbstractBaseUser` 로 chat.User 재정의, role · department FK |
| 2026-05-28 | [b2-seed-test-users](2026-05-28-b2-seed-test-users.md) | management command 로 테스트 계정 시드 |
| 2026-05-28 | [b3-login-logout](2026-05-28-b3-login-logout.md) | 세션 기반 로그인/로그아웃 endpoint |
| 2026-05-28 | [b4-chat-auth-gate](2026-05-28-b4-chat-auth-gate.md) | `ChatAPIView` 에 `IsAuthenticated` 적용 |
| 2026-05-28 | [b5-streamlit-login](2026-05-28-b5-streamlit-login.md) | Streamlit 측 로그인 플로우 + 쿠키 |
| 2026-05-28 | [b6-rbac-permission](2026-05-28-b6-rbac-permission.md) | DRF permission class 로 USER/MANAGER/ADMIN 분리 |

## Moderation (B7 + C 시리즈)

| 날짜 | 노트 | 다룬 것 |
|---|---|---|
| 2026-05-28 | [b7-4boundary-keyword-filter](2026-05-28-b7-4boundary-keyword-filter.md) | 4 경계 keyword 필터 파이프라인 hook |
| 2026-05-28 | [b7c2-moderation-admin-ui](2026-05-28-b7c2-moderation-admin-ui.md) | 운영자 Admin UI + 실시간 테스트 패널 |
| 2026-05-28 | [c3-test-suite-repair](2026-05-28-c3-test-suite-repair.md) | legacy User/patch 경로 복구 + ONNX 부재 시 skip |
| 2026-05-28 | [c4-forbidden-words-starter-seed](2026-05-28-c4-forbidden-words-starter-seed.md) | idempotent seed (재실행 안전) |
| 2026-05-28 | [c5-regex-patterns](2026-05-28-c5-regex-patterns.md) | KW + RE 둘 다 쓰는 pattern_type 도입 |
| 2026-05-28 | [c7-block-next-steps](2026-05-28-c7-block-next-steps.md) | BLOCK 응답에 next_steps + amber ribbon UI |

→ 개념 정리: [docs/concepts/moderation-4boundary.md](../../../docs/concepts/moderation-4boundary.md)

## Retrieval · IR

| 날짜 | 노트 | 다룬 것 |
|---|---|---|
| 2026-05-28 | [pgvector-migration](2026-05-28-pgvector-migration.md) | Chroma → Postgres pgvector |
| 2026-05-29 | [ir-rag-concepts](2026-05-29-ir-rag-concepts.md) | Recall@K, MRR, nDCG 개념 도입 |
| 2026-05-29 | [ir-improvement-plan](2026-05-29-ir-improvement-plan.md) | 단기/중기 retrieval 개선 plan |
| 2026-05-29 | [embedding-eval-harness](2026-05-29-embedding-eval-harness.md) | labeled YAML dataset + eval CLI |
| 2026-05-29 | [faiss-eval-harness](2026-05-29-faiss-eval-harness.md) | FAISS backend 측 평가 도구 |

→ 개념 정리: [docs/concepts/reranker.md](../../../docs/concepts/reranker.md) · [embedding-eval.md](../../../docs/concepts/embedding-eval.md) · [ir-metrics.md](../../../docs/concepts/ir-metrics.md)

## Persona ACL · Security

| 날짜 | 노트 | 다룬 것 |
|---|---|---|
| 2026-05-28 | [acl-filter-wiring](2026-05-28-acl-filter-wiring.md) | retrieval 후 ACL filter + `[수정됨·N건]` 가시화 |
| 2026-05-29 | [persona-security-design](2026-05-29-persona-security-design.md) | persona × namespace × confidentiality 설계 |
| 2026-05-29 | [sales-persona-analysis](2026-05-29-sales-persona-analysis.md) | 영업 페르소나의 실제 질의 패턴 분석 |
| 2026-05-31 | [doc-collection-namespace](2026-05-31-doc-collection-namespace.md) | 문서 collection → namespace 매핑 |

→ 개념 정리: [docs/concepts/persona-acl.md](../../../docs/concepts/persona-acl.md)

## Labs · Tooling

| 날짜 | 노트 | 다룬 것 |
|---|---|---|
| 2026-05-28 | [comparison-labs-extend](2026-05-28-comparison-labs-extend.md) | chat-compare + embedding pair-compare endpoint |
| 2026-05-29 | [token-lab-test-sets](2026-05-29-token-lab-test-sets.md) | 모델·언어별 토큰화 비교 test set |

---

## 새 노트 작성 규칙 (CLAUDE.md 발췌)

- 파일명: `YYYY-MM-DD-<slug>.md`
- 대상: 이 코드를 처음 보는 주니어 개발자
- 필수 섹션:
  1. 한 줄 요약
  2. 비유 (회사 문서고 출입증 / 우편함 등)
  3. 왜 이게 필요한가 (이전 방식 한계 vs 새 방식 이점)
  4. 핵심 코드 (5 줄 이내 + 주석)
  5. 데이터 흐름 (화살표 다이어그램)
  6. 확인 방법
  7. 연습 문제 (1~2개)

작성 후 본 인덱스 해당 토픽 표에 한 줄 추가.
