# Embedding Lab — Page 통합 노트

> **상태**: ✅ Mode A (Pair Compare) 구현 완료 (2026-05-28). Mode B/C/D 미구현 — [`design.md`](design.md) §8 참조.

## 1. 구현된 범위

- ✅ **Mode A (Pair Compare)** — 두 텍스트 → 모델별 cosine 유사도 한 줄.
- ✅ **모델 4종** (등록 패턴):
  - `gemini` — text-embedding-004 (기존 provider 재사용)
  - `bge-m3` — `BAAI/bge-m3` (sentence-transformers, ~2GB 첫 다운로드)
  - `e5-large` — `intfloat/multilingual-e5-large` (sentence-transformers, ~2GB)
  - `reranker-bge` — 기존 ONNX `BAAI/bge-reranker-v2-m3` cross-encoder 재사용 (벡터 X, score 직접)
- ✅ **Lazy load + `@lru_cache`** — `_load_st_model`, `_load_gemini_embedder`, `_load_onnx_reranker`
- ✅ **API endpoint** — `POST /api/v1/triple/embeddings/compare` + `GET` (등록 모델 목록)
- ✅ **Streamlit page** — `frontend/pages/embedding_lab.py`
- ✅ **고정 SEMANTIC_PAIRS sample** — `design.md` §6 의 한국어 유사/반대/jargon 쌍 5종 frontend sidebar 에 노출

## 2. 검증된 호출 경로

```python
# backend/chat/embedding_views.py
class EmbeddingCompareAPIView(APIView):
    def post(self, request):
        text1 = request.data.get("text1", "").strip()
        text2 = request.data.get("text2", "").strip()
        models = request.data.get("models", [])
        for key in models:
            spec = EMBEDDING_REGISTRY[key]
            handler = spec["handler"]                  # _embed_st_pair / _embed_gemini_pair / _score_reranker_pair
            results[key] = handler(spec["model_id"], text1, text2)
        return Response({"text1": text1, "text2": text2, "results": results})
```

호출 예시:
```bash
curl -X POST http://localhost:8000/api/v1/triple/embeddings/compare/ \
  -H 'Content-Type: application/json' \
  -d '{"text1":"연차 휴가","text2":"연차 사용","models":["gemini","bge-m3","reranker-bge"]}'
```

응답 형태:
```json
{
  "text1": "연차 휴가",
  "text2": "연차 사용",
  "results": {
    "gemini":       {"kind": "cosine", "score": 0.81, "dim": 768,  "label": "Gemini text-embedding-004 (현재 default)"},
    "bge-m3":       {"kind": "cosine", "score": 0.87, "dim": 1024, "label": "BAAI/bge-m3 (다국어, 한국어 강함)"},
    "reranker-bge": {"kind": "cross",  "score": 5.12,              "label": "ONNX bge-reranker-v2-m3 (cross-encoder)"}
  }
}
```

`GET /embeddings/compare/` 호출 시 등록 모델 목록 반환 — frontend dropdown 자동 갱신.

## 3. 학습 메모 — 무엇을 가르치나

design.md §9 의 "한국어 약점" 5가지를 본 페이지로 측정 가능:

1. **서브워드 토크나이저의 영향** — 같은 한국어 쌍을 multilingual 모델 vs OpenAI(o200k) 로 돌렸을 때 점수 차이로 가시화. (직접 비교는 추가 모델 등록 시 가능)
2. **학습 데이터 비율** — 한국어/영어 평행 쌍 ("3분기 매출" vs "Q3 revenue") 점수가 bge-m3 ≫ gemini 면 다국어 학습량 차이 증거.
3. **다국어 vs 한국어 특화** — bge-m3 vs ko-sroberta 비교는 모델 등록 시 가능 (연습 문제 2 참조).
4. **거리 분포 차이** — 유사 쌍과 반대 쌍의 점수 차가 크면 변별력 강함. SEMANTIC_PAIRS 5종 sample 로 한눈에 확인.
5. **재인덱싱 비용** — 본 페이지는 *in-memory* 비교만 — 모델 교체 후 corpus 재인덱싱 비용은 별도. 페이지 상단 경고는 아직 노출 안 함 (다음 작업).

## 4. chunk_lab / token_lab 패턴 일관성

| 항목 | embedding_lab | 상태 |
|---|---|---|
| `set_page_config(layout="wide")` | ✅ |
| `BACKEND_URL` env var (fallback 8000) | ✅ |
| 사이드바 = 입력 / 본문 = 결과 | ✅ |
| "이 페이지가 무엇" expander | ✅ |
| 저장·임베딩 부작용 없음 (in-memory) | ✅ — `EMBEDDING_REGISTRY` 가 lru_cache 로 모델만 캐시, 결과 저장 없음 |
| 강의 7강 reference | ✅ — page caption + design.md §1 |
| 고정 sample 비교 | ✅ — `SEMANTIC_PAIRS` 5종 sidebar selectbox |

## 5. 안 한 것 (의도적, 다음 phase)

`design.md` §8 의 phase 진행:

- ❌ **Phase B — Matrix (n×n 히트맵)** — 미구현
- ❌ **Phase C — Retrieval Test (corpus + 질문)** — 미구현
- ❌ **Phase D — 고정 sample 자동 평가** — frontend sidebar 에 sample 선택은 노출했으나 자동 평가표는 아직
- ❌ **Phase E — UMAP/t-SNE 2D 투영** — 미구현
- ❌ **Phase F — 영구 결과 저장** — 의도적 보류 (lab 페이지 본분)

각각 별도 작업 단위.

## 6. 다음 세션 처리 사항

- [x] `requirements.txt` 의 `sentence-transformers>=2.7.0` 추가됨 (line 추가). T3 의 `pytesseract` 와 충돌 없음 — 둘 다 append 라 trivial.
- [ ] **첫 호출 시 ~2GB 모델 다운로드 UX**: 현재 단순 `st.spinner` 만. 진행률 / 사이즈 안내 추가 검토 (다음 phase).
- [ ] **공통 헬퍼 추출**: chunk_lab / chat_compare / embedding_lab 모두 "sidebar 입력 + N-col 결과" 패턴 — DRY 가능. but **페이지별 자유도** 가 더 가치 있다는 의견. 일단 추출 보류.
- [ ] **추가 모델 등록 예시**: `ko-sroberta-multitask`, `cohere-multilingual-v3` 등 — registry 한 줄로 가능 ([연습 문제 2](../../learning/2026-05-28-comparison-labs-extend.md#연습-문제)).
- [ ] **모델 등록 자동 검증**: registry 의 model_id 가 실제 다운로드 가능한지 startup 시 ping (선택).

## 관련 문서

- [`design.md`](design.md) — Phase A spec (구현 완료 부분)
- [`../../learning/2026-05-28-comparison-labs-extend.md`](../../learning/2026-05-28-comparison-labs-extend.md) — 본 작업 학습 노트
- [`../chunking/lab_page.md`](../chunking/lab_page.md) — 패턴 reference (chunk_lab)
- [`../token_lab/page.md`](../token_lab/page.md) — 패턴 reference (token_lab)
- [`../../architecture/core_concepts.md`](../../architecture/core_concepts.md) — A2 임베딩 개념
- [`../../sessions/2026-05-27-night-parallel.md`](../../sessions/2026-05-27-night-parallel.md) — skeleton 이 만들어진 야간 분배
