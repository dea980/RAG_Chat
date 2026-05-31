# FAISS 임베딩 평가 시스템 — 실험은 FAISS, 프로덕션은 pgvector

## 한 줄 요약

프로덕션 벡터 DB(pgvector)를 건드리지 않고, **FAISS로 임베딩 모델을 빠르게 비교·평가**한 뒤 최적 모델을 프로덕션에 반영하는 실험 파이프라인 구축.

## 비유 — 시식 코너

마트에서 새 과자를 진열대에 올리기 전에 **시식 코너**에서 먼저 반응을 본다:

| | 시식 코너 (FAISS) | 진열대 (pgvector) |
|---|---|---|
| **목적** | 빠른 비교·테스트 | 실제 고객 서빙 |
| **준비 시간** | 접시에 담기만 (수초) | 포장·바코드·진열 (수분) |
| **비용** | 무료 (일회용 접시) | DB 저장·인덱싱 비용 |
| **결과** | "이 맛이 더 낫다" → 결정 | 확정된 상품만 진열 |

시식 코너에서 이것저것 비교해보고, **제일 맛있는 것만 진열대에 올리는 것**.

## 왜 이게 필요한가

| | 변경 전 | 변경 후 |
|---|---------|---------|
| **모델 선택** | "Gemini가 유명하니까" (감) | recall@3=0.963 vs 0.917 (수치) |
| **비교 방법** | 없음 | FAISS + 12문항 자동 평가 |
| **비교 시간** | pgvector 재인덱싱 → 수분 | FAISS in-memory → 수초 |
| **비용** | Gemini API 과금 | MiniLM/BGE-M3 무료 로컬 |
| **UI** | 터미널만 | Streamlit Retrieval Lab 페이지 |

### 실제 A/B 결과

```
Model     Dim   Recall@3  MRR    Speed   Cost
MiniLM    384   0.963     0.805  41ms    무료
Gemini    3072  0.917     0.917  452ms   API 과금
BGE-M3    1024  0.911     0.903  89ms    무료
E5-Large  1024  0.800     0.833  69ms    무료
```

**384차원 무료 모델(MiniLM)이 3072차원 유료 모델(Gemini)을 recall에서 이김!**

## 핵심 코드

### 1. FAISS 인덱스 생성 (5줄)

```python
import faiss
import numpy as np

# L2 정규화된 벡터 → Inner Product = Cosine Similarity
embeddings = model.encode(texts, normalize_embeddings=True)  # (N, dim)
index = faiss.IndexFlatIP(embeddings.shape[1])                # 코사인 유사도
index.add(embeddings.astype(np.float32))                      # 인덱스에 추가
scores, indices = index.search(query_vec, k=3)                # top-3 검색
```

- `IndexFlatIP` — Inner Product (내적). 정규화된 벡터에서 내적 = 코사인 유사도
- `normalize_embeddings=True` — sentence-transformers가 자동 정규화
- 인덱스 생성·검색이 수 밀리초 — pgvector의 SQL 쿼리보다 빠름

### 2. 평가 메트릭 (eval_core.py)

```python
def keyword_recall(question, retrieved_text):
    """top-k 결과에 기대 키워드가 몇 개 포함되었나"""
    hits = sum(1 for kw in question.expected_keywords
               if kw.lower() in retrieved_text.lower())
    return hits / len(question.expected_keywords)
    # 예: 기대 ["Galaxy S25", "256GB", "1199.99"]
    #     top-3에 2개 포함 → recall = 2/3 = 0.667

def mrr_score(question, ranked_texts):
    """첫 번째 관련 결과의 역순위"""
    for rank, text in enumerate(ranked_texts, 1):
        if any(kw.lower() in text.lower() for kw in question.expected_keywords):
            return 1.0 / rank
    return 0.0
    # 예: 1등에 정답 → MRR = 1.0
    #     3등에 정답 → MRR = 0.333
```

- **recall@k**: "필요한 정보가 결과에 얼마나 포함되었나" (높을수록 좋음)
- **MRR**: "정답이 몇 등에 있나" (1.0 = 1등, 0.5 = 2등, 0.333 = 3등)

### 3. Streamlit Retrieval Lab (retrieval_lab.py)

```python
# 모델 로딩 — @st.cache_resource로 한 번만 로드
@st.cache_resource
def load_model(model_key):
    return SentenceTransformer(MODEL_REGISTRY[model_key]["hf_name"])

# 평가 실행 — 슬라이더 값이 바뀌면 즉시 재실행
chunk_texts = load_and_chunk(csv_path, chunk_size, chunk_overlap)
result = evaluate(model_key, chunk_texts, questions, k)
```

Streamlit 캐시로 모델은 한 번만 로드, 설정 변경 시 FAISS만 재빌드 → 인터랙티브.

## 데이터 흐름

```
[CLI 평가 (오프라인)]
run_embedding_ab.py
    │
    ├─ CSV 로드 → RecursiveCharSplitter → chunk_texts[]
    │
    ├─ 각 모델:
    │    SentenceTransformer.encode(chunk_texts) → embeddings
    │    faiss.IndexFlatIP(dim).add(embeddings) → index
    │    │
    │    └─ 각 질문:
    │         model.encode(question) → query_vec
    │         index.search(query_vec, k) → top-k indices
    │         keyword_recall + mrr_score → 메트릭
    │
    └─ 결과: JSON + HTML 리포트

[Streamlit UI (인터랙티브)]
retrieval_lab.py
    │
    ├─ 사이드바: chunk_size/overlap 슬라이더, 모델 체크박스, k 슬라이더
    │
    ├─ "평가 실행" 클릭
    │    → 위와 동일한 흐름 (FAISS in-memory)
    │
    └─ 결과: 요약 테이블 + 바 차트 + per-question 히트맵
```

```
[프로덕션 반영]
실험 결과 확정 후:
    1. embedding 모델 변경 → provider_manager 설정
    2. PgvectorSink로 재인덱싱
    3. pgvector에서 프로덕션 검색
```

## 확인 방법

```bash
cd Rag_Chat/backend

# 1. CLI 평가 실행
python -m chat.tests.evals.run_embedding_ab \
    --csv galaxy_s25_data.csv \
    --dataset chat/tests/evals/dataset.jsonl \
    --models minilm,bge-m3 \
    --k 3
# 기대: recall@3, MRR, latency 출력

# 2. HTML 리포트 생성
python -m chat.tests.evals.run_embedding_ab \
    --models minilm,bge-m3,gemini \
    --k 3 \
    --html chat/tests/evals/results/report.html
# 기대: 브라우저에서 비교 테이블 + 히트맵

# 3. Streamlit UI
cd ../frontend
streamlit run pages/retrieval_lab.py
# 기대: 슬라이더 조작 → 즉시 결과 비교
```

## 연습 문제

### 연습 1: chunk size가 recall에 미치는 영향

Retrieval Lab에서 MiniLM을 선택한 뒤:
1. chunk_size=500, overlap=100 → recall@3 기록
2. chunk_size=1000, overlap=200 → recall@3 기록
3. chunk_size=2000, overlap=400 → recall@3 기록

어떤 설정이 가장 높은가? 왜 그럴까?

**힌트**: chunk가 너무 작으면 키워드가 잘려나감. 너무 크면 관련 없는 내용이 섞여 임베딩이 희석됨.

### 연습 2: 새 평가 질문 추가

`dataset.jsonl`에 새 질문을 추가해보자:

```json
{"id": "q13", "question": "S25 시리즈 중 가장 저렴한 모델 가격은?", "expected_keywords": ["Galaxy S25", "128GB", "1099.99"], "scenario": "영업팀 가격 문의"}
```

추가 후 CLI로 재실행하면 recall이 바뀌는지 확인. 새 질문의 키워드가 실제 데이터에 있는지도 먼저 확인할 것.

### 연습 3: FAISS vs pgvector 결과 비교

같은 질문으로 FAISS(MiniLM)와 pgvector(Gemini) 결과를 비교해보자:

```python
# pgvector 결과
from chat.utils import RAGUtils
pg_result = RAGUtils.get_rag_context("S25 배터리 용량", k=3)

# FAISS 결과
# run_embedding_ab.py --models minilm --k 3 의 출력

# 같은 질문인데 다른 chunk가 나오는가? 왜?
```

두 시스템의 차이는 **임베딩 모델이 다르기 때문** (Gemini 3072d vs MiniLM 384d). 같은 모델을 쓰면 동일한 결과가 나와야 함.
