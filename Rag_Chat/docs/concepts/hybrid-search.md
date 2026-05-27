---
title: Hybrid Search (하이브리드 검색)
slug: hybrid-search
category: Retrieval
level: 입문
order: 30
summary: 의미 기반(임베딩) 검색과 키워드 기반(BM25) 검색을 합쳐, 둘의 약점을 서로 보완하는 RAG 검색 전략.
prerequisites: []
related: [reranker]
updated: 2026-05-21
---

## 1 · 무엇인가

:::definition term="용어" name="Hybrid Search"
**의미 기반 벡터 검색**(dense)과 **키워드 기반 검색**(sparse, 대표적으로 BM25) 두 가지를 동시에 돌려, 각자의 결과를 가중치로 합쳐(top-k에 같이 올려) 더 좋은 retrieval 결과를 얻는 방법.
:::

벡터 검색만 쓰면 "갤럭시 S25"라는 정확한 모델명 같은 **고유 토큰**을 놓치는 경우가 생기고, BM25만 쓰면 "비싼 폰" → "고가 스마트폰" 같은 **의미가 같지만 단어가 다른** 문장을 못 잡습니다. Hybrid는 두 채널의 결과를 합쳐 이 둘 다 잡으려는 시도입니다.

## 2 · 비유로 이해하기

:::analogy title="도서관 두 사서"
- **사서 A (벡터 검색)** — "이 책 같은 *주제* 다른 책 추천" 잘 해줍니다. 단, 책 *제목*을 정확히 물어보면 헤맵니다.
- **사서 B (BM25)** — 제목·저자·ISBN을 *정확히* 알고 있을 때 빠릅니다. 의미가 비슷한 책 추천은 못 합니다.

같은 질문을 두 사서한테 같이 물어보고, 둘이 다 추천한 책은 더 위로 올리면 — 둘 중 한 명만 썼을 때보다 빠뜨리는 책이 줄어듭니다.
:::

## 3 · 왜 중요한가

- **고유명사·숫자 누락 방지** — 임베딩은 "갤럭시 S25 Ultra"와 "갤럭시 S24 Ultra"를 거의 같은 벡터로 보기 쉬움. BM25는 토큰이 다르므로 명확히 구분.
- **의미 일반화 유지** — "가격" vs "비용" 같은 동의어는 BM25에선 별개 토큰이지만 벡터에선 가깝게 잡힘.
- **도메인 적응 비용 절감** — 임베딩 모델을 fine-tune하지 않아도 BM25가 도메인 특화 키워드를 보강해 줌.

:::callout warn title="흔한 함정"
점수 스케일이 완전히 다릅니다. 벡터 cosine은 [0, 1], BM25는 [0, ∞). **그대로 더하면 BM25가 항상 이깁니다.** 정규화(min-max 또는 RRF) 필수.
:::

## 4 · 우리 시스템에서의 의미

현재 Triple Chat은 `backend/chat/pipeline/modules.py` 에서 **벡터 검색만** 사용. 도입할 경우:

- `pgvector` (또는 현재 vector store) 결과 → `scores_dense`
- Postgres `ts_rank_cd` (또는 `rank_bm25` 라이브러리) → `scores_sparse`
- **Reciprocal Rank Fusion (RRF)** 로 결합 후 reranker(현재 작업 중)에 넘김

```python
def rrf(dense: list[Doc], sparse: list[Doc], k: int = 60) -> list[Doc]:
    scores: dict[str, float] = {}
    for rank, doc in enumerate(dense):
        scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank)
    for rank, doc in enumerate(sparse):
        scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank)
    return sorted(all_docs, key=lambda d: -scores[d.id])
```

`k=60`은 RRF 원 논문(Cormack et al., 2009)의 default. 작은 코퍼스에서도 안정적.

## 5 · 어떻게 측정·검증하나

| 지표 | 의미 | 가드 |
|---|---|---|
| `recall@5` | 정답 청크가 top-5 안에 들어온 비율 | ≥ 현재 vector-only baseline |
| `MRR` | 정답이 처음 나타난 순위의 역수 평균 | 동등하거나 향상 |
| `p95 latency` | 두 검색 + 결합 overhead | +50ms 이하 |

A/B test 절차는 `ab_testing_guide.html` 11절(7단계) 그대로. 한 번에 하나만 — **검색 결합만** 바꾸고 reranker / chunk_size / 임베딩은 고정.

:::callout ok title="우리 평가셋 규모 주의"
`n=12`로는 0.05 미만 p-value를 얻기 어렵습니다. Hybrid를 채택할 때도 **효과 크기**(recall delta)와 **방향 일관성**(여러 카테고리 질문에서 모두 개선)을 같이 봐야 합니다.
:::

## 6 · FAQ

:::qa q="Q. 벡터 검색이 잘 되고 있으면 굳이 BM25를 더할 필요가 있나요?"
A. 잘 되는 카테고리에선 차이가 작거나 오히려 노이즈가 늡니다. 단, "정확한 모델명·코드", "숫자(가격, 용량)" 같은 정형 토큰이 자주 나오는 도메인(우리 같은 제품 카탈로그)에선 거의 항상 도움.
:::

:::qa q="Q. RRF 말고 다른 결합 방법은?"
A. (1) **Weighted sum** — 점수 정규화 후 `α·dense + (1-α)·sparse`. α tuning 필요. (2) **Cascade** — BM25로 100개 뽑고 벡터로 재정렬. RRF가 가장 무난한 시작점.
:::

:::qa q="Q. Reranker가 있으면 Hybrid 필요 없지 않나요?"
A. Reranker는 *재정렬*만 합니다. 처음 가져온 후보 안에 정답이 **없으면** reranker도 못 살립니다. Hybrid는 *후보군 자체*를 풍부하게 만들어 reranker가 일할 거리를 줍니다.
:::

## 7 · 더 읽기

- [Reciprocal Rank Fusion (Cormack et al., 2009)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) — RRF 원 논문
- [Pinecone Hybrid Search](https://docs.pinecone.io/guides/data/understanding-hybrid-search) — 실무 가이드
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — chunk + BM25 + reranker 결합의 정량 분석
