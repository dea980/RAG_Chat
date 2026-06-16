# Phase 7-a — HWP Loader (yesterday T4 리서치 결과 받을 자리)

> **5분 진입 (다음 세션)** — yesterday T4 리서치 완료: [phase7a_hwp_research.md](phase7a_hwp_research.md). 결론 = **pyhwp 채택** + `six` 동반 설치 (setup.py 누락). libhwp Rust 패닉 / hwp-extract 본문 추출 불가 / LibreOffice 600MB 의존성 부담 → 모두 거부. 표/그림은 `<표>`·`<그림>` 플레이스홀더로 손실 → chunk metadata 에 `has_tables` 표기. AGPLv3 라이선스 → 외부 노출 시 재평가 필요.
>
> **상태**: 🔧 SKELETON — yesterday T4 에이전트가 HWP 라이브러리 *리서치만* 진행. 코드는 다음 세션이 결정 후 작성.
>
> T4 가 작성할 doc: [`phase7a_hwp_research.md`](phase7a_hwp_research.md) — 라이브러리 후보 비교 + 권고.
>
> 본 doc (`phase7a_hwp.md`) 는 *구현* 단계 진입 시 통합 노트가 될 자리.

---

## 1. 리서치 → 구현 흐름

```
T4 (다른 Claude)            다음 세션 (Codex 부활 or 다른 Claude)
   │                             │
   ▼                             ▼
phase7a_hwp_research.md  ───►  의사 결정  ───►  hwp.py loader 작성
   │                             │                  │
   라이브러리 비교 + 권고    사용자 채택       phase7a_hwp.md (본 doc)
   설치 부담 / 정확도 / 라이선스                  통합 노트
```

---

## 2. T4 가 답해야 할 질문 (사전 정의)

T4 의 결과 doc 가 다음을 다뤄야 본 phase 가 진행 가능:

### 라이브러리 후보
- [ ] `pyhwp` (HWP 5.x parser, Python)
- [ ] `hwp5txt` (pyhwp 의 CLI 추출 도구)
- [ ] `olefile` + 커스텀 (HWP 의 OLE 구조 직접 파싱)
- [ ] LibreOffice headless (`soffice --headless --convert-to txt`)
- [ ] (다른 후보 있으면)

### 비교 축
- [ ] **설치 난이도** — 순수 Python? 시스템 의존성? Java? .NET?
- [ ] **한국어 정확도** — 표준 취업규칙 fixture 로 실측
- [ ] **의존성 무게** — wheel size, 추가 시스템 패키지
- [ ] **라이선스** — MIT / GPL / 상업
- [ ] **유지보수 상태** — 마지막 커밋, issue 응답 속도, HWP 2014/2018 포맷 대응 여부
- [ ] **HWP/HWPX 구분** — HWP 5.x vs HWPX (XML 기반 신규 포맷) 지원 여부

### 실측 데이터
- [ ] Fixture: `backend/chat/tests/ingest/fixtures/special/standard_employment_rules_2026.hwp` (277KB, 고용노동부 2026 표준 취업규칙)
- [ ] 추출된 텍스트 길이
- [ ] 추출된 텍스트 sample 100자
- [ ] 표/이미지 처리 여부

### 권고
- [ ] **이걸로** + 이유 3줄
- [ ] **대안 B** (권고 실패 시 fallback)

---

## 3. 다음 세션 작업 (구현 단계, 작성 예정)

T4 권고 채택 후 작성:

```python
# backend/chat/ingest/loaders/text/hwp.py
from chat.ingest.base import BaseLoader, RawDoc
from chat.ingest.registry import register

@register(extensions=(".hwp", ".hwpx"), source_type="hwp")
class HWPLoader(BaseLoader):
    source_type = "hwp"

    def load(self, path: str) -> list[RawDoc]:
        # T4 권고 라이브러리 사용
        text = extract_hwp_text(path)
        return [RawDoc(
            content=text,
            source_file=path,
            source_type="hwp",
            metadata={"format": "hwp5" if path.endswith(".hwp") else "hwpx"},
        )]
```

---

## 4. 학습 메모 — 분류 4 의 본질 (작성 예정)

강의 7강 4분류 중 *분류 4* (전용 포맷). HWP 가 이 분류의 대표:

1. **사유 포맷의 비용** — HWP 는 한컴이 독점. 표준화 안 됨 → 모든 RAG 시스템이 별도 변환 필요.
2. **헬스케어/공공 도메인 필수** — 한국 공공기관 90%+ HWP. 영업/HR/법무 부서 RAG 는 우회 불가.
3. **변환 vs 직파싱 트레이드오프**:
   - 변환 (LibreOffice) — 의존성 무거움, 환경 설정 까다로움. 그러나 *지원 포맷 가장 넓음* (HWP 5.x, HWPX, 변형 모두).
   - 직파싱 (pyhwp) — 가볍지만 *HWP 버전 따라 깨질 수 있음*.
4. **HWPX 의 등장** — XML 기반 신규 포맷 (2010+). 분류 1 (텍스트 추출형) 에 가까움. 미래엔 분류 1 로 흡수 예상.
5. **CAD/dwg 와의 공통점** — 둘 다 사유 포맷. 같은 패턴: 라이브러리 비교 → 권고 → 변환 단계 + ingest loader 작성.

---

## 5. 안 된 것 (의도적, 별도 phase) (작성 예정)

- **HWP 내 표 추출** — 텍스트만 우선. 표는 *분류 3 (정형)* 로 별도 라우팅 후 SQL 적용 (Phase 8 ?)
- **HWP 내 이미지** — Phase 5 OCR 와 연계 후속 작업
- **HWPX 별도 loader** — 일단 같은 loader 가 둘 다 처리. 동작 검증 후 분리 결정
- **CAD/dwg loader** — Phase 7-b 별도

---

## 6. 다음 세션 즉시 처리할 것 (작성 예정)

- [ ] T4 의 `phase7a_hwp_research.md` 결과 검토
- [ ] 라이브러리 1개 채택 → `requirements.txt` 추가
- [ ] (LibreOffice 채택 시) docker-compose 에 system 패키지 추가
- [ ] `hwp.py` loader 작성
- [ ] `loaders/__init__.py` import 추가
- [ ] Test: 표준 취업규칙 fixture 로 `load()` 호출 + 39조 ("연차 휴가") 추출 확인

---

## 관련 문서

- [`phase7a_hwp_research.md`](phase7a_hwp_research.md) — T4 가 작성할 라이브러리 비교 (리서치 완료 후 채워짐)
- [`../../architecture/ingest_layer.md`](../../architecture/ingest_layer.md) — 분류 4 전용 포맷 설계
- [`../../sessions/2026-05-27-night-parallel.md`](../../sessions/2026-05-27-night-parallel.md) — T4 가 어떤 분배 하에서 진행됐는지
- [`../../guides/test_fixtures.md`](../../guides/test_fixtures.md) — HWP fixture 위치
- [`phase5_ocr.md`](phase5_ocr.md) — 분류 2 처리 (이미지 → HWP 내 이미지 추출 시 연계)
