# Work Distribution — Claude Code · Codex · 다른 Claude

> Phase 1 (ingest layer skeleton) 이 깔린 상태에서 Phase 2~Phase 8 까지 어떻게
> 세 도구에 분배할지 정리. 각 도구의 강점·약점·접근권한을 기준으로 분담.
>
> **2026-05-27 갱신**: 다음 작업은 Celery 비동기 ingest 가 아니라
> **Phase 2 Manifest** 이다. Celery/Redis 락/beat 는 Upload API 또는 외부
> 트리거가 생기는 Phase 8 에서 적용한다.

---

## 1. 도구별 강점 / 제약 매트릭스

| 항목 | Claude Code (현 세션) | Codex CLI | 다른 Claude (Claude.ai / 별도 세션) |
|---|---|---|---|
| 레포 접근 | ✅ 풀 접근 (Read/Edit/Bash) | ✅ 풀 접근 | 부분 — 파일 첨부/복붙 의존 |
| Django ORM/migration | ✅ 강함 | ⚠️ 가능하나 cross-file 변경에서 컨텍스트 부담 | ⚠️ 레포 접근 제약상 검토만 |
| 단일 파일 알고리즘 | ✅ | ✅✅ 가장 강함 | ⚠️ |
| 정규식·파싱 정확도 | ✅ | ✅✅ "200 IQ" 강점 | ✅ |
| 디자인/리서치 | ✅ | ⚠️ 약함 | ✅✅ 가장 강함 |
| 외부 라이브러리 사용 결정 | ✅ web search 가능 | ⚠️ 제한적 | ✅ |
| UI prototyping (Streamlit) | ✅ | ⚠️ | ✅ |
| 장시간 작업 컨텍스트 보존 | ✅ (1M 토큰) | ✅ | ⚠️ 세션 끊김 위험 |

---

## 2. 분배안 — Phase 2 ~ Phase 8

### Claude Code (나)
**역할: 레포 일관성·통합·Django 영역**

- **Phase 2 — IngestManifest** (모델 + 마이그레이션 + dedup 로직)
  - `chat/models.py` 에 `IngestManifest` 추가
  - `chat/migrations/000X_ingest_manifest.py`
  - `chat/ingest/manifest.py` — SHA256 헬퍼
  - `pipeline.py` 에 dedup 분기 통합
  - 기존 88청크 누적 데이터 정리 스크립트
- **Phase 6 — ORM Sink + galaxy_s25_data 이전**
  - `chat/ingest/sinks/knowledge_orm.py`
  - CSV → `knowledge_product` 마이그레이션 + `seed_demo` 통합
  - `Chroma` sink 에는 자연어 description 만 가도록 조정
- **build_vectors / build_vector_store 중복 제거**
  - `chat/build_vector_store.py` 삭제 또는 deprecated 경고
  - 관련 테스트 갱신
- **CI 통합**
  - 새 ingest layer 가 기존 `chunk_experiment` A/B 와 호환되도록 어댑터
- **PR 리뷰 — Codex/다른 Claude 가 만든 loader 들의 통합 검토**
- **Phase 8 — Upload API + Async ingest** (요구사항이 생길 때)
  - Admin/Upload API
  - `ingest_file_task` Celery task
  - Redis in-progress 락 + 진행률 캐시
  - Celery beat 디렉토리 스캔

이유: cross-file 변경 + ORM + migration + 기존 코드 일관성 유지가 필요한 영역.

---

### Codex CLI
**역할: 단일 파일 단위로 완결되는 loader/splitter 구현**

**핵심 담당: 단일 파일 loader (PDF/DOCX/HTML/TXT/HWP), splitter,
clause/heading 정규식 구현**

| Phase | 입력/전략 | 구현 파일 | 핵심 처리 | 테스트 포인트 |
|---|---|---|---|---|
| Phase 3 | PDF | `chat/ingest/loaders/text/pdf.py` | `PyPDFLoader` 래핑, page 단위 `RawDoc` 반환 | page metadata, 빈 페이지 skip, 첫/마지막 페이지 content |
| Phase 3 | DOCX | `chat/ingest/loaders/text/docx.py` | `Docx2txtLoader` 래핑, 문단 텍스트 정규화 | source_type, 줄바꿈 보존, 빈 문서 처리 |
| Phase 3 | HTML | `chat/ingest/loaders/text/html.py` | `BeautifulSoup` 기반 본문 추출, script/style 제거 | heading 보존, 불필요 태그 제거, HTML entity 처리 |
| Phase 3 | TXT | `chat/ingest/loaders/text/txt.py` | plain text 읽기, encoding fallback | UTF-8/CP949, 빈 파일, 큰 파일 일부 검증 |
| Phase 4 | Clause splitter | `chat/ingest/splitters/clause.py` | `"제 N 조"` / `"Article N"` 정규식, 조항 단위 분리 | 조 번호 section, 누락/중복 조항, 전문/부칙 edge case |
| Phase 4 | Heading splitter | `chat/ingest/splitters/heading.py` | `MarkdownHeaderTextSplitter` 래핑 + HTML heading 구조 반영 | heading hierarchy, section metadata, 본문 없는 heading |
| Phase 7-a | HWP | `chat/ingest/loaders/special/hwp.py` | LibreOffice headless 변환, 실패 시 `hwp5txt` CLI fallback | timeout, temp dir 정리, 외부 binary 없음, 변환 실패 메시지 |

이유: 각 loader/splitter 가 self-contained (입력 path → RawDoc[]). 정규식·파싱
정확도가 핵심인 영역에서 Codex 강점이 살아남. 단위 테스트와 짝지어 PR.

**제공할 컨텍스트** (Codex 에 붙여줄 것):
- `chat/ingest/base.py` (RawDoc / Protocol 정의)
- `chat/ingest/registry.py` (`@register` 패턴)
- 같은 분류 기존 loader 1개 (예: csv.py) — 코드 스타일 참조
- 테스트 작성 규칙 (`chat/tests/` 컨벤션 1~2개)

**Fixture 준비 상태** (2026-05-27):
- **HWP** (Phase 7-a): `chat/tests/ingest/fixtures/special/standard_employment_rules_2026.hwp`
  — 고용노동부 2026년 표준 취업규칙 실제 파일 (277KB). Loader 구현 즉시 검증 가능.
- **Clause / heading 패턴** (Phase 4 검증용): `chat/tests/ingest/fixtures/text/sample_rules.txt`
  (한국어 "제N조"), `sample_rules.html` (HTML h1/h2/h3), `sample_handbook.md` (Markdown 헤딩).
- **PDF/DOCX** (Phase 3): 미준비 — loader 구현 시 `reportlab`/`python-docx` 함께 설치하며 추가.
- 인벤토리·출처: [test_fixtures.md](../guides/test_fixtures.md).

---

### 다른 Claude (Claude.ai 또는 별도 세션)
**역할: 리서치·디자인·UI/Notebook**

- **Phase 5 — OCR Loader** (리서치 + 구현)
  - pytesseract vs PaddleOCR vs Azure Document Intelligence 비교
  - 한국어 모델 정확도 / 표 인식 / 비용 trade-off 리포트
  - 선택 후 `chat/ingest/loaders/ocr/image.py`, `scanned_pdf.py` 구현
  - 의존성을 optional extra 로 분리 (`requirements-ocr.txt`)
- **Chunking Testing Page** (`chunk_testing_page.md` 의 1~3 단계)
  - `backend/notebooks/chunk_lab.ipynb` — 청크 길이 분포, UMAP 시각화
  - Streamlit `frontend/pages/chunk_lab.py` 프로토타입
  - 필요한 backend 엔드포인트 `/api/v1/ingest/preview` 스펙 작성 (구현은 Claude Code 가)
- **Eval 확장**
  - 강의 사례 (사규 / 연차) 시나리오 12문항을 `chat/tests/evals/dataset_legal.jsonl` 로 추가
  - 임베딩 모델 A/B (text-embedding-004 vs bge-m3 vs e5) — 리포트 작성
- **HWP 외 분류 4 리서치**
  - CAD 도면 처리 — 강의 예제 코드 분석 + 우리 프로젝트 도입 가능성 검토
  - 오디오/영상 ingest 가 필요해지는 시점 판단

이유: 리서치 비중 큰 작업 + UI prototyping. 레포 접근이 부분이어도 디자인
산출물 위주라 영향 작음. Claude Code 가 그 산출물을 받아 통합.

**제공할 컨텍스트**:
- `ingest_layer.md` + `chunk_testing_page.md` 전문
- `ingest_phase1_skeleton.md` (현재 layer 상태)
- 기존 `chunk_experiment.md` (현재 A/B 결과)

---

## 3. 의존성·순서

```
[Claude Code Phase 2: Manifest]
         │
         ├─► [Codex Phase 3: text loaders]  ──► PR 리뷰 (Claude Code)
         │                                          │
         ├─► [Codex Phase 4: splitters]    ──► PR 리뷰 (Claude Code)
         │                                          │
         ├─► [다른 Claude: OCR research]   ──► [Codex/다른 Claude: OCR 구현]
         │
         ├─► [Claude Code Phase 6: ORM sink + seed]
         │
         └─► [다른 Claude: chunk lab notebook + streamlit]
                       │
                       └─► Claude Code: /api/v1/ingest/preview 엔드포인트
```

**Phase 2 (Manifest) 가 모든 후속 작업의 전제** — 중복 적재 방지 없이는
Codex/다른 Claude 가 만든 loader 를 실제로 돌릴 때 Chroma 가 계속 오염됨.
Claude Code 가 가장 먼저 Phase 2 마치고, 그 다음 병렬 분배.

Async ingest 는 이 그래프의 선행 작업이 아니다. Upload API/외부 자동 인입/
동시 업로드 중 하나가 실제 요구사항이 될 때 Phase 8 로 별도 실행한다.

---

## 4. 인터페이스 계약 (각 도구가 지켜야 할 것)

세 도구 모두 다음 계약을 지키면 통합이 깔끔해짐:

### Loader 계약
```python
@register
class FooLoader:
    extensions = (".foo",)
    source_type = "foo"

    def load(self, path: str) -> Iterable[RawDoc]:
        # 반드시 RawDoc(content, source_file, source_type, ...) yield
        ...
```
- `RawDoc.content` 는 검색 대상 텍스트만 — 메타데이터 키를 본문에 섞지 말 것
- 페이지/섹션 식별자는 `page` / `section` 필드 사용
- nested dict 는 `metadata['fields']` 에 모아 두기 (Chroma sink 가 폐기해도
  ORM sink 가 활용 가능)

### Splitter 계약
```python
class FooSplitter:
    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        # chunk_index, splitter 이름을 metadata 에 추가
        # source_file, source_type, page, section 은 보존
        ...
```

### 테스트 계약
- 각 loader: `chat/tests/ingest/test_loader_<name>.py`
- 픽스처: `chat/tests/ingest/fixtures/<sample>.<ext>` — 5KB 이하 미니멀
- 검증: 청크 수, source_type, 첫/마지막 chunk content 부분 매칭

---

## 5. 비-분배 (혼자 결정해야 할 것)

다음은 분배 대상이 아니라 사람이 결정해야 함:

- **OCR 솔루션 최종 선택** — 비용·보안(사내 기밀)·정확도 trade-off
- **임베딩 모델 변경 여부** — 한국어 약점 vs 호환성 (기존 Chroma collection 재빌드 필요)
- **분류 3 ORM 이전 범위** — 어디까지 SQL 라우팅으로 갈지 (8강 오케스트레이션 영역)
- **HWP 처리 방식** — 변환 단계 (LibreOffice 도입) vs 사전 변환 정책

이 결정들은 다른 Claude 가 리서치 리포트 내놓으면 그걸 보고 사람이 결정 →
Claude Code 가 구현.

---

## 6. 협업 시 주의

- **branch 분리** — 도구마다 다른 branch (`feature/loader-pdf`,
  `feature/loader-hwp` 등). main 머지는 Claude Code 가 일괄.
- **import 충돌** — loaders/__init__.py 에 새 sub-package 추가하는 작업은
  Claude Code 가 일괄 정리 (병합 충돌 최소화).
- **테스트 fixture** — 큰 binary 는 LFS 또는 별도 디렉토리. 1MB 이상 PDF는
  fixture 에 두지 말 것.
- **외부 binary** — HWP 의 LibreOffice 같은 시스템 의존은 README 의
  "How to Run" 섹션에 명시 추가 (Claude Code 가 담당).
