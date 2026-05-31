# DocCollection — 청크에 "어떤 종류의 데이터" 라벨 박기

## 한 줄 요약
RAG 벡터스토어에 들어가는 모든 청크에 `collection` (학습/사규/영업/유저) 라벨을 강제로 박아, 검색 시 SQL `WHERE collection = 'policy'` 한 줄로 namespace 분리할 수 있게 한 작업.

## 비유 — 도서관 서가
도서관 책마다 두 가지 라벨이 붙어있다:

| 라벨 | 의미 | 예 |
|---|---|---|
| **분류 스티커** (collection) | 어떤 주제 서가에 꽂힐지 | 문학 / 역사 / 과학 |
| **열람 등급** (sensitivity) | 누가 빌릴 수 있는지 | 일반 / 회원 전용 / 사서만 |

지금까지 RAG 는 **분류 스티커 없이 책을 다 한 통에 쌓아둔 상태**. "영업 자료만 검색" 같은 게 불가능. 이번에 모든 청크에 분류 스티커를 강제로 박는다.

## 왜 이게 필요한가

| 이전 (collection 없음) | 이후 (collection 있음) |
|---|---|
| 사규·영업·학습 데이터 한 통 | 분리된 서가 (4종) |
| 영업이 사규 검색 시 노이즈 ↑ | `collection=policy` 만 검색 → 정밀 |
| 새 데이터 종류 추가 시 비정형 | enum 추가 + migration → 통제됨 |
| "유저가 추가한 거" 식별 불가 | `collection=user` 로 신뢰도 분리 |

핵심: **검색 정확도** + **유지보수 통제** 동시에 잡음. 단어로는 "namespace 분리" 또는 "domain bucketing".

## 핵심 코드

### 1) 모델 enum 추가 (`knowledge/models.py`)
```python
class DocCollection(models.TextChoices):
    TRAINING = "training", "학습 자료"   # ML/사원 교육용
    POLICY   = "policy",   "사규·정책"   # 운영팀 적재 (default)
    SALES    = "sales",    "영업 데이터" # 영업팀 업로드
    USER     = "user",     "유저 추가"   # self-service
```
`TextChoices` = Django 이 enum. **자유 입력 금지** → 오타·신조어 자동 차단.

### 2) 청크에 컬럼 추가 (같은 파일)
```python
class VectorChunk(models.Model):
    sensitivity = models.CharField(...)        # 이미 있던 거
    collection  = models.CharField(             # ← 새로 추가
        max_length=20,
        choices=DocCollection.choices,
        default=DocCollection.POLICY,           # 기본은 사규로 가정
        db_index=True,                          # SQL 필터 빠르게
    )
```
`db_index=True` 중요 — 없으면 청크 수십만 개 쌓일 때 검색 느려짐.

### 3) ingest 파이프라인에 흘려넣기 (`chat/ingest/pipeline.py`)
```python
def ingest_path(..., collection: str = "policy") -> int:
    ...
    for chunk in splitter.split(d):
        chunk.metadata.setdefault("collection", collection)  # 청크에 박음
        chunks.append(chunk)
```

### 4) PgvectorSink 가 metadata → DB 컬럼으로 옮김 (`sinks/pgvector.py`)
```python
VectorChunk.objects.update_or_create(
    chunk_id=chunk_id,
    defaults={
        ...,
        "collection": chunk.metadata.get("collection", "policy"),
    },
)
```

## 데이터 흐름

```
backend/data/seed/policy/isdc_personnel_rules.pdf
      ↓
[seed_collections command]
      ↓ ingest_path(path, collection="policy", sensitivity="internal")
[pipeline.py]
      ↓ loader → splitter → 각 chunk.metadata["collection"] = "policy"
[PgvectorSink.write]
      ↓ embed + VectorChunk.objects.update_or_create(...)
[PostgreSQL VectorChunk 테이블]
  chunk_id | content | embedding | collection | sensitivity | ...
           | ...     | [vec]     | "policy"   | "internal"  | ...
```

## 확인 방법

### A. 마이그레이션 적용
```bash
cd backend
venv/bin/python manage.py makemigrations knowledge
venv/bin/python manage.py migrate knowledge
```

### B. seed 데이터 적재
```bash
# 폴더 구조: backend/data/seed/<collection>/*.pdf
venv/bin/python manage.py seed_collections
venv/bin/python manage.py seed_collections --only policy
venv/bin/python manage.py seed_collections --sensitivity confidential
```

### C. DB 에 박혔는지 검증 (Django shell)
```python
from knowledge.models import VectorChunk
from django.db.models import Count

VectorChunk.objects.values("collection").annotate(n=Count("id"))
# → [{'collection': 'policy', 'n': 140}, ...]

VectorChunk.objects.filter(collection="policy").count()
# → 정확히 policy 만 카운트
```

### D. ACL 필터 prototype
```python
# 사원 (USER role) — 영업·기밀 빼고만 검색
allowed = ["training", "policy"]
VectorChunk.objects.filter(collection__in=allowed).count()
```

## 연습 문제

### 문제 1 — 새 collection 추가
회사가 "법무팀 계약서" 도메인을 추가하고 싶다.
1. `DocCollection` enum 에 `LEGAL = "legal", "법무"` 추가
2. `makemigrations` 가 어떤 SQL 을 생성할지 예측해보기 (힌트: CHECK constraint? 아니면 그냥 string?)
3. 기존 `default=policy` 청크들이 영향받나? 받으면 왜, 안 받으면 왜?

### 문제 2 — sensitivity 와 collection 의 관계
같은 청크가 `collection=sales, sensitivity=confidential` 일 수 있나?
1. 이 조합이 의미하는 시나리오 한 문장 작성
2. 사원(USER)이 "영업 계약 단가" 라고 질문하면 이 청크가 검색에 잡혀야 하나? `Sensitivity` ladder + `User.access_level` 비교로 설명

### 문제 3 — default 의 함정
`collection` default = `policy`. ingest 시 명시 안 하면 모두 `policy` 로 들어간다.
1. 영업 데이터를 default 로 적재했을 때 어떤 ACL 사고가 날 수 있나?
2. `default` 없애고 `null=False` 로 강제 picker 만들면 장단점은?
3. `seed_collections` 커맨드가 이 함정을 어떻게 피하는지 코드에서 찾아보기 (힌트: 폴더 이름 = collection 값)

## 관련 문서
- `knowledge/models.py` — Sensitivity / DocCollection enum 정의
- `chat/ingest/pipeline.py` — ingest_path 의 collection 파라미터 흐름
- `chat/ingest/sinks/pgvector.py` — metadata → DB 컬럼 매핑
- `chat/management/commands/seed_collections.py` — 폴더 구조 기반 seed
- 메모리: [project_data_catalog_direction.md](~/.claude/projects/.../memory/project_data_catalog_direction.md) — 전체 Phase A~D 계획
