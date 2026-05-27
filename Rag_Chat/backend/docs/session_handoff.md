# Session Handoff — 2026-05-27

> 다음 세션(또는 다른 agent)이 이어받기 위한 상태 스냅샷.
> Provider 스위칭 정리 + `.env` 통합 작업 기준.

---

## 1. 한 줄 요약

Chat LLM 과 임베딩을 분리하고 5개 provider(gemini/qwen/openrouter/ollama/huggingface)를
선택 가능하게 만든 뒤, 환경 설정을 **단일 `.env`** 로 통합했다. 현재 운영 provider 는
`openrouter`, Ollama 는 로컬 모델 확인 완료 상태로 즉시 전환 가능.

---

## 2. 이번 세션에 한 것

- **`.env` 통합** — `.env.example` 에만 있던 키(`RERANKER_*`, `OLLAMA_*`, `HUGGINGFACE_*`)를
  겹치지 않게 `.env` 로 병합. `.env.example` 삭제, `.gitignore` 에 `.env.example` 추가.
  → 커밋 `ae308c9` (`feature/onnx-reranker` 브랜치)
- **Ollama 로컬 모델 확인** — `qwen3.6`(23GB), `gemma4`(9.6GB) 설치됨. `llama3.1` 은 미설치.
  `.env` 에 `OLLAMA_MODEL=qwen3.6` 설정.
- **상태 HTML 생성** — `Rag_Chat/project_status.html` (provider/ingest/env 스냅샷).

> 참고: provider 스위칭 코드(`ProviderManager`, 프론트 preset)는 다른 agent 작업분으로
> 이미 working tree 에 있었음. 이번 세션은 그 위에 env 정리 + 문서화를 얹은 것.

---

## 3. 현재 `.env` provider 상태

| 키 | 값 | 비고 |
|---|---|---|
| `EMBEDDING_PROVIDER` | `gemini` | `GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001` |
| `REASONING_PROVIDER` | `openrouter` | `openai/gpt-oss-20b:free` |
| `GENERATION_PROVIDER` | `openrouter` | `openai/gpt-oss-20b:free` |
| `OLLAMA_MODEL` | `qwen3.6` | 로컬 설치됨, provider 만 바꾸면 사용 가능 |
| `RERANKER_ENABLED` | `0` | optional, 무거운 의존성 → 기본 비활성 |

`.env` 는 gitignored → repo 에 없음. 로컬 파일이 source of truth.

---

## 4. 다음 세션 적용 방법

**Ollama 로 전환하려면** (`.env` 만 수정, 코드 변경 불필요):
```env
REASONING_PROVIDER=ollama
GENERATION_PROVIDER=ollama
# OLLAMA_MODEL=qwen3.6  (이미 설정됨)
```
그 뒤 `ollama serve` 만 실행하면 됨 (모델은 이미 로컬에 있음).

**프론트엔드** — Streamlit 사이드바 *Provider Preset* 에서 `Ollama Only` 선택 시 세션 단위 전환.

---

## 5. 주의사항 (gotchas)

- **임베딩 변경 = 재인덱싱 필수.** `EMBEDDING_PROVIDER`/모델을 바꾸면 기존 Chroma 벡터 DB 를
  다시 만들어야 검색 품질이 유효함 (`get_embedding_config()` 가 `requires_reindex: true` 노출).
- **`EMBEDDING_MODEL` 키는 일부러 `.env` 에 안 넣음.** 넣으면 표시값이
  실제 사용값(`GOOGLE_EMBEDDING_MODEL`)과 어긋남. provider별 모델 키만 사용.
- **Hugging Face 는 단순 모델명 불가.** OpenAI 호환 엔드포인트(Inference Endpoint/TGI)가
  `HUGGINGFACE_BASE_URL` 에 있어야 함. 미설정 시 `RuntimeError`.
- **`llama3.1` 미설치.** `.env`/문서의 과거 예시가 llama3.1 이었으나 로컬엔 없음 → qwen3.6 사용.

---

## 6. 안 한 것 / 보류

- **Hugging Face 엔드포인트** — 담당자가 추후 직접 준비 (`HUGGINGFACE_*` 는 빈 placeholder).
- **push** — `ae308c9` 는 로컬 커밋만. 푸시 미실행.
- **다른 working tree 변경** — ingest Phase 3 / Upload API 통합 등 미커밋 변경은 손대지 않음
  (다른 agent 작업분). 통합 이슈는 [_index.md](_index.md) Phase 표 참고.

---

## 관련 문서
- [project_status.html](../../project_status.html) — 시각화된 상태 스냅샷
- [_index.md](_index.md) — 전체 문서/Phase 인덱스
- [../../프로젝트현황.md](../../프로젝트현황.md) — 한국어 진행 현황
