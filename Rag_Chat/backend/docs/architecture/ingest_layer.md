# Ingest Layer 설계

> 학습용 설계 문서. RAG 파이프라인에서 "청킹 → 임베딩 → 검색" 앞단의
> **데이터 수집·정규화 계층(Ingestion Layer)** 을 어떻게 구성할지 정리한다.
> 7강(RAG) 인제스천 분류 + 현재 코드 상태를 기준으로 갱신.
>
> **현재 상태 (2026-05-27)**: Phase 1 skeleton 은 구현됨.
> `chat/ingest/` 패키지, CSV/Excel loader, row/recursive splitter, Chroma sink,
> `build_vectors` 의 ingest layer 위임까지 들어가 있다. 아직 없는 것은
> Phase 2 manifest/dedup, 텍스트·OCR·HWP loader, ORM sink, Upload API 이다.

---

## 1. 왜 ingest layer가 필요한가

대부분의 RAG 튜토리얼은 "이미 텍스트가 준비된 상태"에서 시작한다.
실제 기업 데이터는 그렇지 않다.

- 청킹은 **텍스트가 이미 준비됐을 때만** 작동한다.
- 임베딩·검색이 다루는 것은 결국 "의미를 담은 텍스트, 또는 벡터화 가능한 표현".
- 즉 RAG 의 **진짜 1단계**는 *"우리 데이터를 어떻게 검색 가능한 표현으로 바꿀 것인가"* 이다.

이 단계가 `ingest layer` 또는 `data ingestion & normalization layer`.

이전에는 `chat/build_vector_store.py` + `chat/management/commands/build_vectors.py`
두 군데에 CSV/XLSX 처리 로직이 흩어져 있었다. 지금은 Phase 1 으로
`chat/ingest/` 계층이 생겼고, `build_vectors.py` 는 registry 기반
`ingest_path()` 호출자로 축소됐다.

남은 핵심 문제는 **멱등성**이다. `Chroma.from_documents` 는 같은
persist directory 에 append 하므로, 같은 파일을 반복 ingest 하면 중복 청크가
쌓인다. 따라서 다음 작업은 Celery 가 아니라 Phase 2 manifest 이다.

---

## 2. 데이터 4분류 (강의 프레임)

| 분류 | 예시 | 처리 전략 | 이 프로젝트 매핑 |
|---|---|---|---|
| **1. 텍스트 추출형** | PDF, DOCX, HTML, TXT, MD | 텍스트 그대로 추출 → 청킹 | 사규/규정/매뉴얼 — 현재 없음 |
| **2. OCR 필요형** | 스캔 PDF, 이미지(JPG/PNG) | OCR로 글자 인식 → 분류 1 경로로 합류 | 영업팀이 종이 가격표 스캔해서 올릴 가능성 |
| **3. 구조화 데이터** | CSV, Excel, RDB, ERP | **의미 검색이 아닌 정확 조회(SQL)** 가 더 맞음. RAG는 보조 | `galaxy_s25_data.csv` — 현재 RAG로 강제 처리 중. 8강 오케스트레이션 영역 |
| **4. 전용 포맷** | HWP, CAD, 오디오, 도면, 영상 | 포맷별 전용 변환 (메타데이터 + 비전/구조 추출) | 한국 기업이면 HWP 필수. CAD는 건설/인테리어 |

### 분류 3가 특히 중요한 이유

> "작년 4분기 매출 알려줘" 같은 질문은 의미 검색이 아니라 **SQL 쿼리** 문제다.
> 무리하게 RAG로 처리하기보다는 검색 단계에서 SQL 도구를 호출하도록
> **라우팅**하는 게 낫다. — 7강

현재 `galaxy_s25_data.csv` 는 8행짜리 표인데 통째로 임베딩 되어 있다.
"512GB 모델 가격 알려줘" 같은 질문은 `WHERE storage='512GB'` 가 정답이지
유사도 검색이 아니다. → 이 부분은 **knowledge_product 모델** (이미 존재) 로
이전하고, RAG corpus 에는 "텍스트 설명" 컬럼만 남기는 게 맞다.

---

## 3. Layer 구조

```
backend/chat/ingest/
  __init__.py
  base.py              # BaseLoader / BaseSplitter / RawDoc 인터페이스
  registry.py          # 확장자/MIME → loader 매핑 (플러그인 등록)
  manifest.py          # Phase 2 예정: SHA256 기반 dedup, 재인덱싱 방지
  pipeline.py          # source → loader → splitter → embedder → sink 오케스트레이션

  loaders/
    text/              # Phase 3 예정
      pdf.py           # PyPDFLoader 래핑
      docx.py
      html.py
      txt.py
    ocr/               # Phase 5 예정
      image.py         # pytesseract / PaddleOCR
      scanned_pdf.py   # 텍스트가 없으면 OCR로 폴백
    structured/
      csv.py           # → ORM sink + Chroma sink 분기
      excel.py
    special/           # Phase 7 예정
      hwp.py           # LibreOffice headless 변환 → txt
      cad.py           # 강의 예제: 메타데이터 + 비전 2-경로

  splitters/
    recursive.py       # 기본 길이 기반 (RecursiveCharacterTextSplitter)
    heading.py         # ✅ Markdown heading 계층 단위 (Phase 4, opt-in)
    clause.py          # ✅ 법규/사규 "제 N 조"/"Article N" 단위 (Phase 4, opt-in)
    row.py             # 표 1행 = 1청크

  sinks/
    chroma.py          # 벡터 스토어
    knowledge_orm.py   # Phase 6 예정: Product/Department/Contact 모델
    ragdata_orm.py     # 선택: 검색 스냅샷용 RagData
```

### 동작 순서

```
1. source     : 파일 경로 / S3 키 / 업로드 API
2. registry   : 확장자/MIME 보고 loader 결정
3. loader     : RawDoc[] 반환 (page_content + 표준 metadata)
4. manifest   : Phase 2 부터 동일 SHA256 처리 여부 확인 → skip 또는 진행
5. splitter   : 포맷별로 결정된 splitter 적용
6. embedder   : provider_manager 로 위임 (이미 존재하는 추상화)
7. sink       : Chroma + (선택적으로) ORM
8. manifest   : Phase 2 부터 처리 완료 기록
```

---

## 4. 인터페이스 (최소)

```python
# base.py
from dataclasses import dataclass, field
from typing import Iterable, Protocol

@dataclass
class RawDoc:
    content: str
    source_file: str          # 절대경로 또는 S3 URI
    source_type: str          # "pdf" | "docx" | "csv" | "hwp" | ...
    page: int | None = None   # PDF/PPT 등
    section: str | None = None  # heading / 조항번호
    metadata: dict = field(default_factory=dict)  # 자유 확장

class BaseLoader(Protocol):
    extensions: tuple[str, ...]  # (".pdf",)
    def load(self, path: str) -> Iterable[RawDoc]: ...

class BaseSplitter(Protocol):
    def split(self, doc: RawDoc) -> Iterable[RawDoc]: ...
```

### 메타데이터 표준 (Chroma 에 들어가는 키)

| 키 | 필수 | 설명 |
|---|---|---|
| `source_file` | ✅ | 원본 파일 경로/URI |
| `source_type` | ✅ | 분류용 (`pdf`, `csv`, `hwp` ...) |
| `doc_sha256` | Phase 2 | manifest 추적용 |
| `page` | optional | PDF/PPT |
| `section` | optional | "제39조" / heading |
| `chunk_index` | Phase 2 | splitter 출력 순서 |
| `ingested_at` | Phase 2 | ISO timestamp |
| `data_id` | optional | RagData FK 가 의미 있을 때 |

Phase 1 CSV/Excel loader 는 CSV 컬럼 원본을 `metadata["fields"]` 에 보존한다.
Chroma 는 nested metadata 를 받지 못하므로 `ChromaSink` 에서 scalar key 만
평탄화해 저장한다. `fields` 는 Phase 6 ORM sink 가 활용할 데이터로 남긴다.

---

## 5. 청킹 전략 — 포맷별 분기

| 데이터 | splitter | 이유 |
|---|---|---|
| PDF/DOCX 일반 문서 | `RecursiveCharacterTextSplitter` (200~500자, overlap 50) | 강의: 200/500/1000 비교에서 500이 안정적 |
| 사규/법규 PDF | `clause.py` — "제 N 조" / "Article N" regex | 강사가 39조 정답 못 찾다가 **조항 단위로 바꾸고** 찾음 |
| Markdown/HTML | `heading.py` — `MarkdownHeaderTextSplitter` | 구조가 살아있는 입력은 구조를 보존 |
| CSV/Excel | `row.py` — 1행 1청크 | 표는 행 단위가 의미의 최소 단위 |
| HWP | 변환 후 PDF/Markdown 로 처리 | HWP 자체 파싱 불안정 |
| CAD | metadata 추출 + LLM이 생성한 "의미 문장" | 강의 예제 그대로 — 2-경로 |

청크 사이즈는 **고정값 하드코딩 금지**. `chunk_experiment.md` 의 A/B 결과
(150자가 recall@5 0.789 → 0.833) 가 이미 환경변수로 제어되므로 splitter
선택 시 그 값 그대로 받아쓰면 된다.

---

## 6. Sink 분기 — Chroma vs ORM

분류 3(구조화) 은 sink가 두 갈래로 갈라진다.

```
galaxy_s25_data.csv
  ├─ row → knowledge_product (ORM)  # 정확 조회: 가격, 색상, 용량 필터
  └─ "Galaxy S25 Ultra 카메라는..." 같은 자연어 설명 컬럼만 → Chroma
```

8강 오케스트레이션이 들어오면 라우터가:
- "512GB 모델 가격" → ORM 쿼리
- "S25 Ultra 카메라 스펙 비교" → RAG 검색

으로 분기한다. 지금은 두 sink만 채워두고 라우팅은 나중에.

분류 1/2/4 는 Chroma 단일 sink.

---

## 7. Manifest — 멱등성과 dedup

**현재 가장 큰 hidden bug**: 같은 CSV 8행짜리인데 Chroma에 청크가 88개
적재돼 있다. `Chroma.from_documents` 가 같은 `persist_directory` 에 append
하기 때문 — 빌더 실행할 때마다 중복으로 쌓인다.

해결:

```
ingest_manifest 테이블 (Django 모델)
  - source_uri        : 'file:///app/galaxy_s25_data.csv'
  - doc_sha256        : 파일 hash
  - loader            : 'csv'
  - splitter          : 'row'
  - chunk_count       : 7
  - chroma_ids        : JSON, 삭제 시 사용
  - ingested_at       : datetime
  - status            : 'ok' | 'failed' | 're-ingesting'
```

ingest 호출 시:
1. SHA256 계산
2. manifest 에 동일 hash 있으면 → skip
3. 같은 source_uri 인데 hash 다르면 → 이전 `chroma_ids` 제거 후 재인덱싱
4. 성공 시 manifest 기록

이게 있어야 `python manage.py ingest --reset` 같은 안전한 재시도가 된다.

---

## 8. 현재 코드의 갭 정리

| 항목 | 현재 | 목표 |
|---|---|---|
| 포맷 추가 | CSV/Excel 은 registry 등록 완료 | loader 파일 1개 + registry 등록 |
| PDF | ❌ | loader/text/pdf.py |
| HWP | ❌ | loader/special/hwp.py (변환 단계 포함) |
| OCR | ❌ | loader/ocr/* |
| 중복 적재 | 발생 중 (8행 → 88청크) | manifest 로 차단 |
| 청킹 | row/recursive splitter 존재, source_type 분기 없음 | splitter 등록제, 조항/heading splitter 포함 |
| metadata 표준 | RawDoc 표준화 시작, manifest 키 없음 | SHA256/chunk_index/ingested_at 포함 |
| 구조화 데이터 라우팅 | 전부 RAG | ORM + RAG 이중 sink |
| 한국어 임베딩 | `text-embedding-004` (Google) | 강사 지적 — 한국어 약함. `bge-m3` 등 비교 필요 (별도 실험) |

---

## 9. 구현 단계 (Phased)

### Phase 1 — Skeleton (PR 1)
**상태: 완료.**

- `chat/ingest/` 패키지 + `base.py` + `registry.py`
- 기존 CSV/XLSX 로직을 `loaders/structured/csv.py`, `excel.py` 로 이전
- 동작 결과 100% 동일. 빌더는 새 pipeline 으로 호출만 바꿈
- 테스트: 현재 빌더 출력과 동일한 청크 수 검증

### Phase 2 — Manifest (PR 2)
**상태: 다음 작업. Celery 없이 동기 CLI 경로에 먼저 붙인다.**

- `IngestManifest` 모델 + 마이그레이션
- pipeline 에 dedup 분기 추가
- `--reset` flag — 같은 source 재인덱싱 시 chroma_ids 청소

### Phase 3 — Text 분류 1 (PR 3) — ✅ 완료
- `loaders/text/pdf.py` (PyPDFLoader)
- `loaders/text/docx.py` (Docx2txtLoader)
- `loaders/text/txt.py`, `html.py`
- splitter dispatch 통합 (`default_splitter_for`, build_vectors/Upload 공유)

### Phase 4 — 청킹 고도화 (PR 4) — ✅ 완료
- `splitters/clause.py` — 사규/법규 "제 N 조"/"Article N" 조항 단위
- `splitters/heading.py` — Markdown heading 계층 (section 경로 보존)
- splitter registry (`_BY_NAME` + `splitter_by_name`); clause/heading 은 opt-in
  (`build_vectors --splitter` / chunk_lab), 확장자 자동매핑엔 미포함

### Phase 5 — OCR 분류 2 (PR 5)
- `loaders/ocr/image.py` (pytesseract + 한국어 모델)
- `loaders/ocr/scanned_pdf.py` (텍스트 추출 실패 시 폴백)
- 의존성 무거우므로 optional extras

### Phase 6 — Sink 분기 (PR 6)
- `sinks/knowledge_orm.py` — CSV 행을 Product/Contact 로
- `galaxy_s25_data.csv` 를 ORM 으로 이전
- Chroma 에는 자연어 description 만 남김

### Phase 7 — 분류 4 (PR 7+)
- HWP, CAD 등 도메인 데이터가 실제로 들어올 때 한 포맷씩
- HWP: LibreOffice headless 변환 폴백
- CAD: 강의 예제 따라 metadata + vision LLM 2-경로

### Phase 8 — Upload API + Admin (선택)
- Django Admin 에 파일 드롭 위젯
- Celery 비동기 ingest
- 영업팀이 자료 추가 시 코드 없이 가능

Celery 는 Phase 8 에서 Upload API/외부 트리거/동시 업로드가 생길 때 도입한다.
현재 CLI 단일 호출 단계에서는 Phase 2 manifest 가 우선이다.

---

## 10. 학습 포인트 메모

이 layer를 직접 만들면서 알게 될 것들:

- **왜 RawDoc 같은 중간 표현이 필요한가** — loader 가 langchain Document
  를 바로 만들면 metadata 표준화가 안 되고, splitter/sink 가 포맷 의존이
  되어버린다.
- **chunk_size 가 retrieval 정확도에 미치는 영향** — 강의 41조 case 처럼
  잘못된 청킹은 정답 chunk 가 검색 결과에서 사라진다.
- **임베딩 모델의 한국어 편향** — text-embedding-004 vs bge-m3 vs
  multilingual-e5 같은 A/B를 ingest layer 가 잡혀야 비로소 돌릴 수 있다.
- **분류 3을 RAG에서 빼는 결단** — 무리한 RAG 화는 retrieval 품질을
  희석시킨다. 검색은 검색이 강한 데이터에만 쓰는 게 맞다.
- **멱등성/manifest** — 운영 들어가면 가장 먼저 터지는 곳. 처음부터 잡기.

---

## 참고

- 7강 transcript — 인제스천 4분류, 조항 청킹, 임베딩 한국어 약점
- 6강 transcript — 토큰/임베딩/어텐션 기본기, 컨텍스트 윈도우 제약
- `chunk_experiment.md` — 현재 chunk_size A/B 결과
- `provider_architecture.md` — 임베딩/생성 provider 추상화
- `security.md` — 외부 LLM 의존 시 위협 모델 (HWP/PDF 가 사내 기밀이면
  로컬 임베딩으로 가야 함)
