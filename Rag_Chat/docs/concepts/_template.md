---
title: 개념 제목 (한 줄)
slug: kebab-case-slug
category: Retrieval        # Retrieval / Generation / Evaluation / Architecture / Tooling
level: 입문                # 입문 / 중급 / 심화
order: 100                 # 같은 카테고리 내 정렬용 (작을수록 앞)
summary: 한 줄 lede — 이 개념을 한 문장으로 요약 (목록 카드에서 보임).
prerequisites: []          # 먼저 읽어야 할 다른 concept slug 목록 (예: [bm25, embedding])
related: []                # 같이 보면 좋은 concept slug 목록
updated: 2026-05-21
---

## 1 · 무엇인가 (정의)

:::definition term="용어" name="개념 이름"
한두 문장으로 정확한 정의. 비유 없이.
:::

본 단락 — 정의 다음에 살을 붙이는 한두 문단.

## 2 · 비유로 이해하기

:::analogy title="비유 제목 (예: 김치찌개 레시피)"
일상 사물·상황으로 같은 구조를 묘사. 핵심은 "한 가지만 다르다" 같은 분리 가능한 변수 또는 상태.
:::

## 3 · 왜 중요한가

- 케이스 1 — 어떤 문제가 생기는가
- 케이스 2 — 어떤 이점이 있는가

:::callout warn title="흔한 함정"
실수하기 쉬운 지점.
:::

## 4 · 우리 시스템에서의 의미

이 개념이 Triple Chat 어디에 영향을 주는지. 가능하면 파일/모듈 경로 명시 (예: `backend/chat/pipeline/modules.py`).

## 5 · 어떻게 측정·검증하나

| 지표 | 의미 | 임계값 |
|---|---|---|
| recall@5 | 정답 청크가 top-5 안에 있는 비율 | 0.7 이상 |

```python
# 측정 코드 한 줄
from scipy.stats import mannwhitneyu
stat, p = mannwhitneyu(a, b, alternative='greater')
```

## 6 · FAQ

:::qa q="자주 헷갈리는 질문 1"
짧은 답. 한 단락 이내.
:::

:::qa q="자주 헷갈리는 질문 2"
짧은 답.
:::

## 7 · 더 읽기

- [공식 문서/논문 제목](https://example.com)
- [관련 블로그 글](https://example.com)
