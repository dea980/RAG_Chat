# Comparison Labs 확장 — gpt-oss 토큰 비교 + Chat Compare + Embedding Lab

## 한 줄 요약

같은 입력을 여러 모델·전략에 동시에 보내고 결과를 나란히 비교하는 **lab 페이지 3종**을 확장 — token_lab 에 gpt-oss 프로파일 추가, chat_compare 새 페이지, embedding_lab Mode A 실제 구현.

## 비유 — 와인 시음대

와인 비교 시음회를 떠올려보자:

| 시음대 | 같은 무엇을 | 다른 모델로 측정 |
|---|---|---|
| chunk_lab | 같은 문서 | splitter 4종이 어떻게 쪼개나 |
| token_lab | 같은 문장 | tokenizer 별로 토큰이 몇 개 |
| **chat_compare** (신규) | 같은 프롬프트 | LLM 별로 응답이 어떻게 다른가 |
| **embedding_lab** (신규) | 같은 두 텍스트 | embedding 모델 별로 유사도 점수 |

각 lab 은 **저장·부작용 없는 시음대** — RAG/DB/moderation 우회. 그래야 모델 자체의 특성만 깨끗하게 비교된다.

## 왜 이게 필요한가

| | 변경 전 | 변경 후 |
|---|---|---|
| **gpt-oss 토큰 비교** | token_lab 에 5개 profile (openai_o200k/cl100k/p50k/gemini/claude/qwen). gpt-oss 빠짐 | 6번째 profile `gpt_oss_estimate` 추가 (o200k_harmony 기반). frontend selectbox 도 갱신 |
| **LLM 응답 비교** | `chat.py` 가 단일 모델, full RAG/moderation/DB. 비교 시 매번 .env 바꿔 재기동 | `/chat/compare/` 새 엔드포인트 + `chat_compare.py` 새 페이지. 한 화면에서 N 모델 동시 호출 |
| **임베딩 모델 비교** | 페이지 자체 없음. `EMBEDDING_PROVIDER` env 바꾸고 corpus 재인덱싱해야 비로소 확인 가능 | `/embeddings/compare/` 새 엔드포인트 + `embedding_lab.py` 새 페이지. 두 텍스트 입력 → 모델별 cosine 한 줄 |
| **신규 모델 추가** | env 변경 + 코드 새로 추적 | embedding_lab 은 `EMBEDDING_REGISTRY` 한 줄 추가. chat_compare 는 `provider:model` 문자열 spec |

핵심 가치: 모델 교체 결정을 **데이터로 한다**. 강사 7강의 "임베딩 모델 바꾸니 39조 찾음" 시나리오를 페이지에서 재현 가능.

## 핵심 코드

### 1. Chat Compare — `ProviderManager.build_chat_model_explicit`

```python
# backend/chat/providers/manager.py
def build_chat_model_explicit(self, provider, model=None, purpose="GENERATION"):
    # model 이 None 이면 기존 env-based factory 호출
    if model is None:
        return self._create_chat_model(provider, purpose)
    # model 명시 시 ChatOpenAI/ChatGoogleGenerativeAI 를 직접 빌드
    if provider == "ollama":
        return ChatOpenAI(base_url=os.getenv("OLLAMA_BASE_URL", ...), model=model, ...)
```

- `model=None` → 기존 동작 (env override 체인 사용)
- `model="gpt-oss"` → 명시 모델로 즉시 생성 — **캐싱 안 함** (compare 호출은 동적 model 이라 cache key 충돌)

### 2. Embedding Lab — 등록 패턴

```python
# backend/chat/embedding_views.py
EMBEDDING_REGISTRY = {
    "bge-m3":      {"kind": "embedding", "model_id": "BAAI/bge-m3",  "handler": _embed_st_pair, ...},
    "gemini":      {"kind": "embedding", "handler": _embed_gemini_pair, ...},
    "reranker-bge":{"kind": "cross",     "handler": _score_reranker_pair, ...},  # 기존 ONNX 재사용
}
```

- `kind: "embedding"` — 벡터 2개 만들고 cosine
- `kind: "cross"` — reranker 가 (text1, text2) 점수 바로 산출 (단위 다름 주의)
- 신규 모델 = registry dict 에 한 줄. 코드 흐름은 안 바뀜.

## 데이터 흐름

### chat_compare

```
frontend/pages/chat_compare.py
    │  POST { prompt, models: ["ollama:gpt-oss", "ollama:qwen3.6", "gemini"] }
    ▼
backend/chat/compare_views.py  ChatCompareAPIView.post
    │  for spec in models:
    │      provider, model = _parse_spec(spec)            # "ollama:gpt-oss" → ("ollama", "gpt-oss")
    │      chat = manager.build_chat_model_explicit(provider, model)
    │      result = chat.invoke([HumanMessage(content=prompt)])  ← LLM 직접 호출 (RAG/moderation/DB 없음)
    ▼
Response { results: [{spec, response, elapsed_ms}, ...] }
    ▼
frontend: st.columns(N) 으로 응답 나란히 표시
```

### embedding_lab

```
frontend/pages/embedding_lab.py
    │  POST { text1, text2, models: ["gemini", "bge-m3", "e5-large", "reranker-bge"] }
    ▼
backend/chat/embedding_views.py  EmbeddingCompareAPIView.post
    │  for key in models:
    │      spec = EMBEDDING_REGISTRY[key]
    │      result = spec["handler"](spec["model_id"], text1, text2)
    │          kind=embedding → SentenceTransformer.encode → _cosine(v1, v2)
    │          kind=cross     → OnnxBgeReranker.score(text1, [text2]) → 점수 그대로
    ▼
Response { results: { "bge-m3": {kind, score, dim}, ... } }
    ▼
frontend: dataframe + bar_chart + 해석 가이드
```

## 확인 방법

### Token Lab (Phase B) — backend
```bash
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -m pytest chat/tests/test_token_utils.py -v
# expected: 2 passed
```

### URL 라우팅 / 임포트 smoke
```bash
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -c "
import django; django.setup()
from chat.urls import urlpatterns
for u in urlpatterns:
  if hasattr(u,'name') and ('compare' in (u.name or '') or 'embed' in (u.name or '')):
    print(u.pattern, '->', u.name)
"
# expected:
# chat/compare/         -> chat-compare
# embeddings/compare/   -> embedding-compare
```

### 수동 검증 — Streamlit 페이지
1. backend 기동 (`python manage.py runserver`)
2. ollama 기동 + `ollama pull qwen3.6 gpt-oss` 완료 상태
3. streamlit 기동 → `Chat Compare` 페이지 → 프롬프트 입력 → `ollama:qwen3.6` vs `ollama:gpt-oss` 응답 비교
4. `Embedding Lab` 페이지 → 샘플 쌍 "유사1: 연차 휴가 vs 연차 사용" → bge-m3 / gemini / reranker-bge 점수 비교

### sentence-transformers 첫 호출
```bash
# bge-m3 / e5-large 첫 호출 시 ~2GB 다운로드 발생
# 폐쇄망: SENTENCE_TRANSFORMERS_HOME=/path/to/cache 미리 지정
pip install sentence-transformers>=2.7.0
```

## 연습 문제

1. **신규 ollama 모델 추가**: `ollama pull mistral` 한 뒤, `chat_compare.py` 에서 `KNOWN_MODELS["ollama"]` 리스트에 `"mistral"` 한 줄을 추가하라. 백엔드 코드는 손대지 않아도 동작해야 한다. *왜* 백엔드 변경이 불필요한지 한 줄로 설명. (힌트: `build_chat_model_explicit` 의 ollama 분기는 model 명을 그대로 ChatOpenAI 에 넘긴다)

2. **embedding 모델 추가**: `embedding_views.py` 의 `EMBEDDING_REGISTRY` 에 `"ko-sroberta-multitask"` (한국어 특화, ~440MB) 를 추가하라. 기존 `_embed_st_pair` handler 를 재사용할 수 있는가, 새 handler 가 필요한가? (힌트: sentence-transformers 인터페이스 일치 여부 확인)

3. **chat_compare 의 'RAG 없음' 의미**: production `chat.py` 가 같은 프롬프트로 답할 때와, `chat_compare.py` 가 답할 때 무엇이 다른가? 그 차이가 lab 의 *정확한* 가치를 어떻게 보장하는지 100자 이내로 설명.

## 변경 파일 목록

| 파일 | Phase | 변경 |
|---|---|---|
| `backend/chat/token_utils.py` | B | `ESTIMATE_PROFILES` 에 `gpt_oss_estimate` 추가 |
| `frontend/pages/token_lab.py` | B | selectbox 에 gpt-oss 옵션 + 계산 방식 expander 갱신 |
| `backend/chat/providers/manager.py` | A | `build_chat_model_explicit` 메서드 추가 |
| `backend/chat/compare_views.py` | A | new — `ChatCompareAPIView` |
| `backend/chat/urls.py` | A, C | `/chat/compare/`, `/embeddings/compare/` 라우트 추가 |
| `frontend/pages/chat_compare.py` | A | new — N-col 사이드바이사이드 |
| `backend/chat/embedding_views.py` | C | new — Mode A + `EMBEDDING_REGISTRY` |
| `frontend/pages/embedding_lab.py` | C | new — Mode A UI |
| `backend/requirements.txt` | C | `sentence-transformers>=2.7.0` append |
| `backend/docs/features/embedding_lab/page.md` | C | skeleton → 실 구현 노트로 갱신 |

## 관련 문서

- [`../features/embedding_lab/design.md`](../features/embedding_lab/design.md) — 본 작업의 spec (Mode B/C/D 는 미구현 — Phase 다음)
- [`../features/embedding_lab/page.md`](../features/embedding_lab/page.md) — 실 구현 후 통합 노트
- [`../features/providers/architecture.md`](../features/providers/architecture.md) — ProviderManager 추상의 lab 활용 예
- [`../sessions/night/T2.work.md`](../sessions/night/T2.work.md) — 같은 날 야간의 chunk_lab heading/clause 작업 (lab 4종 라인업 완성의 다른 한 축)
