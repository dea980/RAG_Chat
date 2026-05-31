# Embedding Eval Harness — KorSTS·KorNLI 로 모델을 데이터로 고른다

## 한 줄 요약

라벨된 한국어 벤치마크 (KorSTS·KorNLI) + 자체 도메인 쌍을 가지고 **여러
embedding 모델을 동시에 평가**하고, **Pearson/Spearman/separation/scatter/
worst-pair 까지** 한 화면에 표시하는 lab Mode B를 추가했다.

## 비유 — 와인 시음 단계 2: 블라인드 테스트

처음 시음대 (Mode A) 는 와인을 한 잔씩 따라 맛본다 — "이 와인 어떨까".
블라인드 테스트 (Mode B) 는 **이미 점수가 매겨진 100 병** 을 시음자에게
주고, 시음자가 매긴 점수가 "원래 점수와 얼마나 일치하는가" 를 본다.

| 단계 | Mode A | Mode B |
|---|---|---|
| 입력 | 두 텍스트 (사용자 즉흥) | 라벨된 데이터셋 1500쌍 |
| 점수 | 모델 cosine | 모델 cosine × 사람 라벨 → 상관계수 |
| 결정 | 직관 | 통계 |
| 비용 | 즉시 | 1~3분 |
| 활용 | 호기심 / 첫 검증 | production 모델 선택 결정 |

## 왜 이게 필요한가

| | Mode A 만 있을 때 | Mode B 추가 후 |
|---|---|---|
| 모델 비교 근거 | 5쌍 직감 | 1500쌍 통계 |
| "한국어 약하다" 주장 | 일화 | Pearson 0.62 vs 0.85 같은 수치 |
| 모델 교체 결정 | "느낌상 좋아 보임" | "separation +0.12, Pearson +0.10" |
| 약점 발견 | 우연 | worst-pair drill-down 으로 systematic |
| 재현성 | 매번 새 입력 | 고정 dataset, 누구나 같은 점수 |

사용자가 직접 한 말 — *"5쌍 정도로는 정말 됐다 안 됐다 판단 못 한다"*. 그 한
계를 푸는 게 Mode B 의 핵심.

## 핵심 코드

### 1. 데이터셋 등록 dict — 운영자가 한 줄로 확장

```python
# backend/chat/embedding_eval.py
DATASETS = {
    "korsts-dev":  lambda lim: load_korsts(DATA_DIR / "KorSTS/sts-dev.tsv", lim),
    "kornli-dev":  lambda lim: load_kornli(DATA_DIR / "KorNLI/xnli.dev.ko.tsv", lim),
    "curated":     lambda lim: load_curated(DATA_DIR / "embedding_eval/curated_pairs.yaml", lim),
}
```

- 각 entry = (id) → callable(limit) → `list[EvalPair]`
- 새 데이터셋 = loader 함수 한 개 + dict 한 줄. 평가 흐름 무변화.

### 2. EvalPair — 모든 데이터셋의 공통 형식

```python
@dataclass
class EvalPair:
    text1: str
    text2: str
    label: float | str          # KorSTS=float(0~5), KorNLI/curated=str bucket
    bucket: str                 # 정규화된 카테고리 (positive/negative/hard_negative/neutral)
```

- KorSTS score 4.0+ → bucket=positive, score 1.0− → bucket=negative
- KorNLI entailment → positive, contradiction → hard_negative
- 다 다른 라벨 체계지만 **하나의 bucket 축** 으로 비교 가능

### 3. 메트릭 — 데이터셋 종류 따라 자동 분기

```python
# embedding_eval._compute_metrics 핵심 부분
if len(numeric_labels) == len(pairs):
    metrics["pearson"]  = pearson(numeric_labels, scores)   # KorSTS만
    metrics["spearman"] = spearman(numeric_labels, scores)
if "positive" in bucket_means and "negative" in bucket_means:
    metrics["separation"]      = bucket_means["positive"] - bucket_means["negative"]
if "positive" in bucket_means and "hard_negative" in bucket_means:
    metrics["separation_hard"] = bucket_means["positive"] - bucket_means["hard_negative"]
```

- 라벨이 숫자면 상관계수, 문자면 bucket 평균.
- 하나의 harness 가 세 데이터셋 모두 처리.

## 데이터 흐름

```
[Streamlit] frontend/pages/embedding_lab.py · tab "Benchmark Eval"
  사용자: dataset=korsts-dev, models=[bge-m3, gemini], limit=300
  │ POST /api/v1/triple/embeddings/eval/
  ▼
[Django] chat/embedding_views.py · EmbeddingEvalAPIView
  │ validate → call evaluate(...)
  ▼
[harness] chat/embedding_eval.py · evaluate(dataset, models, limit)
  │
  ├─ pairs = DATASETS[dataset](limit)
  │   ├─ KorSTS  → tsv read, score→bucket
  │   ├─ KorNLI  → tsv read, label→bucket
  │   └─ curated → yaml read, bucket 그대로
  │
  ├─ for key in models:
  │     spec = EMBEDDING_REGISTRY[key]   # ← Mode A 와 공유
  │     if kind == "cross":
  │         scores = _score_cross_pairs(...)   # sigmoid 정규화
  │     elif st-model:
  │         scores = _score_st_pairs(...)      # batch encode + cosine
  │     elif gemini:
  │         scores = _score_gemini_pairs(...)  # sequential API
  │
  ├─ _compute_metrics(pairs, scores, spec):
  │     bucket_means, separation
  │     pearson/spearman if numeric
  │     top_errors (worst 10 분기점 분석용)
  │     scatter (≤ 500 샘플)
  │
  ▼
Response { dataset, pair_count, results: { model_id → metrics } }
  │
  ▼
[frontend] 표 + scatter_chart + bar_chart + worst-pair expander + raw JSON
```

## 확인 방법

### Unit tests
```bash
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings \
  python3 -m pytest chat/tests/test_embedding_eval.py -v
# expected: 15 passed (loaders + 수학)
```

### URL routing
```bash
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -c "
import django; django.setup()
from chat.urls import urlpatterns
for u in urlpatterns:
    if 'eval' in (u.name or ''):
        print(u.pattern, '->', u.name)
"
# expected: embeddings/eval/ -> embedding-eval
```

### CLI (작은 limit 로 빠르게)
```bash
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings \
  python3 manage.py embedding_eval --dataset curated --models bge-m3 --limit 20
# 첫 호출 ~2GB 다운로드. 이후 캐시.
```

### Streamlit UI
1. backend 기동 (`python manage.py runserver`)
2. streamlit → `Embedding Lab` 페이지 → 탭 "📊 Benchmark Eval"
3. dataset=korsts-dev, models=[bge-m3, gemini], 평가 쌍=100 (빠른 시작)
4. "평가 실행" → 표 + scatter + worst-pair 확인

## 데이터셋 출처

- **KorSTS / KorNLI**: <https://github.com/kakaobrain/kor-nlu-datasets> (CC BY-SA 4.0)
- **curated_pairs.yaml**: 자체 작성 (사규/HR/재무/IT 도메인 60쌍)
- 폴더 구조 + license 상세: `backend/data/README.md`

## 연습 문제

1. **bucket 정의 바꾸기**: 현재 KorSTS는 score≥4.0 = positive, ≤1.0 = negative.
   threshold 를 score≥4.5 / ≤0.5 로 좁히면 separation 지표가 어떻게 변할까?
   왜 일반적으로 별로 좋은 변경이 아닐까? (힌트: positive/negative 쌍 수 급감)
2. **새 데이터셋 추가**: KLUE-STS v1.1 (Hugging Face `klue/sts`) 을 다운로드한 뒤
   `load_klue_sts()` loader 와 `DATASETS["klue-sts-dev"]` 한 줄을 추가하라.
   메트릭 산출 코드를 손대지 않아도 동작할까? (힌트: bucket 매핑이 핵심)
3. **상관계수 대신 MSE**: Pearson/Spearman 대신 `mean((label/5 - score)**2)` 를
   추가하면 어떤 케이스에서 의미 있는가? 모델 점수가 sigmoid 적용된 cross-encoder
   일 때 비교 가능한가? (힌트: scale)
4. **worst-pair drill-down 활용**: bge-m3 의 worst 10 쌍에서 공통 패턴 (예: "전부
   부정 표현" / "전부 한·영 혼합") 이 보이면, 그게 모델의 어느 학습 약점을 시사하
   는가? 어떤 데이터셋을 추가해서 보강해야 할까?
5. **cross-encoder 와 embedding 비교의 함정**: reranker-bge 의 separation 이 0.40
   이고 bge-m3 의 separation 이 0.41 일 때, "reranker 가 더 못한다" 라고 단정할
   수 있는가? sigmoid 정규화의 어떤 한계가 이 비교를 부분적으로만 유효하게 만드는가?

## 변경 파일

| 파일 | 역할 |
|---|---|
| `backend/chat/embedding_eval.py` (new) | loader + 메트릭 + evaluate 진입점 |
| `backend/chat/embedding_views.py` | `EmbeddingEvalAPIView` 추가 |
| `backend/chat/urls.py` | `embeddings/eval/` 라우트 추가 |
| `backend/chat/management/commands/embedding_eval.py` (new) | CLI command |
| `backend/chat/tests/test_embedding_eval.py` (new) | 15 unit tests (loader + 수학) |
| `frontend/pages/embedding_lab.py` | `st.tabs` 로 Mode A/B 분리, Mode B UI |
| `backend/data/{KorSTS,KorNLI,embedding_eval,README.md}` | 데이터셋 + 가이드 (이전 commit) |

## 관련 문서

- [`2026-05-28-comparison-labs-extend.md`](2026-05-28-comparison-labs-extend.md) — Mode A 도입 노트
- [`../../data/README.md`](../../data/README.md) — 데이터셋 출처·license·포맷
- [`../features/embedding_lab/page.md`](../features/embedding_lab/page.md) — 통합 노트
- [`../features/embedding_lab/design.md`](../features/embedding_lab/design.md) — Phase B/C/D 미구현 부분
- 기존 retrieval A/B 하네스: `chat/tests/evals/run_embedding_ab.py` (recall@k / MRR — 본 harness 의 보완)
