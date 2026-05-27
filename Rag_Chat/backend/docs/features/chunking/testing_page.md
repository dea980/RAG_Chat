# Chunking Testing Page — 설계 메모

> 의견: "chunking 의 테스팅 페이지가 필요할 것 같기도 하고..."
> 동의. 이미 CLI 기반 A/B (`run_chunk_ab.py`) 와 결과 문서
> (`chunk_experiment.md`) 가 있지만 **새 파일/새 splitter 들어왔을 때 즉시
> 비교할 인터랙티브 UI 가 없다.** 7강 강사가 200/500/1000 자 비교하던 그
> 작업을 누구나 클릭으로 재현할 수 있는 페이지가 한 장 필요.

---

## 1. 현재 자산

| 자산 | 위치 | 한계 |
|---|---|---|
| 12 문항 eval set | `chat/tests/evals/dataset.jsonl` | 정답이 사전 정의됨 — 신규 자료로 못 씀 |
| BM25 기반 A/B | `chat/tests/evals/run_chunk_ab.py` | CLI 출력만, 즉각 시각화 ✕ |
| 결과 보고서 | `docs/chunk_experiment.md` | 정적 markdown, 한 번 찍힌 결과 |
| Streamlit 챗봇 | `frontend/` | 검색 UX 는 있지만 ingest/chunking 노출 ✕ |

신규 자료(PDF, HWP) 가 들어왔을 때 *그 자료의 적정 chunk_size* 를 빠르게
확인할 수단이 없다. 7강 강사처럼 손으로 200 → 500 → 1000 → "조항 단위"
로 바꿔가며 봐야 하는데, 매번 코드 수정·재실행은 비효율.

---

## 2. 무엇을 테스트하는 페이지인가

### 핵심 비교 축

1. **chunk_size**: 80 / 150 / 250 / 500 / 1000
2. **chunk_overlap**: 0 / 30 / 80 / 150 / 200
3. **splitter 전략**: recursive / heading / clause / row
4. **임베딩 모델**: text-embedding-004 vs bge-m3 vs multilingual-e5
   (강사가 짚은 한국어 약점 검증)

### 측정 지표

- **시각 — 청크 미리보기**: 청크 단위로 어떻게 잘렸는지 1청크씩 카드 표시
- **정량 — retrieval 정확도**: 사용자가 입력한 질문에 대해 top-k 청크의
  코사인 유사도 + 정답 청크 rank
- **사이즈 분포**: 청크 길이 히스토그램 (편차가 크면 splitter 가 이상함)
- **시각화 — 청크 간 거리**: 7강 후반의 그 산점도 (UMAP/t-SNE 2D 투영)

---

## 3. 구현 옵션 비교

| 옵션 | 장점 | 단점 | 작업량 |
|---|---|---|---|
| **A. Streamlit 페이지 추가** | 이미 frontend stack. 파일 업로드/시각화 위젯 풍부 | Streamlit 이 frontend 서버라 backend 와 직접 ingest 호출은 API 또는 같은 venv 필요 | 중 |
| **B. Django Admin 커스텀 뷰** | 인증/권한 자연스러움. backend 와 같은 venv | 위젯 빈약. 파일 업로드 후 시각화는 직접 구현 | 중 |
| **C. Jupyter notebook** | 가장 빠른 프로토타이핑. 결과 그대로 저장 | 운영자가 못 씀 (개발자 전용) | 소 |
| **D. CLI 강화 (현재 + HTML 리포트)** | 기존 자산 확장. CI 와도 연동 가능 | 인터랙티브성 부족 | 소 |

### 권장: A (Streamlit) — 운영자 노출 필요할 때 / C (Notebook) — 개발자 실험용

둘 다 만들 가치 있음. C는 1회성 빠른 답, A는 영구 도구.

---

## 4. Streamlit 페이지 — 상세 스케치

위치: `frontend/pages/chunk_lab.py` (Streamlit multi-page 패턴)

```python
# 의사 코드 — 실제 구현은 별도 PR
import streamlit as st
from backend_api import ingest_preview, search   # /api/v1/ingest/preview 호출

st.title("Chunk Lab")

uploaded = st.file_uploader("문서 업로드 (PDF/CSV/DOCX/HWP)")
col1, col2, col3 = st.columns(3)
chunk_size = col1.slider("chunk_size", 50, 2000, 500, step=50)
chunk_overlap = col2.slider("overlap", 0, 500, 100, step=10)
splitter = col3.selectbox("splitter", ["recursive", "heading", "clause", "row"])

if uploaded:
    chunks = ingest_preview(uploaded, chunk_size, chunk_overlap, splitter)
    st.metric("청크 개수", len(chunks))
    st.bar_chart([len(c["content"]) for c in chunks])     # 사이즈 분포

    for i, c in enumerate(chunks[:20]):
        with st.expander(f"chunk {i} · {len(c['content'])}자 · {c.get('section', '')}"):
            st.code(c["content"])

    st.divider()
    question = st.text_input("검색 테스트 질문")
    if question:
        hits = search(question, k=5)
        for h in hits:
            st.write(f"score: {h['score']:.3f}")
            st.code(h["content"])
```

### 필요한 backend 엔드포인트 (신규)

```
POST /api/v1/ingest/preview
  body: { file (multipart), chunk_size, chunk_overlap, splitter }
  → { chunks: [{ content, section, metadata, len }] }
  ※ 임베딩 X, 저장 X — 미리보기 전용
```

```
POST /api/v1/ingest/preview_with_search
  body: { ... + question, embedding_model }
  → { chunks, hits: [{ content, score, rank }] }
  ※ 임시 in-memory Chroma collection 만들어서 검색까지
```

Phase 1 layer 가 이미 `RawDoc` / splitter / loader 를 가지고 있으므로
endpoint 는 그 위에 얇은 wrapper.

---

## 5. Notebook (개발자용) — 우선 만들 것

빠르게 효과 보려면 notebook 부터:

```
backend/notebooks/chunk_lab.ipynb
```

내용:
1. 파일 경로 입력
2. loader_for / splitter 선택 → 청크 리스트
3. matplotlib 으로 길이 히스토그램
4. 옵션: 임시 Chroma 만들어 질문 vs 청크 유사도 산점도 (UMAP)
5. 다른 chunk_size 로 셀 재실행 비교

Streamlit 페이지 만들기 전 단계로 가장 ROI 높음. 사용자가 직접 만지면서
"이 문서에는 어떤 splitter 가 맞는가" 를 손으로 익히기에도 적합 — 강의
포맷의 인터랙티브 버전.

---

## 6. CI 통합 (별도 트랙)

`chunk_experiment.md` 갱신을 자동화:

- `run_chunk_ab.py` 에 신규 dataset 받는 옵션 추가
- GitHub Actions workflow `chunk-ab-report.yml` 가 PR 마다 결과 markdown
  생성 → 아티팩트로 업로드
- 결과 표를 PR comment 로 자동 코멘트 (bot)

이건 운영자 도구가 아닌 **regression 감지** 목적. Streamlit/Notebook 과
독립.

---

## 7. 우선순위 제안

| 순서 | 항목 | 이유 |
|---|---|---|
| 0 | Phase 2 Manifest | 실제 ingest 경로 오염 방지. preview 자체는 저장하지 않지만 loader 실험 전 안전망 |
| 1 | Notebook (`chunk_lab.ipynb`) | 가장 빠르게 학습용으로 작동 |
| 2 | `/api/v1/ingest/preview` 엔드포인트 | Streamlit 의 데이터 공급선. 임베딩/저장 없이 미리보기만 |
| 3 | Streamlit `chunk_lab.py` 페이지 | 운영자도 쓰는 영구 도구 |
| 4 | CI report 자동화 | 정량 회귀 감지 |

각 단계가 다음 단계의 의존이므로 순차 진행 권장. 1~2 는 같은 PR 가능.

---

## 8. 비기능 요구

- **샘플 데이터 sandbox**: 업로드한 PDF 가 영구 적재되면 안 됨 — 임시 in-memory
  Chroma collection 만 쓰고 페이지 닫히면 폐기. 사내 기밀 보호.
- **권한**: Admin / Manager 만. USER 권한은 차단 (이미 role 모델 있음).
- **성능**: 청크 미리보기는 임베딩 없으니 빨라야 함. 100MB PDF 면 OCR 안
  도는 한 수 초 내.
- **다국어 폰트**: matplotlib/Streamlit 차트에서 한글 안 깨지게 NanumGothic
  등록.

---

## 9. 결론

필요하다. 단, 두 가지를 따로 봐야 한다:
- **개발자가 새 자료/splitter 실험할 도구** → notebook
- **운영자가 신규 문서 ingest 전에 청킹 미리보기** → Streamlit + API

ingest layer Phase 1 이 깔려 있어 preview 도구를 만들 기반은 있다. 다만
실제 Chroma ingest 를 오염시키지 않으려면 Phase 2 Manifest 를 먼저 끝내고,
그 다음 Phase 3 (PDF loader) 와 함께 notebook/API preview 를 붙이는 순서가
가장 안전하다.
