# Chroma → pgvector 전환 — 벡터 DB를 PostgreSQL 안으로 옮기기

## 한 줄 요약

벡터 검색용 별도 DB(Chroma SQLite)를 없애고, 이미 쓰고 있던 PostgreSQL에 pgvector 확장을 달아서 **관계형 데이터와 벡터 데이터를 한 DB에서 관리**하도록 전환한 작업.

## 비유 — 창고 통합

회사에 두 개의 창고가 있다고 상상하자:

| 창고 | 역할 | 문제 |
|------|------|------|
| **A창고** (PostgreSQL) | 사원 정보, 채팅 기록, 제품 DB | 잘 관리됨 |
| **B창고** (Chroma SQLite) | 벡터 임베딩 102개 | 별도 파일, 별도 관리, 열쇠도 따로 |

B창고의 물건이 적어서 A창고 안에 **벡터 전용 선반**(pgvector)을 하나 만들면:
- 관리 포인트 1개로 줄어듦
- 물건 찾을 때 "이 사람이 볼 수 있는 물건인가?" (ACL) 확인을 **선반에서 바로** 할 수 있음
- 백업, 복구, 모니터링이 한 곳에서 끝남

## 왜 이게 필요한가

| | 변경 전 (Chroma) | 변경 후 (pgvector) |
|---|---------|---------|
| **저장소** | `vector_store/chroma.sqlite3` (별도 파일) | PostgreSQL `knowledge_vectorchunk` 테이블 |
| **ACL 필터** | Python에서 `apply_acl_filter()` 후처리 | SQL `WHERE sensitivity IN (...)` — DB 레벨 |
| **백업** | Chroma 파일 + PostgreSQL 따로 | PostgreSQL 하나만 |
| **인프라** | 2개 (PG + Chroma) | 1개 (PG) |
| **LangChain 경고** | `Chroma` 클래스 deprecated | pgvector는 Django ORM — 외부 의존 최소 |
| **metadata 쿼리** | Chroma SDK 전용 문법 | 표준 SQL |

## 핵심 코드

### 1. VectorChunk 모델 (knowledge/models.py)

```python
from pgvector.django import VectorField

class VectorChunk(models.Model):
    chunk_id = models.CharField(max_length=64, unique=True)    # SHA256 id
    content = models.TextField()                                 # 검색 대상 텍스트
    embedding = VectorField(dimensions=3072)                     # Gemini 임베딩 벡터
    sensitivity = models.CharField(max_length=20, db_index=True) # ACL 필터링용
    source_file = models.CharField(max_length=512)               # 원본 파일 경로
    extra_metadata = models.JSONField(default=dict)              # 나머지 메타데이터
```

- `VectorField(dimensions=3072)` — pgvector가 PostgreSQL에 `vector(3072)` 타입 컬럼을 만듦
- `sensitivity`에 `db_index=True` — ACL WHERE절 속도 보장
- `extra_metadata` — Chroma처럼 자유 형식 metadata도 JSON으로 저장 가능

### 2. SQL 레벨 ACL 검색 (chat/utils.py)

```python
from pgvector.django import CosineDistance

# 사용자가 볼 수 있는 sensitivity 목록 계산
allowed = [s for s, v in SENSITIVITY_LEVEL.items() if v <= user_level_int]

# pgvector 코사인 거리 정렬 + ACL 필터 — 한 쿼리로 끝
results = (
    VectorChunk.objects
    .filter(sensitivity__in=allowed)           # ACL: SQL WHERE
    .order_by(CosineDistance("embedding", q))   # 유사도 정렬
    [:k]                                        # top-k
)
```

Chroma 방식과 비교:
```python
# 옛 방식 — 전부 가져온 뒤 Python에서 필터
results = chroma.similarity_search(question, k=20)  # ACL 무시
kept, redacted = apply_acl_filter(results, level)   # Python 후처리
```

### 3. PgvectorSink (chat/ingest/sinks/pgvector.py)

```python
class PgvectorSink:
    def write(self, docs):
        embeddings = emb_model.embed_documents(texts)  # 배치 임베딩
        for chunk, emb, id in zip(chunks, embeddings, ids):
            VectorChunk.objects.update_or_create(       # upsert
                chunk_id=id,
                defaults={"content": ..., "embedding": emb, ...}
            )
```

ChromaSink과 동일한 `BaseSink` 프로토콜 — `write()` + `delete_ids()`.

## 데이터 흐름

```
[신규 ingest]
파일 → Loader → Splitter → PgvectorSink
                               │
                               ▼
                    PostgreSQL VectorChunk 테이블
                    ┌─────────────────────────────┐
                    │ chunk_id │ content │ embedding│
                    │ sensitivity │ source_file │...│
                    └─────────────────────────────┘

[검색]
사용자 질문
    │
    ▼
RAGUtils.get_rag_context()
    │  VectorChunk.objects.exists()? → Yes
    │
    ▼
_pgvector_search()
    │  1. embed_query(question) → 3072차원 벡터
    │  2. WHERE sensitivity IN (allowed)  ← SQL ACL
    │  3. ORDER BY CosineDistance          ← 유사도 정렬
    │  4. LIMIT k
    ▼
keyword moderation (Layer 3)
    ▼
응답: { context, image_paths, docs, redacted_count }
```

## 확인 방법

```bash
cd Rag_Chat/backend

# 1. pgvector 데이터 확인
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -c "
import django; django.setup()
from knowledge.models import VectorChunk
print(f'Total chunks: {VectorChunk.objects.count()}')
print(f'Sample: {VectorChunk.objects.first()}')
"

# 2. 검색 테스트
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -c "
import django; django.setup()
from chat.utils import RAGUtils
result = RAGUtils.get_rag_context('Galaxy S25 배터리', k=3)
for doc in result['docs']:
    print(doc.page_content[:80])
"

# 3. 전체 테스트
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -m pytest chat/tests/ -v
# 기대: 97 passed
```

## 연습 문제

### 연습 1: sensitivity 필터 확인

pgvector 검색에서 `user_access_level="public"` 으로 검색하면 `internal` chunk가 나오지 않는지 확인해보자:

```python
result = RAGUtils.get_rag_context('Galaxy', k=5, user_access_level='public')
print(f'Docs: {len(result["docs"])}, Redacted: {result["redacted_count"]}')
# 현재 모든 chunk가 internal이므로 → Docs: 0, Redacted: 5
```

### 연습 2: 새 데이터 ingest

PgvectorSink를 사용해서 새 파일을 ingest해보자:

```python
from chat.ingest.pipeline import ingest_path
from chat.ingest.sinks.pgvector import PgvectorSink

count = ingest_path("path/to/file.txt", sink=PgvectorSink())
print(f"Ingested {count} chunks into pgvector")
```

그 다음 `VectorChunk.objects.count()`로 숫자가 늘었는지 확인.
