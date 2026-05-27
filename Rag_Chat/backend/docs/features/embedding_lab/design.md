# Embedding Lab — 설계 메모

> 의견: "임베딩이 잘되는지도 학습이나 비교하는 페이지가 필요할 것 같다"
> 동의. `chunk_lab` (청크 비교) · `token_lab` (토큰 비교) 가 있는데
> 임베딩 비교 도구가 비어있다. 강의 7강 강사가 "한국어 약함 → 모델 바꿈
> → 39조 찾음" 한 그 결정의 재현 도구.

---

## 1. 왜 필요한가

### 현재 라인업의 빈 칸

| Lab | 측정 | 페이지 |
|---|---|---|
| Chunk Lab | splitter 가 텍스트를 어떻게 자르는가 | `frontend/pages/chunk_lab.py` |
| Token Lab | 모델별로 텍스트가 몇 토큰인가 | `frontend/pages/token_lab.py` |
| **Embedding Lab (제안)** | **모델별로 의미를 얼마나 잘 포착하는가** | (예정) |

### 강사가 짚은 그 시나리오

7강 후반에서 강사가 사규 39조 (연차 휴가) 를 못 찾다가:
1. 청크 크기 바꿔봐도 못 찾음
2. 조항 단위 청킹으로 바꿔도 부족
3. **임베딩 모델을 바꾸고** 비로소 찾음

즉 임베딩 모델 선택이 retrieval 정확도의 천장. 그런데 우리 코드에서는
모델 교체가 환경변수 한 줄(`EMBEDDING_PROVIDER=gemini → ollama`) 인데,
교체 *직전에* 어느 모델이 우리 corpus 에 맞는지 검증할 수단이 없다.

### 한국어 약점 — 왜 발생하나

이론 배경 (학습 메모 §6 자세히):
1. **서브워드 토크나이저** — 한국어를 비효율적으로 쪼개 의미 단위 손실
2. **학습 데이터 비율** — 영어 중심으로 학습된 모델은 한국어 의미 거리가 평탄
3. **다국어 모델 vs 한국어 특화** — bge-m3 / e5-multilingual 이 한국어 강함

이 셋을 *측정으로 확인* 하는 게 Embedding Lab 의 역할.

---

## 2. 무엇을 측정/비교

### 비교 축

1. **임베딩 모델** (5~8개 후보)
   - `gemini` — `text-embedding-004` (현재 default)
   - `openai-3-small`, `openai-3-large` — OpenAI
   - `bge-m3` — 다국어 강함, BAAI (로컬)
   - `multilingual-e5-large` — Microsoft (로컬)
   - `ko-sroberta-multitask` — 한국어 특화 (로컬, sentence-transformers)
   - `cohere-multilingual-v3` — Cohere (선택)
   - `qwen` (OpenAI 호환 endpoint)

2. **측정 지표**
   - **유사도 (cosine similarity)** — 두 텍스트 거리
   - **의미 포착력** — 의미 같은 쌍 → 높은 유사도가 나오는가
   - **구분력** — 의미 다른 쌍 → 낮은 유사도가 나오는가
   - **언어별 일관성** — 같은 의미를 한국어/영어로 표현 시 거리 안정성

3. **시각화**
   - 2D 투영 (UMAP / PCA) — 여러 문장의 의미 클러스터
   - 모델별 매트릭스 (n×n 유사도)

### 3 모드

**모드 A — Pair Compare** (가장 단순)
- 두 텍스트 입력 → 각 모델별 유사도 한 줄 표시
- "사과를 먹다" vs "배를 먹다" 두 문장의 모델별 유사도 비교

**모드 B — Matrix**
- 여러 문장 (5~10개) 입력 → 모델 1개 선택 → n×n 히트맵
- 의미 가까운 문장이 정말 가까이 나오는지 시각 확인

**모드 C — Retrieval Test**
- corpus (예: 사규 청크들) + 질문 1개 → 모델별 top-5
- 정답 청크가 어느 모델에서 어떤 rank 에 등장하는지 비교
- 7강 강사의 39조 시나리오 그대로 재현

---

## 3. UI 스케치 (Streamlit `pages/embedding_lab.py`)

```python
# 좌측 사이드바
mode = st.radio("모드", ["A. Pair Compare", "B. Matrix", "C. Retrieval Test"])
models = st.multiselect(
    "비교할 모델",
    ["gemini", "openai-3-small", "openai-3-large",
     "bge-m3", "multilingual-e5", "ko-sroberta"],
    default=["gemini", "bge-m3", "multilingual-e5"],
)

# 메인 영역
if mode == "A. Pair Compare":
    text1 = st.text_area("텍스트 1")
    text2 = st.text_area("텍스트 2")
    if st.button("비교"):
        results = call_embed_compare(text1, text2, models)
        for m, score in results.items():
            st.metric(m, f"{score:.3f}")

elif mode == "B. Matrix":
    sentences = st.text_area("문장들 (한 줄에 하나)").split("\n")
    model = st.selectbox("모델", models)
    if st.button("매트릭스"):
        matrix = call_embed_matrix(sentences, model)
        st.dataframe(matrix)  # 또는 plotly heatmap
        # UMAP 2D 투영도 옵션

elif mode == "C. Retrieval Test":
    corpus = st.text_area("코퍼스 (한 줄에 청크 하나)")
    question = st.text_input("질문")
    if st.button("검색"):
        results = call_embed_retrieve(corpus, question, models, k=5)
        for m, hits in results.items():
            st.subheader(m)
            for rank, hit in enumerate(hits, 1):
                st.code(f"[{rank}] score={hit['score']:.3f} | {hit['text'][:120]}")
```

---

## 4. Backend API 설계

새 엔드포인트 3개 (또는 1개에 mode 인자):

### `POST /api/v1/triple/embeddings/compare` (Mode A)
```json
// request
{ "text1": "사과", "text2": "배", "models": ["gemini", "bge-m3"] }
// response
{
  "results": {
    "gemini":  { "score": 0.34, "method": "exact",  "dim": 768 },
    "bge-m3":  { "score": 0.41, "method": "exact",  "dim": 1024 }
  }
}
```

### `POST /api/v1/triple/embeddings/matrix` (Mode B)
```json
// request
{ "sentences": ["...", "...", ...], "model": "bge-m3" }
// response
{
  "model": "bge-m3",
  "matrix": [[1.0, 0.62, ...], ...],
  "umap_2d": [[0.1, 0.4], [0.5, 0.3], ...]   // optional
}
```

### `POST /api/v1/triple/embeddings/retrieve` (Mode C)
```json
// request
{ "corpus": ["...", ...], "question": "연차 휴가 며칠?",
  "models": ["gemini", "bge-m3"], "k": 5 }
// response
{
  "results": {
    "gemini": [{"text": "...", "score": 0.88, "index": 4}, ...],
    "bge-m3": [{"text": "...", "score": 0.91, "index": 4}, ...]
  }
}
```

저장 X. 임시 in-memory 비교만.

---

## 5. 의존성 / 모델 가용성

| 모델 | 의존성 | 비용 | 오프라인? |
|---|---|---|---|
| `gemini` (text-embedding-004) | `langchain-google-genai` (있음) | 호출당 과금 | ❌ |
| `openai-3-*` | `openai` SDK | 호출당 과금 | ❌ |
| `bge-m3` | `sentence-transformers` (신규) + 모델 ~2GB | 무료 | ✅ (다운로드 후) |
| `multilingual-e5-large` | 동일 | 무료 + ~2.2GB | ✅ |
| `ko-sroberta-multitask` | 동일 + ~440MB | 무료 | ✅ |
| `cohere` | `cohere` SDK | 호출당 | ❌ |

**핵심 결정**:
- 로컬 모델은 **lazy load** + `@lru_cache` — Token Lab 의 `_encoding_for` 패턴 따라
- 첫 호출 시 다운로드 → 그 다음은 캐싱
- `sentence-transformers` 가 새 의존성 — `requirements.txt` 추가 필요
- 사내 기밀 환경 대응 — 미리 다운로드된 모델만 (`SENTENCE_TRANSFORMERS_HOME` 환경변수)

### Embedding cache (보너스)

Token Lab 처럼:
```python
@lru_cache(maxsize=8)
def _model_for(name: str):
    if name == "bge-m3":
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("BAAI/bge-m3")
    elif name == "gemini":
        return provider_manager.get_embedding_model()  # 기존 재사용
    ...
```

호출당 결과를 Redis 에 캐시하는 건 별도 트랙 — 일단 in-process lru_cache.

---

## 6. 고정 비교 샘플 (학습 페이지 효과)

Token Lab 의 `LANGUAGE_SAMPLES` 처럼 의미 있는 고정 세트:

```python
SEMANTIC_PAIRS = {
    "유사 (동의어/유의어)": [
        ("연차 휴가", "연차 사용"),
        ("가격이 얼마인가요", "비용은 얼마예요"),
        ("camera spec", "촬영 사양"),       # 한·영 매칭
    ],
    "반대 (의미 다름)": [
        ("사과를 먹다", "사과를 받다"),       # 동음이의
        ("배가 고프다", "배를 타다"),
        ("월급 인상", "임금 삭감"),
    ],
    "도메인 jargon": [
        ("3분기 매출", "Q3 revenue"),
        ("CSI", "고객만족도"),
    ],
}
```

기대 결과:
- 좋은 모델: 유사 쌍 > 0.7, 반대 쌍 < 0.5, jargon 쌍 > 0.6
- 한국어 약함 모델: 유사 쌍과 반대 쌍이 비슷한 값 → 변별력 부족

이 결과를 페이지 상단에 표 한 줄로 노출 → 한눈에 모델 우열.

---

## 7. chunk_lab / token_lab 패턴 일관성

세 Lab 이 같은 패턴 따라야 통합 학습 도구:

| 항목 | chunk_lab | token_lab | embedding_lab (제안) |
|---|---|---|---|
| `set_page_config(layout="wide")` | ✓ | ✓ | ✓ |
| `BACKEND_URL` env var | ✓ | ✓ | ✓ |
| 저장·임베딩 부작용 없음 (보안) | ✓ | ✓ | ✓ (in-memory 만) |
| 사이드바 = 입력 / 본문 = 결과 | ✓ | ✓ | ✓ |
| "이 페이지가 무엇을 보여주는가" expander | ✓ | △ | ✓ |
| 결과 시각화 | bar chart | bar chart | heatmap + 2D scatter |
| 고정 sample 비교 | (없음) | ✓ (언어별) | ✓ (semantic pairs) |
| 강의 reference 포함 | ✓ (7강) | ✓ (6강) | ✓ (7강 후반) |

---

## 8. Phased implementation 제안

| Phase | 범위 | 작업량 |
|---|---|---|
| **A. Pair compare 최소 (모드 A 만)** | gemini + bge-m3 + e5 3 모델, 두 문장 비교 | 작음 |
| B. Matrix + UMAP (모드 B 추가) | n×n 매트릭스 + 2D 시각화 | 중 |
| C. Retrieval test (모드 C 추가) | corpus + 질문 → top-k 비교 (Chroma 임시 collection) | 중 |
| D. 고정 sample 비교 | SEMANTIC_PAIRS 자동 평가 표 | 작음 |
| E. UMAP/t-SNE 시각화 | `umap-learn` 의존성 추가 | 작음 |
| F. 영구 결과 저장 (선택) | A/B 비교 결과를 DB 에 기록 | 선택 |

**A + D 만 우선** 권장 — 작업량 작고 학습 효과 큼.

---

## 9. 학습 메모 — 왜 한국어가 약한가

이 페이지가 가르치는 핵심 인사이트:

1. **서브워드 토크나이저의 영향** — BPE/WordPiece 가 한국어 형태소를
   거칠게 쪼개 의미 단위 손실. "꽃이 핀다" → ["꽃", "이", "핀", "다"]
   같은 분해.

2. **학습 데이터 비율** — Common Crawl 등 영어 비율이 80%+. 한국어 데이터
   양 자체가 작아 의미 공간이 평탄.

3. **다국어 모델의 trade-off** — 다국어 임베딩 모델은 언어별 정밀도가
   영어 단일 대비 떨어지지만, **한국어 특화 모델 < bge-m3** 인 경우가
   많음 — bge-m3 가 한·중·일 데이터로 fine-tune.

4. **거리의 분포 차이** — 영어 임베딩은 의미 차이가 0.3~0.9 에 흩어지는
   반면, 한국어 약한 모델은 모든 쌍이 0.6~0.8 에 몰림 → 변별력 부족.

5. **재인덱싱의 비용** — 모델 바꾸면 Chroma 컬렉션 통째로 재구축 필요
   (`build_vectors --rebuild`). 운영에서 가벼운 결정 아님.

---

## 10. 안 한 것 (의도적)

- **실 corpus 자동 평가** — eval set 12 문항 자동 돌려 모델별 recall@5
  표 출력. 기능 좋지만 페이지가 무거워짐. 별도 CLI (`run_embed_ab.py`)
  로 분리.
- **임베딩 차원 비교** — 차원 수 자체보다 의미 포착력이 본질. 표에 dim
  컬럼만 추가하고 직접 비교는 X.
- **Reranker 비교** — embedding 와 reranker 는 다른 단계. Reranker Lab 은
  별도 페이지 (Phase 5+ 후보).
- **다중 언어 자동 번역 매칭** — "사과" 가 "apple" 과 가까운지 검증 흥미롭지만
  메인 시나리오 (한국어 사규 검색) 와 빗나감.

---

## 11. 다음 단계 — 누가 무엇을

| 작업 | 담당 후보 |
|---|---|
| 이 design.md 검토 | 사용자 + 다른 Claude |
| Phase A 구현 (backend endpoint + Streamlit page) | 다른 Claude (UI prototyping) |
| `sentence-transformers` 의존성 추가 + 모델 다운로드 가이드 | Claude Code (cross-file integration) |
| SEMANTIC_PAIRS 한국어 sample set 큐레이션 | 사용자 + 다른 Claude (도메인 지식) |
| 통합 doc `page.md` 작성 (구현 완료 후) | Claude Code |

---

## 관련 문서

- [chunking/lab_page.md](../chunking/lab_page.md) — chunk_lab 패턴 참조
- [token_lab/page.md](../token_lab/page.md) — token_lab 패턴 참조
- [../../architecture/core_concepts.md](../../architecture/core_concepts.md) — 임베딩(A2) + 한국어 약점 개념
- [../../reports/learning_journey.html](../../reports/learning_journey.html) — 학습 가이드 §2 임베딩
- [../providers/architecture.md](../providers/architecture.md) — 현재 provider 추상 (재사용 대상)
- [../providers/switching_result.md](../providers/switching_result.md) — provider 스위칭 (모델 가용성 참조)
