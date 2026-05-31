# IR 개선 plan — baseline 부터 reranker 까지 6 단계

> 이 문서는 [2026-05-29-ir-rag-concepts.md](./2026-05-29-ir-rag-concepts.md) 의
> 후속이다. 개념 정리를 끝낸 다음, "그래서 우리 IR 을 어디서부터 어떻게 고치나" 에
> 답하는 실행 가이드.

## 한 줄 요약

**측정 없는 개선은 추측이다.** 먼저 labeled QA 30개로 baseline (MRR, Recall@5)
을 잡고, 그 다음 reranker → hybrid → metadata filter → 청크 정규화 → query
rewriting 순으로 하나씩 켜고 끄며 효과를 측정한다. 이 순서가 ROI 최적.

---

## 비유 — 자동차 튜닝

엔진 출력 측정기를 안 달고 부품을 갈면 "느낌상 빨라진 것 같다" 가 한계다.
*다이노 (dynamometer)* 에 올려서 출력 곡선을 찍고, **부품 하나 갈 때마다
같은 조건에서 다시 찍어야** "이 부품이 +12hp 줬구나" 가 증명된다.

IR 도 마찬가지. labeled QA dataset = 다이노. 거기 안 올리고 reranker, hybrid,
청크 변경 다 해봐야 "좋아진 것 같다" 까지가 한계다.

---

## 왜 이게 필요한가 — 현재 상태 vs 개선 후

| 항목 | 현재 (2026-05-29) | 개선 후 (목표) |
|---|---|---|
| 코퍼스 | 97 chunks (samples + bundled) | 동일 또는 정규화 후 ~120 |
| Embedding | OpenAI 1536d (text-embedding-3-small) | 동일 (필요 시 large) |
| 검색 | dense cosine top-k=4 | dense 20 → cross-encoder rerank → 5 |
| 키워드 매칭 | 없음 (모델명 정확 매칭 약함) | BM25 + RRF 융합 |
| 카테고리 필터 | 없음 (폰/탭/버즈 섞임) | metadata filter 사전 적용 |
| 평가 | eyeball 4 쿼리 | MRR / Recall@5 자동 측정 |
| 개선 의사결정 | 추측 | 숫자 기반 A/B |

---

## 6 단계 (ROI 순)

### 0. 측정 (blocker — 다른 모든 단계의 전제)

**작업:**
1. `backend/data/embedding_eval/sales_qa.yaml` 작성 — 영업팀 실제 질문 30~50개.
2. 각 질문에 정답 청크 식별자 라벨 (source_file + section).
3. `chat/embedding_eval.py` (이미 untracked 에 존재) 에 mgmt cmd wiring.
4. baseline 측정: MRR, Recall@5, Recall@10.

**예시 dataset (5개):**

```yaml
- query: "Galaxy Z Fold6 가격 알려줘"
  expected_source: "data/samples/foldable_handbook.md"
  expected_section_contains: ["가격", "$1,899"]

- query: "Buds3 Pro ANC 되나"
  expected_source: "data/samples/buds_lineup.csv"
  expected_row_contains: ["Buds3 Pro", "ANC"]

- query: "Tab S10 Ultra DeX 무선"
  expected_source: "data/samples/tab_handbook.md"
  expected_section_contains: ["무선 DeX"]

- query: "A55 카메라 OIS"
  expected_source: "data/samples/a_series_handbook.md"
  expected_section_contains: ["OIS"]

- query: "S25 Ultra 무게"
  expected_source: "data/samples/galaxy_lineup.csv"
  expected_row_contains: ["Galaxy S25 Ultra", "Weight"]
```

**비용:** 2~3시간 (질문 + 라벨링)
**완료 조건:** baseline 숫자 1개 (e.g. MRR=0.42) — 이게 비교 기준선이 됨.

---

### 1. Reranker — 가장 큰 single-lever 효과

**작업:**
- `.env` 의 `RERANKER_ENABLED=0` → `RERANKER_ENABLED=1` 토글.
- ONNX 모델 `BAAI/bge-reranker-v2-m3` 는 이미 repo 에 준비됨 (현재 브랜치 = `feature/onnx-reranker`).
- 파이프라인: dense top-20 → cross-encoder rerank → top-5.

**예시 코드 변경 (5줄 이내):**

```python
# chat/pipeline/modules.py — RetrievalModule
dense_hits = vector_store.similarity_search(query, k=20)
if RERANKER_ENABLED:
    reranked = reranker.rerank(query, dense_hits)  # ONNX cross-encoder
    return reranked[:5]
return dense_hits[:5]
```

**예상 효과:** MRR +20~30%p (논문/벤치 일반치)
**비용:** 1시간 (env 토글 + import + smoke test)
**검증:** 0단계 dataset 으로 재측정. baseline 대비 MRR 변화 기록.

---

### 2. Hybrid 검색 (Dense + BM25)

**왜 필요한가:** dense embedding 은 "Galaxy A55" 같은 **정확 명사** 에 약하다.
"A55 카메라" 라고 물으면 의미는 잡지만 모델명 정확 매칭이 약해서 다른 모델 청크도 섞임.
**BM25** = 전통적 keyword 검색. 정확 단어 일치에 강함.

**작업:**
- `pip install rank_bm25` (또는 langchain BM25Retriever).
- ingest 시 BM25 인덱스 추가 빌드 (in-memory 또는 disk).
- 검색: dense top-20 + BM25 top-20 → **RRF (Reciprocal Rank Fusion)** 으로 합산.

**RRF 공식 (단순):**

```python
score(doc) = sum(1 / (60 + rank_in_each_retriever))
```

**예상 효과:** MRR +5~15%p (모델명·SKU 질문 비율에 따라)
**비용:** 0.5 day
**검증:** 같은 dataset, 같은 baseline 비교.

---

### 3. Category metadata + pre-filter

**왜 필요한가:** 현재 청크 메타에 `product_category` 없음.
영업이 "태블릿 추천" 물으면 폰/버즈까지 섞여 top-k 에 들어옴.

**작업:**
- ingest 시 파일 경로에서 category 자동 부여:
  - `foldable_*` → `foldable`
  - `a_series_*` → `smartphone_midrange`
  - `tab_*` → `tablet`
  - `buds_*`, `watch_*`, `accessories_*` → `accessory`
  - `galaxy_lineup.csv`, `galaxy_handbook.md`, `galaxy_s25_data.csv` → `smartphone_flagship`
- 검색 시: LLM 1콜로 쿼리 → category 추정 → chroma filter 적용 후 similarity.

**예시 코드:**

```python
# chat/ingest/sinks/chroma.py — _to_lc_document
flat_meta["category"] = _infer_category(doc.source_file)

# retrieval
category = classify_query(query)  # 짧은 prompt → "tablet"
hits = vs.similarity_search(query, k=5, filter={"category": category})
```

**예상 효과:** MRR +5~10%p, **noise chunk 큰 감소**
**비용:** 0.5 day
**리스크:** category 분류 실수 → false-negative. fallback (filter 없이 재검색) 권장.

---

### 4. 청크 단위 정규화

**왜 필요한가:** 현재 mixed —
- `lineup.csv` row = ~50~100 토큰 (얇음)
- `handbook.md` heading = ~200~1500 토큰 (들쭉날쭉)

청크 길이 편차가 크면 embedding vector 가 같은 "밀도" 가 아니라서 cosine 비교 비정상.

**작업:**
- handbook heading 청크 중 800 토큰 넘는 건 sub-split (sentence-window 또는 sub-heading).
- lineup csv row 는 너무 얇으면 같은 모델 연속 N행 묶기 — 또는 그대로 두되 metadata 강화.
- 목표: ~300~500 토큰 균질.

**예상 효과:** MRR +0~5%p (corpus 특성 따라 미미할 수도)
**비용:** 1 day
**검증:** 같은 dataset, A/B (정규화 전/후).

---

### 5. Query rewriting / HyDE — 마지막 카드

**언제 쓰나:** 0~4 다 했는데도 MRR 부족할 때.

**Query rewriting:** 짧은 한국어 쿼리 ("Z Fold6 얼마") 를 LLM 이 확장 ("Galaxy Z Fold6 시작가 launch price 출고가").

**HyDE (Hypothetical Document Embedding):** LLM 이 "Galaxy Z Fold6 시작가는 약 $1,899" 같은 **가설 답변** 생성 → 그 답변을 embed → 검색.
- 효과: 짧은 쿼리 vs 긴 문서 청크 간 embedding 거리 단축.
- 비용: 매 쿼리당 LLM 1콜 → 비싸고 느려짐.

**예상 효과:** MRR +0~10%p (이미 1~4 가 한 일이라 marginal 일 수 있음)
**비용:** 0.5 day
**채택 조건:** 0~4 완료 후 여전히 MRR < 0.6 이면 도입.

---

### 6. 코퍼스 품질 (지속적인 일)

**작업 (계속):**
- **caveat N/A 보완:**
  - `foldable_lineup.csv` Z Flip6 dimensions/weight
  - `tab_lineup.csv` Tab S10 Ultra/S10+/S9 FE/A9+ USD 가격
  - `a_series_handbook.md` A16 칩셋 변형
  - `accessories_handbook.md` Watch FE 충전 W 수치
- **사실 표현 통일:** handbook 과 lineup csv 동일 fact 다르게 쓰면 RAG 가 헷갈림.
  예) "OIS 지원" (handbook) vs "Main Camera: 50MP f/1.8" (csv) — csv 에도 OIS 명시.
- **FAQ 청크 추가:** 영업이 자주 받는 Q→A 쌍을 그대로 청크화 (`backend/data/samples/sales_faq.md`).
  embedding 이 짧은 사용자 쿼리와 가깝게 매핑됨.

---

## 데이터 흐름 (개선 후)

```
사용자 질문 ("A55 OIS 지원해?")
   ↓
classify_query (LLM, ~50 토큰)        ← 3단계
   ↓
category = "smartphone_midrange"
   ↓
┌──────────────────────────┐
│ Dense retrieval          │
│ (cosine top-20, filter)  │  ← 3단계 filter
└──────────────────────────┘
   ↓
┌──────────────────────────┐
│ BM25 retrieval           │  ← 2단계
│ (keyword top-20)         │
└──────────────────────────┘
   ↓
RRF fusion → top-20         ← 2단계
   ↓
Cross-encoder rerank        ← 1단계 (bge-reranker-v2-m3 ONNX)
   ↓
top-5
   ↓
GenerationModule (LLM + Korean prompt)
   ↓
답변 + citation
```

---

## 확인 방법

```bash
cd Rag_Chat/backend

# 0단계 — baseline
./venv/bin/python manage.py embedding_eval \
    --dataset data/embedding_eval/sales_qa.yaml \
    --report-path docs/reports/2026-05-29-ir-baseline.json

# 1단계 — reranker on
# .env: RERANKER_ENABLED=1
./venv/bin/python manage.py embedding_eval \
    --dataset data/embedding_eval/sales_qa.yaml \
    --report-path docs/reports/2026-05-29-ir-reranker.json

# 비교
diff docs/reports/2026-05-29-ir-{baseline,reranker}.json
```

**기록 원칙:** 단계마다 결과 JSON 1개. 변경 1개만 켜고 측정 — confounded 측정 금지.

---

## 연습 문제

### 문제 1 (쉬움)

baseline MRR = 0.42. reranker 켰더니 MRR = 0.61. **개선폭 %p** 는?
**상대 개선률** (%)도 계산하라.

> **힌트:** %p = 단순 차. 상대 = (new - old) / old × 100.

### 문제 2 (중간)

영업팀이 "Galaxy A55 카메라 OIS 지원?" 이라고 물었는데
top-1 결과가 `a_series_lineup.csv` 의 A55 행이지만 OIS 명시 없음.
이때 LLM 이 어떤 답을 할 위험이 있나? 우리가 어떻게 막을 수 있나?
**두 개 이상의 layer 에서** 답하라 (corpus 단계, 검색 단계, 답변 단계).

> **힌트:** 6단계 (corpus 사실 표현 통일), 1~3단계 (reranker 가 handbook 청크를 위로 올림),
> Korean prompt 가 "자료에 없으면 모른다고 답하라" 라고 강제.

### 문제 3 (어려움)

이 plan 의 1~6 단계를 **모두 켰을 때** MRR 이 oracle (사람이 직접 선택한 최적 chunk) 대비 90% 까지 도달했다.
그래도 영업팀 만족도가 낮다. **어떤 차원의 문제가 남아있을 가능성이 큰가?**
3가지 이상 추측하라.

> **힌트:** retrieval 만 RAG 가 아니다. generation 품질 (LLM), corpus 누락 (질문은 답이 corpus 에 아예 없음),
> citation UX (영업이 답을 못 믿음), latency (느려서 안 씀) 등.

---

## 다음 단계 체크리스트

- [ ] **0단계:** `sales_qa.yaml` 30개 질문 + 정답 라벨링
- [ ] **0단계:** `embedding_eval` mgmt cmd 와이어링 + baseline JSON 산출
- [ ] **1단계:** `RERANKER_ENABLED=1` 토글 + 재측정
- [ ] **2단계:** BM25 + RRF 구현 + 재측정
- [ ] **3단계:** category metadata + pre-filter + 재측정
- [ ] **4단계:** 청크 정규화 (handbook sub-split, csv row grouping) + 재측정
- [ ] **5단계:** (필요 시) HyDE / query rewriting
- [ ] **6단계:** caveat 보완 + 사실 표현 통일 + FAQ 청크

각 단계 완료 시 `backend/docs/reports/YYYY-MM-DD-ir-stepN.json` 기록.

---

## 관련 문서

- 개념 정리: [2026-05-29-ir-rag-concepts.md](./2026-05-29-ir-rag-concepts.md)
- 코드: `chat/ingest/`, `chat/pipeline/modules.py`, `chat/embedding_eval.py`
- 환경: `Rag_Chat/.env` (`RERANKER_ENABLED`, `EMBEDDING_PROVIDER`)
- 데이터셋 위치: `backend/data/embedding_eval/`
