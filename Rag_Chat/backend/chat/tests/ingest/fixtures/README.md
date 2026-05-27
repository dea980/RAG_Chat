# Ingest Fixtures

Loader/Splitter 단위 테스트용 미니멀 샘플. 각 파일 5KB 이하.

## 디렉토리 구조

```
fixtures/
├── text/                       # Phase 3 text loaders
│   ├── sample_rules.txt        # 한국어 "제N조" 패턴 — clause splitter (합성)
│   ├── sample_rules.html       # h1/h2/h3 구조 — HTML heading splitter (합성)
│   ├── sample_handbook.md      # # / ## / ### 구조 — markdown heading (실제 스펙 기반)
│   └── sample_galaxy.txt       # 평문 단일 문단 — recursive splitter (실제 스펙 기반)
├── structured/
│   └── sample_3rows.csv        # 5컬럼 3행 — CSV loader (실제 가격·스펙)
├── special/                    # Phase 7-a 특수 포맷
│   └── standard_employment_rules_2026.hwp  # 실제 정부 배포 HWP (277KB)
└── ocr/                        # Phase 5 OCR — scripts/build_ocr_fixtures.py 가 생성
    ├── sample_ko.png           # 한국어 텍스트 (실제 S25 스펙)
    ├── sample_en.png           # 영어 텍스트 (실제 S25 스펙)
    └── sample_mixed.png        # 한국어 + 영어 혼합
```

## 출처

### 실제 데이터
- **Galaxy 스펙 (handbook.md, galaxy.txt, 3rows.csv, OCR 이미지)**
  → gsmarena.com (S25: 13610, S25+: 13609, S25 Ultra: 13322) + en.wikipedia.org
  → 2025-02-07 출시 기준
- **standard_employment_rules_2026.hwp**
  → 고용노동부 2026년 표준 취업규칙 (https://www.moel.go.kr/policy/policydata/view.do?bbs_seq=20260200740)
  → 공공누리 정책자료실 배포본

### 합성 데이터
- **sample_rules.txt / sample_rules.html** — 한국어 사규 형식만 모방.
  법령 사이트가 SPA 라 본문 추출 불가하여 구조 검증용으로만 사용.

## 사용 예 (테스트)

```python
from pathlib import Path
FIXTURES = Path(__file__).parent / "fixtures"

def test_csv_loader():
    docs = list(CsvLoader().load(str(FIXTURES / "structured" / "sample_3rows.csv")))
    assert len(docs) == 3
    assert docs[0].source_type == "csv"
    assert "Phantom Black" in docs[0].content
```

## OCR 이미지 재생성

```bash
cd Rag_Chat/backend
venv/bin/python scripts/build_ocr_fixtures.py
```

PIL 만 의존. macOS 시스템 폰트 사용 (AppleSDGothicNeo / AppleGothic).
