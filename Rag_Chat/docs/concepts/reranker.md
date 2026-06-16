---
title: Reranker (재정렬)
slug: reranker
category: Retrieval
level: 중급
order: 40
summary: 임베딩 검색의 top-N 후보를 cross-encoder로 다시 채점해 정확도를 끌어올리는 2 단계 검색의 후단.
prerequisites: [hybrid-search]
related: [hybrid-search, ir-metrics]
updated: 2026-06-16
---

## 1 · 무엇인가

:::definition term="용어" name="Reranker"
임베딩(또는 BM25) 1차 검색이 뽑은 후보 N개를 입력으로 받아, 질의-문서 쌍을 **함께** 모델에 넣고 관련도 점수를 다시 매기는 모델. 결과의 top-K 만 LLM 컨텍스트로 넘김.
:::

본 단락 — 1차 검색은 질의 임베딩과 문서 임베딩을 **따로** 계산해 거리만 비교한다 (bi-encoder). Reranker 는 질의와 문서를 **한 번에** 모델에 넣고 토큰 단위로 상호작용하게 만든다 (cross-encoder). 그래서 더 정확하지만 느리다.

## 2 · 비유로 이해하기

:::analogy title="이력서 1차 / 2차 심사"
- **1차 심사 (임베딩)** — HR 이 검색어("백엔드 5년") 로 DB 에서 100명 끌어옴. 빠르지만 거칠다. "백엔드 솔루션 영업 5년" 도 같이 걸린다.
- **2차 심사 (reranker)** — 면접관이 100명 이력서를 **검색어와 나란히 놓고** 한 명씩 다시 본다. 느리지만 진짜 매칭만 위로 올린다.

먼저 100명으로 좁히지 않으면 면접관은 못 본다. 100명을 그대로 LLM 에 넘기면 컨텍스트가 터진다. → 두 단계가 둘 다 필요.
:::

## 3 · 왜 중요한가

- **임베딩만 쓰면 한국어 동의어·고유명사에서 noise top-1** — "갤럭시 S25 Ultra" 와 "갤럭시 S24 Ultra" 임베딩이 너무 가까움
- **LLM 컨텍스트 비용** — top-30 을 다 넘기면 토큰 폭증 + 답변 품질 하락 (lost-in-the-middle). top-3~5 로 압축 필요
- **답변 품질 = retrieval 품질** — reranker 가 top-3 정확도를 끌어올리면 LLM 변경 없이도 답변이 좋아진다

:::callout warn title="흔한 함정"
Reranker 없이 임베딩 단독으로 top-3 만 뽑으면 정답을 놓친다. 1차에서는 **N 을 넉넉히** (보통 20~50), reranker 가 K (3~5) 로 좁히는 구조여야 한다.
:::

## 4 · 우리 시스템에서의 의미

- 코드: [`backend/chat/rerankers/onnx_bge.py`](../../backend/chat/rerankers/onnx_bge.py)
- 모델: `BAAI/bge-reranker-v2-m3` — 다국어 · 568 MB · 첫 실행 시 `~/.cache/huggingface/` 다운로드
- 형식: **ONNX** Runtime — Python 의존성만으로 CPU 추론. PyTorch 풀스택 불필요
- 통합: `chat/pipeline/modules.py` 의 dense retrieve 이후 hook
- 끄기: `RERANKER_ENABLED=0` env (CI 와 저사양 dev 머신에서)

왜 이 선택:

| 옵션 | 비용 | latency | 오프라인 | 한국어 |
|---|---|---|---|---|
| Cohere Rerank API | $1 / 1k req | ~100ms | ❌ | ⚪ |
| **ONNX `bge-reranker-v2-m3`** | $0 | +50ms | ✅ | ✅ |
| sentence-transformers PyTorch | $0 | +80ms | ✅ | ✅ |
| 없음 (임베딩 단독) | $0 | 0 | ✅ | recall ↓ |

ONNX 선택 이유 — (1) 사내 LLM 전환 가능성 → 오프라인 가능해야 (2) PyTorch 미설치 image 에서도 동작 (3) Cohere 비용·latency·외부 송신 회피.

## 5 · 어떻게 측정·검증하나

| 지표 | 의미 | 가드 |
|---|---|---|
| `recall@3` (rerank 후) | reranker 가 top-3 안에 정답을 올렸는가 | 임베딩 단독 baseline 대비 ≥ |
| `MRR` | 정답이 처음 나타난 순위 역수 평균 | 동등 또는 상승 |
| `p95 latency` | rerank 단계 단독 | < 100 ms (top-N=30 기준) |
| `recall@30 - recall@3` | reranker 가 가져갈 수 있는 상한 | "1차에서 못 가져온 정답" 모니터 |

```python
# 측정 — 1차 N, 최종 K 둘 다 변수
from chat.tests.evals import run_chunk_ab
run_chunk_ab.compare(
    baseline={"rerank": False, "k": 5},
    candidate={"rerank": True, "n": 30, "k": 5},
)
```

:::callout ok title="recall@30 가 천장이다"
Reranker 는 *재정렬*만 한다. 1차에서 정답 chunk 가 안 들어오면 reranker 도 못 살림. recall@N (1차 후보 수) 도 같이 봐야 한다.
:::

## 6 · FAQ

:::qa q="Q. Reranker 가 있으면 hybrid search (BM25+벡터) 필요 없지 않나요?"
A. 다르다. Hybrid 는 **후보군 자체**를 풍부하게 만든다 (BM25 가 고유명사 / 임베딩이 동의어). Reranker 는 그 후보를 **재정렬**한다. 두 단계는 직렬로 같이 쓸 때 효과가 가장 크다 (hybrid → rerank → LLM).
:::

:::qa q="Q. N (1차 후보 수) 은 얼마가 적정인가?"
A. 코퍼스 크기와 reranker 비용 함수. 우리 12 문항 eval 기준 N=30 이 sweet spot. N=10 은 천장이 낮아 recall 손해, N=100 은 latency 비례 증가하는데 recall 거의 동일.
:::

:::qa q="Q. ONNX 와 sentence-transformers 의 점수가 다른가?"
A. 거의 같음 (양자화 안 한 경우 ε 수준). ONNX 는 그래프 최적화 + 의존성 경량화 이점. 모델 동작은 동일.
:::

:::qa q="Q. Reranker 끄면 어떻게 되나?"
A. `RERANKER_ENABLED=0` 으로 끄면 1차 dense top-K 가 그대로 LLM 으로. CI · 저사양 dev 에서 사용. 운영에서는 켜져 있음.
:::

## 7 · 더 읽기

- [BGE Reranker v2 m3 (BAAI)](https://huggingface.co/BAAI/bge-reranker-v2-m3) — 모델 카드
- [Pinecone — Rerankers explained](https://www.pinecone.io/learn/series/rag/rerankers/) — bi-encoder vs cross-encoder 그림
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — chunk + BM25 + reranker 결합 정량 분석
