# Test Fixtures & Sample Data 인벤토리

> 2026-05-27 추가. Ingest layer loader/splitter/eval 검증용 데이터의 단일 소스.
> 합성 데이터와 실제 데이터를 명확히 구분.

---

## 1. 디렉토리 구조

```
backend/
├── chat/tests/ingest/fixtures/         # 단위 테스트용 (5KB 이하 미니멀)
│   ├── text/
│   │   ├── sample_rules.txt            # 한국어 "제N조" 패턴 (합성)
│   │   ├── sample_rules.html           # HTML h1/h2/h3 (합성)
│   │   ├── sample_handbook.md          # Markdown # / ## / ### (실제 S25 스펙 기반)
│   │   └── sample_galaxy.txt           # 평문 (실제 S25 스펙 기반)
│   ├── structured/
│   │   └── sample_3rows.csv            # CSV 5컬럼 3행 (실제 가격)
│   ├── special/                        # Phase 7-a 특수 포맷
│   │   └── standard_employment_rules_2026.hwp  # 실제 정부 HWP 5.x (277KB)
│   ├── ocr/                            # Phase 5 OCR
│   │   ├── sample_ko.png
│   │   ├── sample_en.png
│   │   └── sample_mixed.png
│   └── README.md
├── data/samples/                       # End-to-end 파이프라인용
│   ├── galaxy_lineup.csv               # S25/S25+/S25 Ultra 풀스펙 (gsmarena)
│   ├── galaxy_handbook.md              # 마크다운 핸드북 (gsmarena+wikipedia)
│   ├── galaxy_faq.html                 # HTML FAQ
│   ├── employee_rules.txt              # 한국어 사규 (합성)
│   ├── annual_leave_policy.md          # 연차 정책 (합성)
│   └── README.md
├── chat/tests/evals/
│   ├── dataset.jsonl                   # 기존 12문항 (Galaxy CSV 기반)
│   ├── dataset_galaxy_full.jsonl       # 신규 20문항 (실제 S25 스펙)
│   └── dataset_legal.jsonl             # 신규 15문항 (합성 사규)
└── scripts/
    └── build_ocr_fixtures.py           # OCR 이미지 재생성 (PIL only)
```

---

## 2. 데이터 정확성

| 카테고리 | 출처 | 검증 가능성 |
|---|---|---|
| Galaxy 스펙 (handbook.md, lineup.csv, faq.html, sample_galaxy.txt, OCR 이미지) | gsmarena.com (13610/13609/13322) + en.wikipedia.org | ✅ 실제 — Eval 정답으로 사용 가능 |
| HWP fixture | 고용노동부 2026년 표준 취업규칙 | ✅ 실제 정부 배포본 (공공누리) |
| 한국어 사규 텍스트 (sample_rules.txt/html, employee_rules.txt, annual_leave_policy.md) | — | ⚠️ 합성. 구조(`제N조` / 헤딩) 패턴 검증만 |

---

## 3. Eval Dataset

### dataset_galaxy_full.jsonl (20문항, 실제)
gsmarena/wikipedia 스펙 기반. 각 문항에 `source` 메타 포함 (예: `gsmarena_13610`).
RAG 답변 keyword 매칭으로 정답 검증 가능.

### dataset_legal.jsonl (15문항, 합성)
합성 사규 기반. 검색·청크 분할 정확성 측정용. **답변 사실성은 검증 불가**
(원본 자체가 합성이라 외부 사실과 다름). clause splitter 정확도, top-k recall
같은 메트릭만 의미 있음.

### dataset.jsonl (기존, 12문항)
기존 galaxy_s25_data.csv (7행) 기반. 그대로 유지.

---

## 4. OCR 이미지 재생성

```bash
cd Rag_Chat/backend
venv/bin/python scripts/build_ocr_fixtures.py
```

PIL 만 의존. macOS 시스템 폰트 (`AppleSDGothicNeo.ttc` / `Arial.ttf`) 사용.
다른 OS 는 `KO_FONT` / `EN_FONT` 경로 수정.

각 이미지의 ground-truth 텍스트는 스크립트 본문에 하드코딩 — OCR loader 가
추출한 텍스트와 비교할 때 그대로 사용.

---

## 5. 사용 예

### 단위 테스트
```python
from pathlib import Path
FIX = Path(__file__).parent / "fixtures"

def test_csv_loader_3rows():
    from chat.ingest.loaders.structured.csv import CsvLoader
    docs = list(CsvLoader().load(str(FIX / "structured" / "sample_3rows.csv")))
    assert len(docs) == 3
    assert "Galaxy S25" in docs[0].content
    assert docs[0].section == "row:0"
```

### End-to-end (Phase 6 ORM sink 이후)
```python
from chat.ingest.pipeline import ingest_path
ingest_path("backend/data/samples/galaxy_handbook.md")
```

### Eval 실행 (구현 예정)
```python
import json
with open("chat/tests/evals/dataset_galaxy_full.jsonl") as f:
    cases = [json.loads(line) for line in f]
for c in cases:
    # answer = rag_chat(c["question"])
    # missing = [k for k in c["expected_keywords"] if k not in answer]
    # if missing: log(c["id"], missing)
    ...
```

---

## 6. 안 한 것 (의도적)

- **PDF/DOCX fixture** — `reportlab`/`python-docx` 미설치. Phase 3 PDF/DOCX
  loader 구현 시 함께 추가 권장.
- **Galaxy S24/Z/A 라인업** — gsmarena 추출 가능하지만 본 세션엔 S25 시리즈
  (기본/Plus/Ultra) 만 작업. 필요 시 같은 방식 (WebFetch + CSV) 으로 확장.
- **한국어 법령 본문 텍스트** — law.go.kr / moel.go.kr 본문 페이지가 SPA
  (JavaScript 렌더링) 라 WebFetch 로 추출 실패. HWP 원본은 fixture 로 확보됨.
  텍스트가 필요해지면: (a) Phase 7-a HWP loader 완성 후 자체 추출,
  (b) 법령 OpenAPI 등록 후 호출.

---

## 7. 출처 URL 일괄

- [Samsung Galaxy S25 - GSMArena](https://www.gsmarena.com/samsung_galaxy_s25-13610.php)
- [Samsung Galaxy S25+ - GSMArena](https://www.gsmarena.com/samsung_galaxy_s25_plus-13609.php)
- [Samsung Galaxy S25 Ultra - GSMArena](https://www.gsmarena.com/samsung_galaxy_s25_ultra-13322.php)
- [Samsung Galaxy S25 - Wikipedia](https://en.wikipedia.org/wiki/Samsung_Galaxy_S25)
- [고용노동부 2026년 표준 취업규칙](https://www.moel.go.kr/policy/policydata/view.do?bbs_seq=20260200740)
