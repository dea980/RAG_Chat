ㅇ# IR (정보검색) 과 RAG 구조 — 종합 가이드

## 한 줄 요약

**IR(Information Retrieval) = "문서 더미에서 질문에 가장 가까운 조각을 찾아주는 일"** 이고,
**RAG = "IR 결과를 LLM 한테 컨닝페이퍼로 줘서 답변하게 하는 패턴"** 이다. 이 문서는
오늘 만든 97 chunks 벡터 인덱스가 이 그림 어디에 들어가는지 끝까지 따라간다.

---

## 1부 — IR 기초

### 1.1 비유: 거대 도서관 사서

당신이 시 도서관에 들어가서 사서한테 묻는다고 생각해라.

> "Galaxy Z Fold6 가격이 얼마야?"

사서가 할 수 있는 행동은 두 가지:

- **(A) 정확 검색** — 색인카드에서 "Galaxy Z Fold6" 라는 *정확한 단어* 가
  들어간 책을 찾는다. SQL 의 `WHERE model = 'Galaxy Z Fold6'` 와 같다.
- **(B) 의미 검색** — "이 질문은 *폴더블 폰의 가격* 에 관한 거니까, 비슷한
  주제를 다룬 챕터를 가져오자". 단어가 똑같지 않아도 *의미가 닮은* 페이지를
  꺼낸다. 사용자가 "Z Fold6 얼마야?" 라고 줄여서 물어도 "Galaxy Z Fold6 시작가는
  $1,899.99" 가 적힌 문단을 찾아낸다.

**RAG 의 IR 은 (B) 의미 검색이다.** 정확 검색은 SQL/DB 의 일이고, RAG 는
"단어가 안 맞아도 뜻이 비슷하면 가져온다" 를 한다.

### 1.2 의미가 닮았다 = 수학적으로 뭔가?

문장을 사람 머릿속에서는 "뜻" 으로 이해하지만, 컴퓨터는 수가 아니면 못 다룬다.
그래서 모든 문장을 **벡터 (수의 묶음)** 로 바꾼다.

| 문장 | 벡터 (실제로는 1536 차원) |
|---|---|
| "Galaxy Z Fold6 가격" | `[0.12, -0.34, 0.88, ..., 0.05]` |
| "폴더블 폰 시작가" | `[0.10, -0.31, 0.85, ..., 0.07]` |
| "강아지 산책" | `[-0.89, 0.42, 0.01, ..., -0.66]` |

위 1번과 2번은 *벡터가 비슷한 방향* 을 가리킨다 — 코사인 유사도 (cosine
similarity) 가 1 에 가깝다. 3번은 동떨어진 방향 — 0 에 가깝다.

이 변환을 해주는 함수가 **임베딩 모델 (embedding model)**. 우리 프로젝트는
OpenAI 의 `text-embedding-3-small` 을 쓴다. (Gemini quota 가 죽어서 오늘 갈아탔다.)

### 1.3 그래서 IR 한 단어로 = ?

> 코퍼스(corpus, 문서 모음) 를 미리 벡터로 만들어 두고,
> 질문이 오면 질문도 벡터로 만들어서,
> 코사인 거리가 가장 가까운 N개 (top-k) 를 돌려준다.

이게 끝이다. 나머지는 다 이 위의 살이다.

---

## 2부 — RAG 의 IR 레이어

### 2.1 RAG 전체 그림

```
[원본 문서]                             [사용자 질문]
   ↓                                        ↓
(A) Ingest                               (D) Embed
   ↓                                        ↓
(B) Chunk                                (E) Retrieve (similarity_search)
   ↓                                        ↓
(C) Embed + Index                  ←──→  [top-k 청크]
                                            ↓
                                         (F) Augment — 청크를 prompt 에 끼움
                                            ↓
                                         (G) Generate — LLM 이 답변
                                            ↓
                                         [최종 답변 + citation]
```

**왼쪽 = "오프라인 인덱싱 단계"**, 일 한 번 해두면 끝.
**오른쪽 = "온라인 질의 단계"**, 사용자 질문마다 매번.

### 2.2 우리 프로젝트의 IR 레이어 매핑

| 단계 | 우리 코드 위치 | 오늘 한 일 |
|---|---|---|
| (A) Ingest — 파일 읽기 | `chat/ingest/loaders/` | samples/* 추가 |
| (B) Chunk — 문서 쪼개기 | `chat/ingest/splitters/` | (변경 없음, row/heading 자동) |
| (C) Embed + Index | `chat/ingest/sinks/chroma.py` | provider 갈아탐 (gemini → openrouter) |
| (D) Embed 질문 | `provider_manager.get_embedding_model()` | (C) 와 같은 모델 자동 사용 |
| (E) Retrieve | `vector_store.similarity_search(q, k)` | 4 쿼리 검증 |
| (F) Augment | `chat/pipeline/modules.py` | (stash 에서 복구한 Korean prompt) |
| (G) Generate | 같은 파일 | OpenRouter gpt-oss-20b |

### 2.3 왜 인덱싱을 미리 해두나?

| 방식 | 사용자 한 명 질문 처리 비용 | 단점 |
|---|---|---|
| 매번 모든 문서를 LLM 컨텍스트에 넣음 | 토큰 폭발 (97 chunks × 매번) = 비쌈 + 답변 늦음 + context length 초과 | **현실에서 불가** |
| 매번 모든 문서를 임베딩 | OpenAI API 콜 97번 × 매번 = 비싸고 느림 | 비현실적 |
| **(우리 방식) 미리 임베딩 → Chroma 저장 → 질문 시 top-k 만 꺼냄** | Chroma 디스크 read 1번 + 임베딩 1번 (질문) | 그래서 RAG 가 표준 |

### 2.4 핵심 코드 (5줄)

`chat/ingest/sinks/chroma.py:89` — 인덱싱 한 줄:

```python
vector_store.add_documents(documents=lc_docs, ids=ids)
#                                              ^^^^^^^^
# 결정론적 id (sha256(source+section+chunk)). 같은 청크 재인덱싱 시
# 같은 id 로 upsert → 중복 안 쌓임.
```

`chat/pipeline/modules.py` — 검색 한 줄:

```python
hits = vector_store.similarity_search(query, k=4)
# 질문도 같은 임베딩 모델로 변환 → 코사인 top-4 청크 반환
```

### 2.5 청킹 (B 단계) 가 왜 중요한가

원본 `foldable_handbook.md` 가 5000 단어인데 통째로 임베딩하면:
- 벡터 1개에 너무 많은 의미가 섞임 → 검색 정확도 떨어짐
- LLM 컨텍스트에 통째로 넣으면 토큰 폭발

그래서 **헤딩 (`## 2. Galaxy Z Fold6`) 단위로 쪼갠다**. 우리 splitter:

- `lineup.csv` 같은 행 데이터 → **row splitter** (한 행 = 한 청크)
- `handbook.md` 같은 마크다운 → **heading splitter** (`##` 단위)
- 사규/PDF → **clause splitter** (제N조 단위)
- 그 외 → **recursive** (문자 수 기준)

`build_vectors` 가 확장자 보고 자동 선택. (`--splitter` 로 강제 가능.)

---

## 3부 — IR 평가 지표

### 3.1 비유: 시험 채점

당신이 만든 IR 시스템이 "잘 동작한다" 를 어떻게 증명할까? 영업팀이
"방금 답변 이상한데?" 라고 했을 때 무얼 측정해야 하나?

학생 5명한테 시험 답안지를 받았다고 치자. 채점할 때:
- **정답률** = 맞은 개수 / 총 문제 수
- **빠뜨린 정답** = 정답인데 안 적은 것

IR 도 똑같다. *질문마다 "정답 청크가 무엇인지" 가 미리 정해진 데이터셋* 이
있으면 측정 가능. 이게 **labeled QA dataset**.

### 3.2 주요 지표 4개

데이터셋: 질문 100개, 각 질문마다 "이 청크가 정답" 으로 라벨링.

| 지표 | 정의 | 비유 |
|---|---|---|
| **Precision@k** | top-k 안에 정답이 있는 비율 | "사서가 가져온 5권 중 진짜 답을 담은 책 비율" |
| **Recall@k** | 모든 정답 중 top-k 가 잡은 비율 | "원래 답이 3권에 흩어져 있는데, 사서가 그 중 몇 권 가져왔나" |
| **MRR (Mean Reciprocal Rank)** | 정답이 등장한 순위의 역수 평균. top-1=1.0, top-3=0.33 | "사서가 답을 1번째로 꺼냈는지 5번째로 꺼냈는지" |
| **nDCG@k** | 순위가 높을수록 가중치 큰 점수 | "정답이 상위에 있을수록 점수 후함" |

### 3.3 오늘 결과는 측정된 거 아님

4 쿼리 eyeball 만 했다. 즉:
- "Z Fold6 가격" → top-1 = 색상 섹션. **이게 정답인지 아닌지 우리가 판단 못함.**
  정답은 "§4.6 가격 — Galaxy Z Fold6 시작가는..." 인 청크여야 함.
- 라벨 없이는 "**그럴 듯해 보임**" 까지가 한계.

진짜 IR 평가:

```yaml
# backend/data/embedding_eval/queries.yaml (예시)
- query: "Z Fold6 가격"
  expected_chunk_id: "foldable_handbook.md::§4.6"
- query: "Buds3 Pro ANC 지원?"
  expected_chunk_id: "buds_lineup.csv::row=Galaxy Buds3 Pro"
```

이 dataset 으로 `chat/embedding_eval.py` (오늘 untracked 에 있음) 가 돌면
top-1, top-3, top-5 정답률 → 숫자가 나옴. 그제서야 "IR 잘 됨" 이라 말할 수 있음.

### 3.4 어떤 지표를 봐야 하나? (영업팀 챗봇 기준)

- **MRR** = 사용자가 첫 답변에서 만족하는지 측정. 영업 응대 환경에서 가장 중요.
- **Recall@5** = "정답 청크가 top-5 안에 들어와야 LLM 이 답변 생성 가능".
  LLM 한테 청크 5개 주는데 그 안에 정답 없으면 LLM 도 헛소리함.
- Precision 은 LLM 이 노이즈 청크 필터링을 어느 정도 해주니 후순위.

---

## 데이터 흐름 (오늘 만든 시스템)

```
1. 원본 파일 추가
   backend/data/samples/foldable_lineup.csv        ←  agent WebFetch 결과
   backend/data/samples/foldable_handbook.md
   backend/data/samples/a_series_lineup.csv
   ... (11개 더)

2. python manage.py build_vectors --rebuild
   └─ build_vectors.py 가 DEFAULT_SOURCES 순회
      └─ ingest_path(path) 호출
         ├─ loader 가 파일 읽음 (확장자별)
         ├─ splitter 가 청크로 쪼갬 (15 sources → 97 chunks)
         ├─ ChromaSink.write(chunks)
         │   └─ embedding_model.embed_documents(texts)  ← OpenRouter 호출
         │   └─ chroma collection.upsert(vectors, ids)
         └─ IngestManifest 에 (file_hash, chunk_ids) 기록

3. 사용자 질문 ("Z Fold6 가격")
   └─ chat/views.py
      └─ pipeline 의 RetrievalModule
         └─ vector_store.similarity_search(질문, k=4)
            ├─ embedding_model.embed_query(질문)
            └─ chroma 가 코사인 top-4 반환
      └─ pipeline 의 ReasoningModule (선택)
      └─ pipeline 의 GenerationModule
         └─ "다음 문서를 참고해서 답해" + 청크 + 질문 → LLM
   └─ 답변 + citation (어느 청크에서 가져왔는지)
```

---

## 확인 방법

```bash
# 1. 코퍼스 빌드 (수정 후 매번)
cd Rag_Chat/backend
./venv/bin/python manage.py build_vectors            # 증분 (manifest dedup)
./venv/bin/python manage.py build_vectors --rebuild  # 전체 재구축

# 2. 검색 동작 확인 (Django shell)
./venv/bin/python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'triple_chat_pjt.settings')
django.setup()
from chat.providers import provider_manager
vs = provider_manager.get_vector_store()
print('chunks:', vs._collection.count())
for h in vs.similarity_search('Z Fold6 가격', k=3):
    print(h.metadata.get('source_file', '?'), '|', h.page_content[:60])
"

# 3. 정량 평가 (앞으로 할 일)
./venv/bin/python manage.py embedding_eval --dataset queries.yaml
```

---

## 연습 문제

### 문제 1 (쉬움)

`build_vectors --rebuild` 실행했더니 `Total chunks written: 97` 나왔다.
파일을 새로 1개 (`new_product.md`) 추가하고 `--rebuild` **없이** 다시
실행했다. 무슨 일이 벌어질까? `IngestManifest` 가 어떤 역할을 하는지 답하라.

> **힌트**: `build_vectors.py` 의 `manifest dedup` 주석을 읽어라.

### 문제 2 (중간)

`similarity_search(q, k=4)` 가 4개를 반환했는데 정답 청크가 5번째에 있었다.
**MRR** 은 어떻게 계산되나? 그리고 이 문제를 줄이려면 무엇을 바꿔야 하나?
2개 이상 선택지를 답하라.

> **힌트**: 청킹 단위, k 값, reranker 도입을 떠올려라. reranker 는 우리
> 프로젝트의 `feature/onnx-reranker` 브랜치 이름의 원래 목적이다 (현재 deferred).

### 문제 3 (어려움)

오늘 ingest 한 `a_series_handbook.md` 의 "A55 의 카메라" 섹션은 OIS 가
있다고 적혀있다. 그런데 `a_series_lineup.csv` 의 A55 행은 카메라 컬럼에
OIS 명시가 없다고 가정하자. 사용자가 "A55 OIS 지원해?" 라고 물으면 어떤
청크가 top-1 으로 나올 가능성이 높은가? 왜 그런가? RAG 시스템에서 이런
*같은 사실의 표현 차이* 가 만드는 위험은 무엇인가?

> **힌트**: handbook 청크는 "A55 의 메인 카메라는 50MP f/1.8 OIS" 라는 문장이
> 들어있고, csv 청크는 `Main Camera: 50MP f/1.8` 정도의 줄로 들어있다.
> 두 청크의 embedding 벡터가 "OIS" 라는 단어를 얼마나 강하게 담을지 생각해라.

---

## 다음 단계 (이 문서를 끝낸 다음에 할 일)

- [ ] labeled QA dataset 만들기 (`backend/data/embedding_eval/sales_qa.yaml`)
- [ ] `embedding_eval` mgmt cmd 로 MRR / Recall@5 측정
- [ ] caveat 필드 수동 보완 (Z Flip6 dimensions, Tab USD 가격 등)
- [ ] reranker 재개 시점 결정 — MRR 이 0.6 이하면 도입 정당화

---

## 출처

- 우리 코드: `chat/ingest/`, `chat/pipeline/`, `chat/embedding_views.py`
- LangChain Chroma: https://python.langchain.com/docs/integrations/vectorstores/chroma
- 임베딩 모델 비교 (MTEB 리더보드): https://huggingface.co/spaces/mteb/leaderboard
- 본 학습 문서: `Rag_Chat/backend/docs/learning/2026-05-29-ir-rag-concepts.md`
