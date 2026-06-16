# FAISS Embedding Eval Harness — Spec

## 목표

**프로덕션(pgvector) 검색 품질을 오프라인(FAISS)에서 측정·비교·개선**하는 평가 시스템.

## 배경

- 프로덕션 검색: **pgvector** (Gemini text-embedding-004, 3072차원)
- 기존 eval: `run_chunk_ab.py` — BM25 기반 chunk size/overlap 그리드 (dense retrieval 미포함)
- 평가 데이터: `dataset.jsonl` (12문항, keyword recall)
- 과제: 임베딩 모델 교체, reranker 효과, chunking 전략 변경 시 **정량적 근거** 없이 감으로 결정 중

## 아키텍처

```
chat/tests/evals/
├── dataset.jsonl                 # 평가 질문셋 (기존)
├── dataset_galaxy_full.jsonl     # 확장 질문셋 (기존)
├── run_chunk_ab.py               # BM25 chunk A/B (기존)
├── run_embedding_ab.py           # ★ 임베딩 모델 A/B (신규)
├── eval_core.py                  # ★ 공통 메트릭/로더 (신규)
└── results/                      # JSON 결과 저장
```

## Phase 1: 임베딩 모델 A/B 테스트

### 입력
- 소스 문서 (CSV/텍스트)
- 평가 질문셋 (JSONL)
- 임베딩 모델 목록

### 비교 모델

| 모델 | 차원 | 특징 | 설치 |
|---|---|---|---|
| Gemini text-embedding-004 (baseline) | 3072 | 현재 프로덕션 | API key |
| `BAAI/bge-m3` | 1024 | 한국어 강, 오픈소스 | sentence-transformers |
| `intfloat/multilingual-e5-large` | 1024 | MS, 다국어 | sentence-transformers |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 초경량 | sentence-transformers |

### 흐름

```
1. 문서 로드 → chunking (고정: 1000/200)
2. 각 모델로 chunk 임베딩 생성
3. FAISS IndexFlatIP (내적 = 코사인, 정규화 후) 생성
4. 평가 질문 → 모델별 query 임베딩 → FAISS top-k 검색
5. recall@k + MRR 계산
6. 모델 간 비교 리포트 생성
```

### 메트릭

| 메트릭 | 설명 | 수식 |
|---|---|---|
| **recall@k** | top-k 결과에 expected keywords 몇 개 포함 | hits / total_keywords |
| **MRR** | 첫 번째 관련 chunk의 역순위 | 1/rank_of_first_hit |
| **latency** | 검색 소요 시간 (ms) | wall clock |
| **index_size** | 메모리 사용량 (MB) | FAISS index bytes |

### CLI

```bash
python -m chat.tests.evals.run_embedding_ab \
    --csv galaxy_s25_data.csv \
    --dataset chat/tests/evals/dataset.jsonl \
    --models gemini,bge-m3,e5-large,minilm \
    --k 3,5,10 \
    --output results/embedding_ab.json \
    --html results/embedding_ab.html
```

### 출력 (HTML 리포트)

- 모델별 recall@k 비교 차트
- per-question 히트맵 (어떤 질문에서 어떤 모델이 실패하는지)
- 통계 검정 (Mann-Whitney U)
- 추천: "모델 X가 recall@5에서 Y% 우위, latency Z배 빠름"

## Phase 2: Reranker 효과 측정

기존 ONNX BGE-reranker-v2-m3의 실제 효과를 수치화.

```
FAISS top-20 → 그대로 → recall@3  (baseline)
FAISS top-20 → reranker → top-3 → recall@3  (reranked)
→ Δrecall 리포트
```

## Phase 3: pgvector 검증

FAISS 결과와 pgvector 결과의 일치도 검증 — Chroma 제거 판단 근거.

```
같은 질문 → FAISS top-k vs pgvector top-k
→ Jaccard similarity (결과 집합 겹침)
→ Rank correlation (순위 일치도)
```

## 구현 우선순위

| Phase | 내용 | 파일 |
|---|---|---|
| **1a** | `eval_core.py` — 공통 메트릭 + 질문 로더 | 신규 |
| **1b** | `run_embedding_ab.py` — FAISS 임베딩 A/B | 신규 |
| **2** | reranker 효과 플래그 추가 | 1b 확장 |
| **3** | pgvector 비교 모드 추가 | 1b 확장 |

## 제약

- API key 없는 모델(bge-m3, e5, minilm)은 `sentence-transformers` 로컬 실행
- Gemini는 API key 필요 — 없으면 skip
- FAISS는 `faiss-cpu` (GPU 불필요, 102 chunks)
