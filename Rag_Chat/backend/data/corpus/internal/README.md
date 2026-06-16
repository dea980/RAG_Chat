# internal_only — 의도적으로 비어있는 디렉토리

## 이 디렉토리에 무엇이 들어가나?

**아무것도 들어가지 않는다.**

`audience_tier=internal_only` 로 분류되는 데이터는 다음과 같다:

- 마진율, 매장 인센티브
- 매장 KPI, 매출 목표 vs 실적
- 기업 견적 단가, 임대 계약 조건
- 통신사 보조금표 (수시 변동, 비공개)
- 영업 인센티브, 성과급 기준

이 정보들은 **이 repo 에 절대 들어오지 않는다.**

## 실제 저장 위치 (이 repo 밖)

| 데이터 | 사는 곳 |
|---|---|
| 마진율, 단가 | 사내 ERP (SAP) |
| 매장 KPI | 사내 BI (Tableau / PowerBI) |
| 견적 정보 | Salesforce / CRM |
| 영업 인센티브 | HR 시스템 |
| 통신사 보조금표 | 영업 운영팀 SharePoint Excel |

## 왜 디렉토리만 두는가?

신호용. 다음 3 가지를 분명히 한다:

1. **`infer_tier()` 매핑 안전장치** — 누가 실수로 internal 파일을 여기 떨어뜨려도
   `build_vectors` 가 `internal/` 경로 보고 인덱싱 skip.
2. **`.gitignore` 안전장치** — repo 의 `.gitignore` 에 `backend/data/corpus/internal/*` 추가됨.
   실수로 commit 시도해도 git 이 막음.
3. **문서화 신호** — 이 README 가 "여기 코퍼스 아님" 을 명시.

## 챗봇이 internal 정보 요청을 받으면

```
"마진율 정보는 사내 ERP(SAP) 에서 조회 가능합니다.
챗봇은 공개 정보만 제공합니다.
바로 가기: [내부 SAP 링크]"
```

- 추론으로 만들어낼 수 없음 (LLM 이 본 적 없음).
- escalation_attempt 로그 기록 (운영자가 패턴 추적).

## 관련 문서

- [페르소나 × 보안 통합 설계](../../docs/learning/2026-05-29-persona-security-design.md)
- 안전 원칙: 인덱싱 차단 > 검색 필터 > 답변 마스킹
