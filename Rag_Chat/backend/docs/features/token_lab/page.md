# Token Lab — 토큰 비교 페이지 (다른 agent 작업 통합 기록)

> 6강(LLM 기초) 의 토큰화 단원을 인터랙티브로 재현하는 페이지.
> 다른 agent (Codex 또는 별도 Claude 세션) 가 추가한 모듈을 프로젝트 맥락에
> 통합하기 위한 기록 — 패턴/네이밍 일관성 확인 + 작은 불일치 노트.

---

## 1. 추가된 파일

```
backend/chat/token_utils.py          # tiktoken 기반 정확 카운트 + 추정 multiplier
backend/chat/token_views.py          # POST /api/v1/triple/tokens/estimate/
backend/chat/urls.py                 # 라우트 등록
frontend/pages/token_lab.py          # Streamlit 페이지
```

## 2. 무엇을 보여주는가

6강 강의에서 짚은 두 가지 현상을 인터랙티브로 확인:

1. **같은 모델이 같은 텍스트를 어떻게 토큰화하는가** — `tiktoken` 의
   `o200k_base` / `cl100k_base` / `p50k_base` 인코딩 결과 비교
2. **한국어는 영어보다 토큰을 더 많이 먹는다** — 6개 고정 샘플 (한/영/일/중/
   코드/혼합) 의 `tokens / char` 비율 비교

부가로:
- **RAG chunk 추천**: 기준 모델(cl100k) 토큰 기준 250/500/1000/2000 토큰
  청크면 몇 개 만들어지는가 — `chunk_lab_page.md` 와 짝지어 보면 chunk_size
  결정에 정량 근거
- **Gemini / Claude / Qwen estimate**: 실 tokenizer 가 달라 정확 계산 불가
  → OpenAI 카운트에 multiplier 적용한 추정치로 표기 (UI 에 "estimate" 명시)

## 3. 새 엔드포인트

`POST /api/v1/triple/tokens/estimate/`

**Body (JSON)**:
```json
{ "text": "...", "include_samples": true }
```

**Response 200**:
```json
{
  "analysis": {
    "text_preview": "first 160 chars",
    "characters": 42,
    "bytes": 126,
    "reference_profile": "openai_cl100k",
    "reference_tokens": 38,
    "profiles": [
      {"id": "openai_o200k", "label": "GPT-4o / o-series",
       "tokens": 35, "tokens_per_character": 0.833,
       "method": "exact", "tokenizer": "o200k_base", "note": "..."},
      ...
    ],
    "chunk_recommendations": [
      {"target_tokens": 250, "estimated_chunks": 1},
      {"target_tokens": 500, "estimated_chunks": 1}
    ]
  },
  "language_samples": [...]
}
```

`method` 값:
- `"exact"` — tiktoken 인코딩 적용
- `"fallback"` — tiktoken 없거나 인코딩 캐시 미스 → `ceil(bytes / 4)` 보수적 추정
- `"estimate"` — Gemini/Claude/Qwen — exact 카운트에 multiplier

## 4. 사용법

```bash
# 터미널 1 — backend
cd Rag_Chat/backend && ./venv/bin/python manage.py runserver

# 터미널 2 — frontend
cd Rag_Chat/frontend && streamlit run app.py
# → http://localhost:8501 사이드바에서 'token_lab' 선택
```

오프라인 안전성: `tiktoken.get_encoding` 이 인코딩 파일을 로컬에서 못 찾으면
네트워크 fetch 를 시도하는데, `_encoding_for()` 가 그 예외를 잡아 fallback
계산으로 떨어진다. **API key 도, 네트워크도 불필요.**

## 5. chunk_lab 과의 관계

두 페이지는 RAG 파이프라인의 다른 단면을 다룬다:

| 페이지 | 무엇을 측정 | 언제 쓰나 |
|---|---|---|
| **chunk_lab** | splitter 가 텍스트를 어떻게 자르는가 (글자 단위) | 신규 문서 들어왔을 때 적정 chunk_size 결정 |
| **token_lab** | 같은 텍스트가 모델별로 몇 토큰 (토큰 단위) | LLM 비용/컨텍스트 윈도우 예측, 한국어 효율 확인 |

**연결고리** — `chunk_lab` 이 보여주는 청크가 `token_lab` 의 chunk_recommendations
에서 권장한 토큰 수에 부합하는가? 추후 두 페이지를 합쳐 "이 chunk_size 는
이 모델 기준 평균 N 토큰" 을 보여주는 통합 뷰가 자연스러운 다음 단계.

## 6. 일관성 노트 — 다른 페이지와 비교

다른 agent 작업과 통합하면서 발견한 작은 불일치들. 시급하진 않지만 향후
정리 시 참고:

### 6.1 `API_BASE` 환경변수 처리

`chunk_lab.py`:
```python
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1/triple")
```

`token_lab.py`:
```python
API_BASE = os.getenv("API_BASE_URL") or (
    os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
)
```

token_lab 가 더 유연 (BACKEND_URL fallback 지원). **권장: chunk_lab 도 동일
패턴으로 정렬**. 도커 환경에서 `BACKEND_URL=http://backend:8000` 식으로
서비스 이름만 주입하면 양쪽 페이지가 자동 동작.

### 6.2 `permission_classes`

`token_views.IngestEstimateAPIView`: `permission_classes = [AllowAny]` 명시.

`ingest_views.IngestPreviewAPIView`: 명시 없음 — DRF 기본값에 의존.

기본값이 `DEFAULT_PERMISSION_CLASSES` 설정에 따라 달라질 수 있으므로
**preview 류 anonymous API 는 명시적으로 `AllowAny` 를 박는 게 안전**.
미세 차이지만 같은 카테고리의 두 endpoint 가 다른 권한 분기를 타지 않게.

### 6.3 응답 키 네이밍

| 항목 | chunk_lab | token_lab |
|---|---|---|
| 메타 정보 위치 | top-level (`source`, `num_chunks`) | nested (`analysis.characters`, ...) |
| 주 데이터 | `chunks: [...]` | `analysis.profiles: [...]` |
| 부가 데이터 | (없음) | `language_samples: [...]` |

분석성 데이터 (multiple profiles, multiple samples) 가 있는 token_lab 은
nested 가 자연스러움. chunk_lab 은 단일 결과라 flat. **둘 다 합리적, 통일
강제 불필요.** 단 다음 페이지가 들어올 때 어느 쪽 패턴 따를지 사전 결정.

## 7. 학습 메모

- **tiktoken 의 네트워크 동작**: `o200k_base` 같은 일부 인코딩은 첫 사용
  시 BPE rank 파일을 다운로드한다. 운영 환경이 인터넷 단절이면 이 호출이
  실패 → 그래서 `_encoding_for` 가 broad except 로 감싸 fallback 으로 떨어진다.
  사내 기밀 환경에서도 동작 보장.
- **estimate vs exact 명시**: UI 가 method 컬럼으로 "exact" / "fallback" /
  "estimate" 를 노출 — 사용자가 숫자를 절대값으로 오해하지 않도록. 6강
  강사가 "확률적이기 때문에 이게 어 ..." 라며 강조한 부분의 대응.
- **fixed 언어 샘플**: 모든 사용자가 같은 한 문장으로 비교 → 한국어 토큰
  비효율이 일관되게 보임. 자유 입력만 두면 결과가 흔들려 학습 효과 떨어짐.
- **`@lru_cache(maxsize=8)`**: 인코딩 로드는 한 번이면 충분. 여러 요청에서
  같은 인코딩 객체 재사용 → 응답 빠름.

## 8. 안 한 것 (의도적)

- **사내 LLM(로컬) 토큰화 비교** — vLLM/Ollama 의 tokenizer 가 있어야 하므로
  의존성이 무거워짐. 분류 4 (CAD/HWP) 작업과 묶어 별도 트랙.
- **실시간 cost 환산** — 모델별 가격 변동성이 커서 정적 표는 stale 위험.
  필요해지면 `chat/providers/` 의 price catalog 와 연동.
- **저장/로그** — Token Lab 은 일회성 실험 도구. 호출 기록 안 남김.

---

## 관련 문서

- [chunk_lab_page.md](chunk_lab_page.md) — 청크 splitter 비교 페이지
- [ingest_layer.md](ingest_layer.md) — 전체 ingest 설계 (Token Lab 은 ingest 와 독립)
- [chunk_experiment.md](chunk_experiment.md) — CLI 기반 청크 A/B (정량 회귀 감지)
