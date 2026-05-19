# OpenRouter 평가 리포트 — Provider 결정 근거

> 2026-05-18 · provider 추상화 검증 사례

## 1. 가설

영업팀 챗봇의 LLM 공급망을 **단일 API 키 + 다양한 free-tier 모델**로 통일할 수 있는지 검증하기 위해 [OpenRouter](https://openrouter.ai)를 1차 후보로 평가했다.

기대 효과:
- 단일 키로 Qwen3 / Llama 3.3 / Nemotron 등 free-tier 모델 한 번에 접근
- vendor lock-in 회피 — 미래에 다른 모델로 갈아끼울 때 endpoint URL만 변경
- Gemini 한 곳으로 모든 데이터를 보내지 않는 *공급망 분산*

## 2. 검증 절차

### 2-1. 환경
- `.env` 에 `OPENROUTER_API_KEY` + `OPENROUTER_BASE=https://openrouter.ai/api/v1` 설정
- `provider_manager.py` 에 OpenRouter 분기 추가 (`langchain_openai.ChatOpenAI` / `OpenAIEmbeddings` 재사용 — OpenAI 호환 endpoint)
- 후보 모델 (사용자 OpenRouter 페이지에서 확인한 ID):
  - Embedding: `nvidia/llama-nemotron-embed-v1-1b-v2:free`
  - Reasoning: `qwen/qwen3-235b-a22b:free`
  - Generation: `nvidia/nemotron-nano-9b-v2:free`

### 2-2. 자동화 검증

```python
# OpenRouter 전체 모델 listing
GET https://openrouter.ai/api/v1/models  → 356 models

# 'embed' / 'nemotron' / 'nvidia' 필터
nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free   modality: text → text
nvidia/nemotron-3-super-120b-a12b:free               modality: text → text
nvidia/nemotron-nano-9b-v2:free                      modality: text → text
nvidia/llama-3.3-nemotron-super-49b-v1.5             modality: text → text
... (총 9개 nvidia 모델)
```

**모든 모델의 `architecture.output_modalities` 가 `['text']`** — chat completion 전용. **embedding output을 가진 모델 0개**.

### 2-3. 직접 embedding API 호출

```
POST /api/v1/embeddings  { "model": "nvidia/llama-nemotron-embed-v1-1b-v2:free", "input": "hello" }
→ HTTP 400 { "error": { "message": "Model nvidia/llama-nemotron-embed-v1-1b-v2 does not exist" } }

POST /api/v1/embeddings  { "model": "nvidia/llama-nemotron-embed-v1-1b-v2", ... }
→ HTTP 400 (동일)

POST /api/v1/embeddings  { "model": "nvidia/nemoretriever-llama3.2-embed-v2", ... }
→ HTTP 400 (동일)
```

## 3. 발견

| 항목 | 결과 |
|------|------|
| OpenRouter는 *production endpoint* 에서 embedding 모델을 지원하는가? | **사실상 미지원** (2026-05 시점) |
| 공식 페이지에 보이는 embedding 모델 ID는 작동하는가? | ❌ 모든 시도가 HTTP 400 |
| Chat completion (Qwen, Nemotron 등) 은? | ✅ 정상 |

OpenRouter는 **chat completion 게이트웨이가 본업**이며 embedding은 docs/listing 페이지에 일부 노출되지만 API 차원에서는 지원되지 않거나 제한적.

## 4. 결정 — Gemini 단독 통일

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| EMBEDDING_PROVIDER | openrouter | **gemini** (`models/gemini-embedding-001`) |
| REASONING_PROVIDER | openrouter (qwen3-235b) | **gemini** (`gemini-1.5-flash`) |
| GENERATION_PROVIDER | openrouter (nemotron-nano) | **gemini** (`gemini-1.5-flash`) |
| 필요 키 | OPENROUTER + GOOGLE | **GOOGLE 단일** |

## 5. 코드 변경 비용 — **0줄**

`backend/chat/providers/manager.py` 는 그대로. 전환은 `.env` 의 세 줄만 수정하면 완료:

```diff
- EMBEDDING_PROVIDER=openrouter
- REASONING_PROVIDER=openrouter
- GENERATION_PROVIDER=openrouter
+ EMBEDDING_PROVIDER=gemini
+ REASONING_PROVIDER=gemini
+ GENERATION_PROVIDER=gemini
```

이 자체가 **provider 추상화의 검증 사례** — 후보를 자유롭게 시도하고, 결과에 따라 코드 변경 없이 롤백 가능했음.

## 6. OpenRouter는 영구히 제거되는가?

아니다. 코드와 `.env.example` 에 OpenRouter 분기는 그대로 유지한다.

이유:
1. **Chat completion 으로는 여전히 가치 있음** — embedding을 Gemini로 두고 chat만 OpenRouter로 가는 hybrid 도 한 줄 변경으로 가능
2. **다른 provider 추가의 reference** — Phase 2 의 사내 Ollama / vLLM 통합 시 OpenRouter 분기와 동일 패턴
3. **공급망 옵션 보유** — Gemini 장애 시 OpenRouter chat 으로 즉시 전환 가능

## 7. 자소서 워딩

> "초기에는 OpenRouter 를 통한 다중 모델 비교 전략을 시도했으나 embedding API 미지원을 발견하고 Gemini 단일 공급망으로 일원화했습니다. 이 의사결정 자체가 사전에 만들어 둔 **provider 추상화**의 가치를 검증하는 사례가 되었습니다 — 후보 provider 를 추가/제거/조합하는 데 코드 변경이 0줄이었고, 실험 결과에 따라 즉시 롤백할 수 있었습니다."

## 8. 향후 재시도 시점

OpenRouter 가 embedding API 를 공식 production 으로 풀거나, 사내에 Ollama/vLLM 임베딩 서버를 띄울 때 다시 분기 활성화. 그 시점에 같은 평가 절차 (모델 listing + 직접 API 호출 + recall@k 비교) 를 재실행한다.

## 관련 문서
- [provider_architecture.md](provider_architecture.md) — 추상화 구조
- [security.md](security.md) §4 — 로컬 LLM 전환 경로 (Ollama / vLLM)
- [chunk_experiment.md](chunk_experiment.md) — chunk A/B 평가
