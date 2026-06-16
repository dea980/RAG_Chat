---
title: IR Metrics (Recall@K · MRR · nDCG · p95 latency)
slug: ir-metrics
category: Evaluation
level: 입문
order: 65
summary: 검색 품질을 어떻게 숫자로 표현하는가. Recall@K, MRR, nDCG, p95 latency의 정의 · 해석 · guard threshold.
prerequisites: []
related: [embedding-eval, hybrid-search, reranker]
updated: 2026-06-16
---

## 1 · 무엇인가

:::definition term="용어" name="Recall@K, MRR, nDCG"
- **Recall@K** — 정답 chunk 가 top-K 안에 등장한 비율 (0~1). "정답을 가져왔는가?"
- **MRR (Mean Reciprocal Rank)** — 정답이 처음 나타난 순위의 역수 평균. "정답이 *얼마나 위에* 나왔는가?"
- **nDCG (normalized Discounted Cumulative Gain)** — 정답이 여러 개일 때, 더 관련 깊은 정답이 더 위에 있는가를 0~1 로 정규화
- **p95 latency** — 응답 시간 분포의 95퍼센타일. "최악의 5% 사용자가 얼마나 기다리나"
:::

## 2 · 비유로 이해하기

:::analogy title="구글 검색 결과 1 페이지"
"피자 맛집" 을 검색한다. 친구가 추천한 가게는 *진짜 정답*.

- **Recall@10** — 1 페이지 (10개 결과) 안에 친구 추천 가게가 있는가 (있다/없다)
- **MRR** — 그 가게가 몇 번째? 1등이면 1.0, 5등이면 0.2
- **nDCG** — 친구가 3 군데 추천했는데, 그중 *가장 좋은* 곳이 위에 있는가
- **p95 latency** — 100명 검색 중 95명이 느꼈을 최악의 로딩 시간

좋은 검색 = 정답이 (1) 있고 (recall) (2) 위에 있고 (MRR) (3) 가장 좋은 게 가장 위에 있고 (nDCG) (4) 빠르게 (latency).
:::

## 3 · 왜 중요한가

- **Recall@K 없이 MRR 보면 거짓 안전** — top-1 에 정답이 있는데 시스템이 top-10 의 9 번을 답으로 골라도 MRR 은 좋게 보임
- **MRR 없이 Recall 보면 사용자 체감 누락** — recall 1.0 이어도 정답이 항상 10등이면 사용자는 답을 못 본다 (lost-in-the-middle)
- **nDCG 는 graded relevance** — 정답이 binary 아니라 "관련 깊음 / 관련 있음 / 무관" 일 때 필요 (우리 dataset 은 아직 binary)
- **p95** — 평균 latency 는 거짓말. 최악 5% 가 운영 결정의 기준

:::callout warn title="흔한 함정"
K 를 명시 안 하면 비교 불가. "recall 0.85" 가 K=5 인지 K=20 인지에 따라 의미 정반대. **항상 `recall@K` 로 표기.**
:::

## 4 · 우리 시스템에서의 의미

- 코드: `chat/tests/evals/run_chunk_ab.py`, `chat/embedding_eval.py`
- Dataset: 영업팀 12 문항 (binary relevance), `expected_chunk_ids` 라벨
- 측정 지점:

```
Question
    │
    ▼
Dense retrieve → Recall@N=30      ← 1차 천장
    │
    ▼
Rerank → Recall@K=5, MRR@5         ← LLM 컨텍스트 입력
    │
    ▼
LLM call → end-to-end p95          ← 사용자 체감
```

Guard threshold (현재 baseline):

| Metric | Baseline | Guard (회귀 차단) |
|---|---|---|
| `recall@5` (rerank 후) | 0.917 | ≥ 0.85 |
| `MRR@5` | 0.81 | ≥ 0.75 |
| `p95 latency` (retrieve + rerank) | 138 ms | < 200 ms |
| `recall@30` (1차 천장) | 0.95 | ≥ 0.92 |

PR 이 guard 깨면 CI fail (chunk A/B artifact 검사).

## 5 · 어떻게 측정·검증하나

```python
# Recall@K
def recall_at_k(retrieved_ids, expected_ids, k):
    return len(set(retrieved_ids[:k]) & set(expected_ids)) / len(expected_ids)

# MRR (정답 하나일 때)
def mrr(retrieved_ids, expected_id):
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id == expected_id:
            return 1.0 / rank
    return 0.0

# nDCG@K (정답 여러 개 + relevance 점수)
import numpy as np
def ndcg_at_k(retrieved_ids, relevance_map, k):
    gains = [relevance_map.get(d, 0) for d in retrieved_ids[:k]]
    dcg  = sum(g / np.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(relevance_map.values(), reverse=True)[:k]
    idcg = sum(g / np.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0
```

latency 측정:

```python
import time
from statistics import quantiles
times = []
for q in dataset:
    t0 = time.perf_counter()
    pipeline.run(q.question)
    times.append((time.perf_counter() - t0) * 1000)
p50, p95, p99 = quantiles(times, n=100)[49], quantiles(times, n=100)[94], quantiles(times, n=100)[98]
```

## 6 · FAQ

:::qa q="Q. K 를 몇으로 잡아야?"
A. LLM 에 넘기는 chunk 수와 일치시켜라. 우리 시스템은 top-5 를 LLM 에 넘김 → `recall@5` · `MRR@5` 가 의사결정 metric. `recall@N=30` 은 1차 천장 모니터링용.
:::

:::qa q="Q. nDCG 와 MRR 중 뭐가 더 좋나?"
A. 정답이 1개 (또는 동등 가치 N개) 면 MRR 로 충분. 정답에 "더 관련 깊음 / 부분 관련" 차이가 있으면 nDCG. 우리는 currently binary → MRR + Recall.
:::

:::qa q="Q. 왜 평균 latency 가 아니라 p95 인가?"
A. 평균은 outlier 에 둔감. 100 req 중 5 req 가 5 초 걸려도 평균은 작게 나옴. 사용자는 그 5 req 의 사람들 — 그들이 다시 안 온다. p95 가 운영 결정.
:::

:::qa q="Q. recall 100% 면 끝?"
A. 아님. recall 100% 인데 정답이 항상 K 번째 (꼴찌) 라면 lost-in-the-middle 로 LLM 이 못 본다. MRR 같이 봐야 함.
:::

## 7 · 더 읽기

- [TREC Eval](https://trec.nist.gov/trec_eval/) — 표준 IR metric 구현
- [BEIR paper](https://arxiv.org/abs/2104.08663) — IR metric 사용 사례
- [Lost in the Middle (Liu et al., 2024)](https://arxiv.org/abs/2307.03172) — 컨텍스트 중간 정보 누락 현상
- [`backend/docs/learning/2026-05-29-ir-rag-concepts.md`](../../backend/docs/learning/2026-05-29-ir-rag-concepts.md) — 우리 학습 narrative
