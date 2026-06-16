---
title: Embedding Eval Harness (임베딩 평가 하네스)
slug: embedding-eval
category: Evaluation
level: 중급
order: 60
summary: 임베딩 모델·청크 사이즈를 직관 아니라 labeled dataset + metric으로 결정하기 위한 검증 자동화 구조.
prerequisites: []
related: [ir-metrics, hybrid-search, reranker]
updated: 2026-06-16
---

## 1 · 무엇인가

:::definition term="용어" name="Eval harness"
"질문 → 정답 chunk id" 라벨이 붙은 dataset 과, 후보 모델/설정을 그 dataset 으로 돌려 metric (Recall@K, MRR, nDCG) 을 자동 계산하는 스크립트의 결합. 모델 선택·하이퍼파라미터 결정 시 anecdotal 비교를 metric 비교로 대체.
:::

본 단락 — "이 모델이 한국어가 더 좋아 보인다" 는 5쌍 샘플을 눈으로 본 결과다. 실제 운영에서 같은 결정을 30 번 내려야 한다 (모델 교체 · 청크 크기 변경 · 임계값 조정). 매번 눈으로 보면 **재현 불가 · 비교 불가 · 회귀 감지 불가**.

## 2 · 비유로 이해하기

:::analogy title="시각 검사 vs 자판기 부품"
신호등 LED 새 부품을 받았다.
- **눈으로 검사** — "밝아 보이네" — 작업자마다 다름, 어제와 비교 불가
- **광도계** — 같은 거리, 같은 각도에서 lumen 측정. 부품 A=320, B=295. 숫자가 같은 조건에서 나옴

Eval harness 가 광도계. dataset 이 *같은 거리·같은 각도*. 새 모델 / 청크 사이즈를 똑같이 돌려 숫자로 비교한다. 어제 도입한 변경이 오늘 회귀했는지도 같은 숫자로 본다.
:::

## 3 · 왜 중요한가

- **결정의 재현 가능성** — "왜 모델을 X 로 바꿨지?" → eval 로그 + dataset version
- **회귀 감지** — 모델 업그레이드가 한국어 성능을 깎는지, splitter 변경이 단답형 질문 recall 을 깎는지
- **CI 통합** — chunk A/B harness 가 PR artifact 로 붙음 → 코드 리뷰가 정량 비교

:::callout warn title="흔한 함정"
"5쌍 정답 dataset 이면 충분" — n=5 는 p-value 가 계산 안 된다. 카테고리 별 (영업 / 지원 / 정책 / 스펙) 최소 10 문항씩 ≥ 40 권장. 우리 12 문항도 anecdotal 에 가까움 — 확장 대기 중.
:::

## 4 · 우리 시스템에서의 의미

- 코드: [`backend/chat/embedding_eval.py`](../../backend/chat/embedding_eval.py), [`chat/tests/evals/`](../../backend/chat/tests/evals/)
- Dataset: `backend/data/external/eval/` 의 labeled YAML
- 페이지: Streamlit `pages/embedding_lab.py` — Mode A (모델 비교)
- CLI:
  ```bash
  python -m chat.tests.evals.run_chunk_ab \
      --sizes 80,150,250,500,1000 --overlaps 0,30,80,150 --k 5
  ```
- CI: GitHub Actions `chunk A/B report` artifact

dataset 구조 (YAML):

```yaml
- id: sales-001
  question: "갤럭시 S25 Ultra 256GB 가격이 얼마인가요?"
  expected_chunk_ids: ["product/galaxy_s25_ultra#row42"]
  category: sales
  difficulty: easy

- id: hr-007
  question: "연차 이월 가능한가요?"
  expected_chunk_ids:
    - "hr/annual_leave#section-3-2"
    - "hr/annual_leave#section-3-3"
  category: hr
  difficulty: medium
```

`expected_chunk_ids` 가 복수면 Recall@K 는 *교집합 비율*, MRR 은 *첫 등장 순위*.

## 5 · 어떻게 측정·검증하나

| 비교 시나리오 | 측정 |
|---|---|
| 모델 교체 (`text-embedding-004` → `bge-m3`) | dataset 전체 Recall@5, MRR — 카테고리별 분해 |
| chunk_size 변경 (1000 → 150) | 같은 모델로 두 인덱스 빌드, 같은 dataset |
| Reranker on/off | 1차 후보 30 고정, top-5 비교 |
| Hybrid (BM25 추가) | dense-only vs dense+BM25 (RRF) |

```python
# 결과 표 예
| config            | recall@5 | MRR  | p95 latency |
|-------------------|----------|------|-------------|
| baseline          | 0.789    | 0.62 |  92 ms      |
| chunk=150         | 0.833    | 0.71 |  88 ms      |
| chunk=150 + rerank| 0.917    | 0.81 | 138 ms      |
```

판단 기준 — recall@5 ≥ baseline + 0.02 **and** MRR 동등 **and** p95 latency < +50ms.

## 6 · FAQ

:::qa q="Q. labeled dataset 만들기 너무 비싸다"
A. 초기 30 문항은 PM/도메인 전문가 1 인 · 2 시간이면 충분. 그 후는 실제 사용자 질문 로그에서 *답변이 좋았던 케이스* 를 사후 라벨링 (정답 chunk = 실제 인용된 chunk). 점진 확장.
:::

:::qa q="Q. n=12 로는 통계적으로 유의미한 결론 안 나오지 않나?"
A. 맞다. n=12 에서는 **effect size + direction consistency** 로 본다 — recall delta 0.04 정도면 의미 있고, 모든 카테고리에서 동일 방향이면 노이즈 아닐 가능성 ↑. p-value 는 n=40 부터.
:::

:::qa q="Q. anecdotal SEMANTIC_PAIRS 같은 5쌍 비교는 언제 쓰나?"
A. 디버깅 · 데모. 의사결정에는 쓰지 않는다. 우리 prior commit 의 5쌍은 모델 동작 확인용으로만 남기고 결정 근거에서 제거됨.
:::

:::qa q="Q. metric 이 좋은데 실제 답변이 안 좋으면?"
A. dataset 이 실제 사용 분포를 못 잡고 있다. 사용자 로그에서 새 패턴 (예: 다중 제품 비교 질문) 추가 라벨링. eval harness 의 가치는 *dataset 의 진화 도구* 라는 데 있다.
:::

## 7 · 더 읽기

- [`backend/docs/learning/2026-05-29-embedding-eval-harness.md`](../../backend/docs/learning/2026-05-29-embedding-eval-harness.md) — 우리 구현 narrative
- [`backend/docs/learning/2026-05-29-faiss-eval-harness.md`](../../backend/docs/learning/2026-05-29-faiss-eval-harness.md) — FAISS backend 측 harness
- [BEIR — Heterogeneous IR benchmark](https://github.com/beir-cellar/beir) — 표준 eval dataset
- [MTEB — Massive Text Embedding Benchmark](https://huggingface.co/spaces/mteb/leaderboard) — 임베딩 모델 비교 표준
