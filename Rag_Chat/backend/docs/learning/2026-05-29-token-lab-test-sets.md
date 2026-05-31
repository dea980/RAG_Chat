# Token Lab — Test set 추가 (언어·콘텐츠 타입 비교 자동화)

## 한 줄 요약
같은 의미를 6언어로 / 같은 언어를 6콘텐츠 타입으로 묶은 **test set** 11개를 Token Lab 에 박아, "한국어가 영어보다 토큰을 몇 배 먹는가" 를 한 번 클릭으로 비교한다.

## 비유
환율판이다. "1달러 = ?원" 만 봐서는 의미가 없고, **같은 컵라면을 서울/도쿄/베를린에서 사봐야** 진짜 구매력 차이가 보인다. Test set 은 그 "같은 컵라면" 카탈로그. 어느 모델로 보든(GPT-4o · Claude · Gemini) **동일 컨텐츠를 동일 비교축으로** 환산해 보여준다.

## 왜 이게 필요한가

| 이전 (1세대 Token Lab) | 이후 (test sets) |
|---|---|
| `LANGUAGE_SAMPLES` 6개 고정 — 한·영·일·중·코드·혼합 1문장씩 | 11개 test set 캡슐화, 사이드바에서 셀렉트 |
| 시나리오 하나(짧은 RAG 질문) | A1~A5 = 5 시나리오(인사·RAG질문·장문·스펙·구어) × 6 언어 (Ko/En/Ja/Zh/Es/De) |
| 콘텐츠 타입 비교 없음 | B1~B6 = prose / code / JSON / markdown / 숫자 / emoji+URL |
| 사용자가 직접 텍스트를 붙여 비교해야 비용 추정 가능 | "RAG 질문은 한국어가 영어 대비 1.86× cl100k 토큰" 같은 결론을 즉시 노출 |
| 모든 결과를 사용자가 눈으로 비교 | parallel set 은 자동으로 `× ref` (영어 대비 배율) 컬럼 추가 |

운영 비용 추정에 직결한다 — Korean RAG 질문 1건이 영어 대비 cl100k 1.86×, o200k 1.31× 라는 게 실제 input token 비용 배율이다.

## 핵심 코드 (token_utils.py)

```python
TEST_SETS = [
    {
        "id": "parallel_rag_question",   # UI selector key
        "category": "parallel",           # parallel(언어 비교) | content_type(형식 비교)
        "label": "A2. RAG 질문 (parallel · 6언어)",
        "description": "전형적 사내 RAG 질문 — 제품 스펙 / 가격 / 색상.",
        "samples": [
            {"language": "Korean",  "text": "갤럭시 S25 Ultra 512GB ..."},
            {"language": "English", "text": "Summarize the camera ..."},
            # ... Ja / Zh / Es / De
        ],
    },
    # A1·A3·A4·A5 (parallel) + B1~B6 (content_type)
]

def test_set_comparison(set_id: str) -> dict:
    """주어진 set_id 의 각 sample 을 analyze_text 로 돌려 token 수 비교 row 생성."""
    test_set = next((ts for ts in TEST_SETS if ts["id"] == set_id), None)
    if test_set is None:
        raise ValueError(f"unknown test_set id: {set_id}")
    samples = [
        {**sample, **analyze_text(sample["text"])}  # 실제 코드는 키별로 명시
        for sample in test_set["samples"]
    ]
    return {"id": ..., "category": ..., "label": ..., "samples": samples}
```

핵심:
- **list_test_sets()** — 메타데이터만 (UI dropdown 채울 때 사용, 토큰 계산 X)
- **test_set_comparison(id)** — 실제 토큰 분석. unknown id → `ValueError` (view 에서 400 으로 매핑)
- 기존 `LANGUAGE_SAMPLES` / `language_sample_comparison()` 보존 — backward compat

## 데이터 흐름

```
frontend/pages/token_lab.py
   │  (페이지 로드)
   ├──► GET  /api/v1/triple/tokens/test-sets/     ──► TokenTestSetsAPIView
   │                                                       │
   │                                                       └─► list_test_sets()
   │  (사용자가 사이드바에서 set 선택 + '계산' 클릭)
   └──► POST /api/v1/triple/tokens/estimate/
              {text, include_samples, test_set: "parallel_rag_question"}
                                                  │
                                                  └─► TokenEstimateAPIView
                                                          ├─► analyze_text(text)         # 본문
                                                          ├─► language_sample_comparison()  # legacy 6
                                                          └─► test_set_comparison(id)    # 신규
                                                                  │
                                                                  └─► 각 sample × profile (cl100k, o200k, gemini, ...)
```

## 측정 결과 (TOKENLAB_ENABLE_TIKTOKEN=1, exact)

A2 RAG 질문 (parallel · 6언어):

| Lang | chars | cl100k | × EN | o200k | × EN |
|---|---:|---:|---:|---:|---:|
| Korean | 67 | 54 | **1.86×** | 38 | **1.31×** |
| English | 134 | 29 | 1.00 | 29 | 1.00 |
| Japanese | 64 | 54 | 1.86× | 34 | 1.17× |
| Chinese | 53 | 38 | 1.31× | 29 | 1.00× |
| Spanish | 142 | 36 | 1.24× | 33 | 1.14× |
| German | 145 | 39 | 1.34× | 34 | 1.17× |

읽는 법: **o200k 가 한국어/일본어 부풀림을 절반 가량 흡수한다** (1.86→1.31). GPT-4o 기반 호출이 GPT-4 기반보다 한국어 비용에 유리하다는 정량 근거.

## 확인 방법

```bash
cd Rag_Chat/backend

# 1. 단위 동작 확인 (exact 카운트)
TOKENLAB_ENABLE_TIKTOKEN=1 ./venv/bin/python -c "
from chat.token_utils import test_set_comparison
r = test_set_comparison('parallel_rag_question')
for s in r['samples']:
    cl = next(p for p in s['profiles'] if p['id'] == 'openai_cl100k')
    print(f\"{s['language']:10} chars={s['characters']:4} cl100k={cl['tokens']}\")
"

# 2. API 라우트 (서버 띄운 후)
curl -s http://localhost:8000/api/v1/triple/tokens/test-sets/ | jq '.test_sets | length'
curl -s -X POST http://localhost:8000/api/v1/triple/tokens/estimate/ \
     -H "Content-Type: application/json" \
     -d '{"text":"hi","test_set":"content_json"}' | jq '.test_set.samples[0].profiles[0]'

# 3. UI 확인
cd ../frontend && streamlit run app.py
# → token_lab 페이지 → 사이드바 "Test set" 셀렉트 → 계산
```

## 연습 문제

1. **C 카테고리 추가**: 새 category `"length"` 를 정의하고 같은 한국어 문장을 50/200/1000/3000자로 늘려 길이별 token/char 비율 변화를 확인하는 set 3개를 추가하라. (`TEST_SETS` 리스트에 항목만 추가하면 끝나도록 구조가 이미 받쳐주는지 검증)
2. **× ref 컬럼을 cl100k 가 아닌 o200k 기준으로 토글**: 현재 frontend 는 `chart_profile` 셀렉트 값을 그대로 사용하지만, 비율 비교의 "ref language" 는 English 로 고정돼 있다. ref 언어도 셀렉트로 만들어 일본어 운영팀이 "일본어 대비 다른 언어" 를 볼 수 있게 하라. (`pages/token_lab.py` 의 `ref_row` 선택부 수정)
