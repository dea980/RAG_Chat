# Ingest Test Samples

End-to-end 파이프라인 검증용 샘플 문서. fixtures (단위 테스트) 보다 크고
현실에 가까운 내용으로 구성.

## 파일 목록

| 파일 | 종류 | 출처 | 비고 |
|---|---|---|---|
| `galaxy_lineup.csv` | CSV (실제) | gsmarena.com | S25 / S25+ / S25 Ultra 풀스펙 |
| `galaxy_handbook.md` | Markdown (실제) | gsmarena + wikipedia | 헤딩 splitter 검증용 |
| `galaxy_faq.html` | HTML (실제) | gsmarena + wikipedia | HTML 헤딩 splitter 검증용 |
| `employee_rules.txt` | 텍스트 (합성) | — | 한국어 "제N조" 패턴, clause splitter |
| `annual_leave_policy.md` | Markdown (합성) | — | markdown heading + 표 splitter |

## 데이터 정확성

### 실제 데이터 (Galaxy 파일들)
2025-02-07 출시 직후 gsmarena.com 과 en.wikipedia.org 스펙 페이지에서
WebFetch 로 추출. 각 파일 하단/메타에 출처 URL 명시.

### 합성 데이터 (한국어 사규 파일들)
법령 사이트 (law.go.kr, moel.go.kr) 가 SPA 라 WebFetch 로 본문 추출 불가.
구조 (조 번호, 헤딩 계층) 만 실제 사규를 모방한 합성 텍스트.
clause / heading splitter 의 *분할 정확성* 검증이 목적이고,
내용 (조문 본문) 정확성은 검증 대상이 아니므로 충분.

진짜 한국어 공공 문서가 필요하면 (Phase 7-a HWP loader 검증):
- `chat/tests/ingest/fixtures/special/standard_employment_rules_2026.hwp`
  — 고용노동부 2026년 표준 취업규칙 (HWP 5.x, 277KB, 실제 정부 배포본)

## 사용

```python
from chat.ingest.pipeline import run_ingest
run_ingest("backend/data/samples/galaxy_lineup.csv")
```
