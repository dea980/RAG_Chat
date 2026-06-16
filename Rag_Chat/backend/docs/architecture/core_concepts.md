# Core Concepts — 이 프로젝트로 익혀야 할 개념

> RAG 챗봇을 만들면서 머릿속에 "왜 이렇게 짜여있는가" 의 뼈대가 잡혀야
> 다음 단계 (Phase 3~8) 가 따라온다. 이 문서는 강의(6강/7강) 와 코드를
> 묶어, **꼭 손으로 만져봐야 하는 개념** 을 정리한다.
>
> 추상적 정의는 줄이고, **이 레포의 어느 파일에서 보이는가** 와 **어떻게
> 실험해야 손에 잡히는가** 에 집중.

---

## A. LLM 기초 (6강 — 기본기)

### A1. 토큰 (Tokenization)

- **한 줄 정의**: LLM 은 글자가 아니라 *토큰* 단위로 텍스트를 본다. 한국어
  는 같은 의미를 영어보다 더 많은 토큰으로 표현하는 경향.
- **이 레포의 어디서**: [`chat/token_utils.py`](./token_lab_page.md) — `tiktoken`
  으로 OpenAI 인코딩 실측 + Gemini/Claude/Qwen 추정. 페이지: `/token_lab`.
- **손으로 실험**:
  - Token Lab 에서 한 문장을 한국어 / 영어 / 일본어 / 코드 로 비교.
  - `tokens_per_character` 비율 차이를 관찰. 한국어가 가장 높음.
- **흔한 오해**: "단어 수 = 토큰 수" 아니다. `chatGPT` 한 단어가 2 토큰
  으로 쪼개진다. 비용 예측이 단어 카운트로 안 되는 이유.

### A2. 임베딩 (Embedding)

- **한 줄 정의**: 텍스트를 의미적 위치를 담은 *고정 길이 벡터* 로 변환. 의미
  가 가까운 단어는 벡터 공간에서도 가깝다.
- **이 레포의 어디서**: [`chat/providers/manager.py`](./provider_architecture.md)
  의 `_create_gemini_embeddings()` / `_create_openrouter_embeddings()`. 모델은
  env 로 교체 (`GOOGLE_EMBEDDING_MODEL=text-embedding-004`).
- **손으로 실험**:
  - 같은 한국어 문장을 다른 임베딩 모델로 검색해 결과 비교 (강의 후반의
    "한국어 약함" 현상). Phase 5~6 에서 bge-m3 등으로 A/B 예정.
- **흔한 오해**: 임베딩 모델 바꾸면 *기존 Chroma 컬렉션 그대로 못 쓴다*. 다른
  공간이라 의미 비교가 안 됨. → `build_vectors --rebuild` 필요.

### A3. 어텐션 (Attention)

- **한 줄 정의**: 토큰들끼리 "누가 누구를 얼마나 참고하는가" 의 가중치 계산.
- **이 레포의 어디서**: 직접 안 보임 (LLM 내부). 하지만 **어텐션의 한계가
  RAG 가 필요해진 이유**.
- **이해 포인트**: 어텐션은 *컨텍스트 윈도우 안에서만* 동작. 사규 문서
  100MB 를 통째로 어텐션 못 시키니 → 관련 부분만 검색해서 컨텍스트에
  넣자 → 그게 **RAG**.

### A4. 컨텍스트 윈도우 (Context Window)

- **한 줄 정의**: 한 번에 모델에 넣을 수 있는 최대 토큰 수.
- **이 레포의 어디서**: Token Lab 의 `chunk_recommendations` — "기준 토큰
  대비 chunk_size 250/500/1000/2000 이면 몇 청크" 추산. 청크가 커지면
  필요한 컨텍스트 윈도우도 커짐.
- **손으로 실험**: 긴 문서 붙여넣고 모델별 토큰 수 차이 보기. 한국어가
  같은 의미인데 윈도우를 더 많이 먹는 현상.

### A5. 템퍼처 / 탑-p (Sampling)

- **한 줄 정의**: 다음 토큰 *선택* 전략. 낮으면 결정적, 높으면 창의적.
- **이 레포의 어디서**: provider 별 설정. RAG 답변은 보통 낮게 (사실 기반).
- **흔한 오해**: 모델이 매번 똑같이 답해야 한다고 기대 → 디버깅 어려움.
  같은 입력도 temperature > 0 이면 흔들림.

### A6. LLM 한계 — 할루시네이션 / 지식 단절 / 컨텍스트 제약

- **한 줄 정의**: (1) 모를 때 그럴듯하게 지어냄 (2) 학습 cutoff 이후 모름
  (3) 윈도우보다 크면 못 봄.
- **이 레포가 어떻게 대응**:
  - (1) → 검색 결과를 컨텍스트로 강제 + outbound moderation (`moderation/`)
  - (2) → 사내 문서를 RAG 로 외부 데이터 주입
  - (3) → chunking + retrieval (검색해서 필요한 부분만 넣음)

---

## B. RAG 기초 (7강 — 이 프로젝트의 본체)

### B1. 인제스천 계층 (Ingestion Layer)

- **한 줄 정의**: 청킹 전, *데이터를 검색 가능한 텍스트로 변환* 하는 단계.
  RAG 의 진짜 1단계. 종종 튜토리얼이 건너뜀.
- **이 레포의 어디서**: [`chat/ingest/`](./ingest_layer.md) 패키지 전체.
- **4분류 (7강 강사 프레임)**:
  1. 텍스트 추출형 — PDF/DOCX/HTML/TXT (현재: TXT만, 나머지 Phase 3)
  2. OCR 필요형 — 스캔 PDF/이미지 (Phase 5)
  3. 구조화 — CSV/Excel/RDB (현재 CSV/XLSX; "SQL 라우팅이 더 맞다" 강사 지적)
  4. 전용 포맷 — HWP/CAD/오디오 (Phase 7)
- **손으로 실험**: Chunk Lab 에서 같은 텍스트를 splitter/chunk_size 바꿔
  결과 비교.
- **흔한 오해**: "그냥 loader 한 개면 되는 거 아닌가" — 4분류마다 처리
  방식이 다르고, 분류 3 는 사실 RAG 가 아닌 SQL 이 정답인 경우가 많다.

### B2. 청킹 (Chunking)

- **한 줄 정의**: 긴 문서를 검색 단위로 자르기. 너무 작으면 맥락 끊김,
  너무 크면 노이즈.
- **이 레포의 어디서**: [`chat/ingest/splitters/`](./chunk_testing_page.md).
  현재 `recursive` (길이 기반) + `row` (표 1행 1청크). Phase 4 에서
  `clause` (조항 단위) + `heading` 추가 예정.
- **손으로 실험**: Chunk Lab 페이지에서 같은 사규 텍스트를 200/500/1000
  자로 비교. 7강 강사의 39조 사례 — 500 자로는 정답 청크를 못 찾고,
  조항 단위로 바꾼 후 찾음.
- **흔한 오해**: "chunk_size 큰 게 무조건 좋다" — retrieval 노이즈가 늘어
  답변 정확도가 *떨어질 수 있다*. 측정해야 함.

### B3. 벡터 검색 (Similarity Search)

- **한 줄 정의**: 질문도 임베딩 → 벡터 공간에서 가까운 청크 top-k 가져오기.
- **이 레포의 어디서**: [`chat/utils.py:RAGUtils.get_rag_context`](../chat/utils.py)
  → `vector_store.similarity_search(question, k=k)`. 벡터 스토어는 Chroma.
- **손으로 실험**: 의미는 같은데 다른 단어로 질문 ("연차" vs "휴가") →
  결과가 비슷한지. 임베딩 모델의 한국어 의미 포착 능력 확인.

### B4. Retrieval 결과 통합 + 응답 생성

- **한 줄 정의**: top-k 청크를 컨텍스트로 LLM 에 넘기고, LLM 은 그 안에서
  답을 합성.
- **이 레포의 어디서**: [`chat/views.py:ChatAPIView.post`](../chat/views.py)
  의 pipeline 흐름 — retrieve → rerank → moderate → generate.
- **흔한 오해**: "검색 결과를 그대로 보여주면 RAG" — 아니다. *합성된 답*
  이 RAG. 출처 추적은 별도 (SearchLog 가 담당).

### B5. Reranker

- **한 줄 정의**: 임베딩 검색의 top-N 을 cross-encoder 로 다시 정렬해 정밀
  도 올림. 임베딩은 빠르지만 거칠고, reranker 는 느리지만 정확.
- **이 레포의 어디서**: [`chat/rerankers/onnx_bge.py`](../chat/rerankers/onnx_bge.py)
  — ONNX `BAAI/bge-reranker-v2-m3`. `RERANKER_ENABLED=0` 으로 끌 수 있음.
- **이해 포인트**: 두 단계 검색 (retrieve → rerank) 가 production RAG 의
  표준 구조. 임베딩 단독으로는 한계.

### B6. 평가 (Recall@k, A/B)

- **한 줄 정의**: "정답 청크가 top-k 에 있느냐" 비율. 청킹·임베딩 결정의
  근거.
- **이 레포의 어디서**: [`chat/tests/evals/run_chunk_ab.py`](../chat/tests/evals/run_chunk_ab.py)
  + [`chunk_experiment.md`](./chunk_experiment.md). 12 문항 eval set.
- **이해 포인트**: 본인 직관 ("이 청크가 답이지") 가 아니라 *측정* 으로
  결정. 강사가 모델 바꿨다 합/오답 사례 그대로 재현 가능.

---

## C. 시스템 — 이 프로젝트가 추가로 가르치는 것 (강의 밖)

### C1. 멱등성 (Idempotency)

- **한 줄 정의**: 같은 작업을 두 번 해도 같은 결과 — 운영의 기본 안전성.
- **이 레포의 어디서**: [`chat/ingest/manifest.py`](./ingest_phase2_manifest.md)
  + 결정론적 청크 id (`ChromaSink._chunk_id`).
- **이해 포인트**: 청크 id 가 *content + 위치* 의 해시라 같은 청크는 항상
  같은 id → `add_documents` 가 upsert 처럼 동작. 88청크 중복 적재 사고가
  여기서 차단됨.

### C2. SHA256 dedup + Manifest

- **한 줄 정의**: 파일 내용 hash 로 "이미 들어온 파일인가" 판단 + DB 에
  기록 남김. 내용이 바뀌면 옛 청크 자동 제거.
- **이 레포의 어디서**: `chat/models.py:IngestManifest`,
  `chat/ingest/manifest.py:file_sha256`.
- **이해 포인트**: 이게 없으면 Celery 같은 비동기 도입이 *문제를 가린다*.
  운영 안정성의 토대는 동기 멱등성.

### C3. Plugin Registry 패턴

- **한 줄 정의**: 새 기능 추가가 한 파일 작성 + 데코레이터 한 줄로 끝나는
  구조. 코어 코드를 수정하지 않게 함.
- **이 레포의 어디서**: [`chat/ingest/registry.py:@register`](../chat/ingest/registry.py).
  Loader 가 자기 확장자를 들고 import 시 자동 등록.
- **이해 포인트**: side-effect import (`loaders/__init__.py` 가 하위 모듈을
  import 함) 가 데코레이터 실행을 트리거. Django app 등록과 같은 패턴.

### C4. 계층 분리 (Layered Architecture)

- **한 줄 정의**: `Loader → Splitter → Sink` 처럼 각 단계가 다음 단계를
  모름. 표준 표현(`RawDoc`) 으로만 대화.
- **이 레포의 어디서**: `chat/ingest/base.py` 의 3 Protocol.
- **이해 포인트**: PDF loader 가 들어와도 splitter / sink 는 안 바꾼다.
  Protocol 이 인터페이스 계약, registry 가 디스패치.

### C5. Traceability (추적성)

- **한 줄 정의**: 모든 답변이 *어떤 데이터를 근거로* 나왔는지 추적 가능.
- **이 레포의 어디서**: `Chat` / `SearchLog` / `RagData` 모델 + `views.py`
  에서 매 요청마다 row 작성. Django Admin / `/api/v1/triple/search-logs/`
  로 조회.
- **흔한 오해**: "응답 텍스트만 저장하면 된다" — 검색 컨텍스트도 같이
  스냅샷 저장해야 *후일* 재현 가능. 외부 LLM 응답은 비결정적이라 더더욱.

### C6. Moderation (입출력 필터)

- **한 줄 정의**: BLOCK / MASK / WARN 다단계 필터로 PII·기밀·경쟁사 차단.
  inbound (질문) + outbound (LLM 응답) 양방향.
- **이 레포의 어디서**: `moderation/` 앱 + Admin 검수 페이지.
- **이해 포인트**: outbound 가 중요. LLM 이 잘못 노출할 수 있는 키워드를
  *응답 직전* 에 한 번 더 걸러야 함.

### C7. Provider Abstraction (벤더 분리)

- **한 줄 정의**: LLM/임베딩 벤더를 env 만 바꿔 교체. 코드 수정 없음.
- **이 레포의 어디서**: [`chat/providers/manager.py`](./provider_architecture.md).
- **이해 포인트**: API 키·base_url·모델명을 *코드가 아니라 설정* 으로 받는다.
  대외비 등급 올라가면 로컬 LLM(Ollama 등) 으로 전환하기 위한 토대.

### C8. 권한 / 세션 / 만료

- **한 줄 정의**: USER / MANAGER / ADMIN 역할 + Redis 세션 TTL 과 DB
  `expired_datetime` 가 한 변수(`SESSION_TIMEOUT`) 로 일관 관리.
- **이 레포의 어디서**: `chat/models.py:User.Role`, `chat/redis_manager.py`,
  `chat/session_strategies.py`.

---

## D. 다음 (8강 오케스트레이션 — 미리보기)

7강 끝에서 강사가 예고한 8강 주제. 이 프로젝트가 **아직 안 한** 것:

### D1. Tool Use / Function Calling

- 단순 검색이 아니라 LLM 이 *어떤 도구* 를 호출할지 결정.
  - 분류 3 (CSV/표) 질문 → SQL 도구
  - 분류 1 (사규) 질문 → RAG 검색
  - 실시간 정보 (오늘 환율) → Web 도구

### D2. 라우팅 (Routing)

- 질문을 분석해 적절한 sub-pipeline 으로 분배. 강의 8강 핵심.
- 이 레포에는 아직 없음. Phase 6 (ORM sink) 와 같이 도입 자연스러움.

### D3. Agent

- 여러 도구를 *자율적* 으로 조합하는 LLM. 단일 파이프라인 → 다단계 동적
  플로우.

---

## E. Python / Django specifics — 만지면서 익히게 되는 것

- **`typing.Protocol`** vs ABC — duck typing 형태의 인터페이스. `@runtime_checkable`
  로 isinstance 검사 가능. 이 레포의 ingest 계약이 다 Protocol.
- **side-effect import** — `__init__.py` 가 하위 모듈을 import 하는 것만으로
  registry 채우기. 명시적 등록 함수 호출 없이.
- **Django migration 작성** — `chat/migrations/0006_*.py` 를 손으로 작성하기
  도 함 (자동 생성 + 보정). schema 변경이 코드 리뷰 대상.
- **`update_or_create`** — 동시성 + 재시도에 안전한 upsert. `create` 만 쓰면
  unique 제약에서 터짐.
- **DRF `APIView` + `parser_classes`** — multipart + JSON 동시 받기 (Chunk
  Lab 의 file upload + text 패턴).
- **Streamlit multipage** — `frontend/pages/<name>.py` 만 두면 자동 사이드바
  네비. main app 변경 불필요.

---

## F. 학습 우선순위 — 무엇부터 손에 익혀야 하는가

다 한 번에는 못 한다. 권장 순서:

| 순서 | 개념 | 왜 먼저인가 |
|---|---|---|
| 1 | **B1 인제스천 4분류** | 데이터가 안 들어오면 RAG 가 없다. 강의 7강 첫 단원 |
| 2 | **A1 토큰 + A4 컨텍스트 윈도우** | 비용/성능 직관의 기본. Token Lab 으로 즉시 체감 |
| 3 | **B2 청킹 + B6 평가** | "왜 청크가 중요한가" 와 "측정 없이 못 한다" 의 짝. Chunk Lab + run_chunk_ab.py |
| 4 | **C1~C3 멱등성·dedup·registry** | RAG 가 *운영 가능한 시스템* 이 되려면 필요한 시스템 개념 |
| 5 | **A2 임베딩 + B3 벡터 검색 + B5 reranker** | 검색 정확도 끌어올리는 두 단계 구조 이해 |
| 6 | **C5 traceability + C6 moderation** | 사내 도입 시 *반드시* 필요한 운영 안전망 |
| 7 | **C7 provider abstraction + D Tool Use/Routing** | 다음 단계 확장 가능성 (로컬 LLM 전환, agent 화) |

각 항목은 **연관 doc 한 개 + 코드 한 파일 + 손 실험 하나** 로 끝낼 수 있도록 구성돼있다. 위 표의 우선순위대로 따라가면 약 일주일 분량.

---

## G. 관련 문서 / 코드 한눈에

- [`_index.md`](./_index.md) — 전체 문서 인덱스
- [`ingest_layer.md`](./ingest_layer.md) — B1·B2·C1~C4 의 본문
- [`token_lab_page.md`](./token_lab_page.md) — A1·A4 실습 도구
- [`chunk_lab_page.md`](./chunk_lab_page.md) — B2 실습 도구
- [`chunk_experiment.md`](./chunk_experiment.md) — B6 CLI A/B
- [`provider_architecture.md`](./provider_architecture.md) — C7
- [`security.md`](./security.md) — C6·C7 의 운영 측면
- [`work_distribution.md`](./work_distribution.md) — 여러 agent 와 함께 일하는 법 (메타)
