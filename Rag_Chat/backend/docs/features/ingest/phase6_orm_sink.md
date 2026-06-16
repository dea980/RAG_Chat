# Phase 6 — ORM Sink + CSV fields 보존 (작업 기록)

> 정형 데이터 (CSV/XLSX) 를 Chroma 벡터 + Django ORM **둘 다** 에 동시에
> 적재할 수 있게 한 hybrid retrieval 의 ORM 쪽 끝.

---

## 1. 동기

기존엔 모든 RawDoc 이 `ChromaSink` → 벡터 스토어로만 갔다. 정형 데이터
(`galaxy_lineup.csv` 등 spec 표) 는 가격·RAM 같은 정확값을 묻는 질문에 대해
*벡터 근사 검색* 이 부정확하다 — "S25 Plus 256GB 가격?" 같은 쿼리는 SQL
exact lookup 이 답이다.

이 PR 은 분류 3 (정형) 데이터를 `knowledge.Product` 테이블에 함께 적재해
검색 시 사용처가 SQL/ORM 또는 벡터를 선택할 수 있는 토대를 만든다.

## 2. 추가된 파일

```
backend/chat/ingest/sinks/knowledge_orm.py   # KnowledgeOrmSink — CSV/XLSX → Product upsert
backend/chat/ingest/sinks/composite.py       # CompositeSink — 여러 sink fan-out
backend/chat/tests/test_knowledge_orm_sink.py # 7 unit tests
backend/docs/features/ingest/phase6_orm_sink.md  # 본 문서
```

## 3. 수정된 파일

```
backend/chat/ingest/loaders/structured/csv.py
  — LangChain CSVLoader 래핑 제거, csv.DictReader 직접 사용.
    metadata['fields'] 에 실제 컬럼 값 dict 가 들어가도록 (이전엔 LangChain 의
    source/row 만 들어가 ORM 매핑 불가).

backend/chat/ingest/sinks/__init__.py
  — ChromaSink / KnowledgeOrmSink / CompositeSink export 추가.

backend/chat/build_vector_store.py
  — 모듈 상단에 DeprecationWarning 추가. Ingest layer 가 대체. 다음 정리
    라운드에서 제거 예정.
```

## 4. 매핑 규칙

`KnowledgeOrmSink` 의 RawDoc → Product 매핑:

| Product 필드 | 출처 |
|---|---|
| `name`        | `metadata['fields'][name_column]` (기본 컬럼 `Model`) |
| `description` | `RawDoc.content` (loader 가 만든 "컬럼: 값" 직렬화) |
| `specs`       | `metadata['fields']` 전체 (name_column 제외) |
| `category`    | `Product.Category.PRODUCT` (고정) |
| `department`  | 생성자 `default_department` (기본 `"영업팀"`, 없으면 자동 생성) |
| `is_active`   | `True` |

`Product.name` 으로 `update_or_create` → 같은 name 재호출은 upsert (멱등).

비정형 source_type (pdf, txt, ocr ...) RawDoc 은 silently skip — `ChromaSink`
가 처리하도록 둔다.

## 5. Hybrid 사용 예

```python
from chat.ingest.pipeline import ingest_path
from chat.ingest.sinks import ChromaSink, CompositeSink, KnowledgeOrmSink

ingest_path(
    "backend/data/samples/galaxy_lineup.csv",
    sink=CompositeSink([
        ChromaSink(),           # 모든 청크 → 벡터
        KnowledgeOrmSink(),     # 정형만 → Product
    ]),
)
```

`CompositeSink` 는 자식 sink 의 `WriteResult.ids` 를 `<prefix>:<id>` 로 묶어
한 list 로 돌려준다 (`chroma:<sha256>`, `knowledgeorm:product:<pk>`). 같은
prefix 로 `delete_ids` 가 원 sink 로 역디스패치한다.

## 6. CSV fields 형태 변경 — 영향 범위

`metadata['fields']` 가 LangChain 메타 → 실제 컬럼 dict 로 바뀐 변경.

확인된 영향:
- `ChromaSink._to_lc_document` — `flat_meta` 가 scalar 만 통과시키므로
  `fields` (dict) 는 자동으로 drop. 기존 임베딩 영향 없음.
- 다른 grep 결과 caller 없음 (`metadata['fields']` 참조하는 코드 0건).

## 7. 단위 테스트

`chat/tests/test_knowledge_orm_sink.py` — 7 개 함수, `@pytest.mark.django_db`:

1. `test_upserts_csv_rows_into_products` — 2행 적재 + 필드 검증
2. `test_idempotent_on_repeat_write` — 같은 입력 재호출 시 중복 없음
3. `test_skips_non_structured_doc_types` — PDF/TXT 무시
4. `test_uses_default_department_creates_it_once` — 부서 자동 생성
5. `test_custom_name_column` — name_column 인자
6. `test_delete_ids_removes_products` — delete_ids 동작
7. `test_delete_ids_ignores_unknown_id_formats` — 모르는 prefix 무시

**현재 실행 불가** — `health/ready/` 가 `database ok=false, password
authentication failed for user "postgres"` 로 응답하는 **기존(pre-existing)
DB 인증 문제** 때문. postgres volume 에 옛 비밀번호가 굳어 있을 가능성.
해결 후 통합 검증 필요. import / 문법 / dry-run 은 통과.

## 8. 안 한 것 (의도적)

- **`seed_demo` 갱신** — 현재 `seed_demo` 가 Product 8개를 하드코딩한다.
  KnowledgeOrmSink 가 동작하면 CSV 한 줄로 대체 가능하지만, seed/시연용
  데이터 (가격·color 변종) 와 새 lineup (모델 단위 풀 스펙) 이 다르므로
  이전을 별도 단계로 분리. 다음 세션 (또는 별도 PR) 에서 다룸.
- **"Chroma 에 자연어 description 만"** — work_distribution.md 의 표현.
  지금은 CSV → ChromaSink 이 "Model: ...\nColor: ...\n..." 풀 텍스트를 그대로
  임베딩한다. 진짜 자연어 한 줄로 압축하려면 (a) 컬럼 → 문장 템플릿,
  (b) LLM 으로 description 생성 — 둘 다 별도 결정 필요. 이번엔 ORM 추가만.
- **pipeline 의 `sink: list[BaseSink]` 직접 지원** — CompositeSink 으로 우회
  가능해서 pipeline 인터페이스 변경 없이 처리. 추후 빈도 높아지면 검토.

## 9. 후속 작업

1. **DB 인증 fix** — postgres volume 비밀번호 재설정 또는 .env 일치 작업.
   `health/ready/` 가 200 + ok=true 가 되면 KnowledgeOrmSink 통합 테스트 실행.
2. **galaxy_s25_data.csv 실적재** — `ingest_path("galaxy_s25_data.csv",
   sink=KnowledgeOrmSink())` 1회 실행 → seed_demo 의 하드코딩 데이터와
   중복/덮어쓰기 확인.
3. **seed_demo 갱신** — CSV ingest 로 대체 (1번 + 2번 후).
4. **build_vector_store.py 완전 제거** — 호출처 없는지 확인 후 다음 정리 PR.
