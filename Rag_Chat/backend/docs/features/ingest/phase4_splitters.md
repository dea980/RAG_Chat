# Ingest Phase 4 — Clause / Heading Splitters (다른 agent 통합 기록)

> Codex 가 추가한 구조 기반 splitter 2종.
> 핵심 설계 결정: **opt-in only** — 확장자만으로는 안전한 자동 dispatch 불가하므로
> `default_splitter_for()` 에는 등록하지 않고 `splitter_by_name()` 명시 호출만 허용.

---

## 1. 추가된 파일

```
chat/ingest/splitters/clause.py        66 lines   ClauseSplitter   ("제 N 조" / "Article N")
chat/ingest/splitters/heading.py       58 lines   HeadingSplitter  (markdown heading 계층)
chat/tests/ingest/test_clause_splitter.py    85 lines
chat/tests/ingest/test_heading_splitter.py   70 lines
```

수정 (다른 agent):
```
chat/ingest/splitters/__init__.py      두 클래스 _BY_NAME 등록, DEFAULT_BY_SOURCE 는 unchanged
```

## 2. 핵심 결정 — opt-in only

`__init__.py` 의 주석이 결정 근거를 명시:

> heading/clause 는 DEFAULT_BY_SOURCE 에 넣지 않는다 — 확장자만으론 자동
> 선택이 위험하다(clause=조항 문서, heading=구조화된 md). flat 마크다운/
> 일반 PDF 에 자동으로 걸면 청킹이 오히려 깨지므로 splitter_by_name 으로
> 명시 선택(opt-in)만 허용.

즉:

| 호출 | 결과 |
|---|---|
| `ingest_path("사규.pdf")` | RecursiveSplitter (default 유지) |
| `ingest_path("사규.pdf", splitter=splitter_by_name("clause"))` | ClauseSplitter (명시) |
| `splitter_by_name("heading")` | HeadingSplitter |

이 결정의 트레이드오프:
- **+** 일반 문서가 잘못된 splitter 로 깨지지 않음 (안전 default)
- **+** 사용자 명시 책임 — 사규/법규임을 아는 사람이 의도적으로 선택
- **−** "이 PDF 가 사규인가?" 판단 자동화 부재 → 추후 source_type 세분화
  (`pdf-legal`, `md-structured`) 가 필요하면 그때 매핑 추가

## 3. ClauseSplitter — "제 N 조" 조항 단위

**용도**: 사규/법규/약관처럼 조항 번호가 명확한 한국어/영어 문서.

**검증 (smoke)**:
```
input:  "제1조 (목적) 이 규정은... 제2조 (적용범위) 이는..."
output: 1개 청크 (테스트 데이터가 짧아서) — sections=['제1조']
```

각 청크의 `section` 필드에 조항 번호 (예: `"제39조"` / `"Article 5"`) 가
저장됨 → retrieval 결과에서 출처 노출 가능. 7강 강사가 "39조 정답 못
찾다 조항 단위 splitter 로 찾은" 그 시나리오를 코드로 풀어냄.

## 4. HeadingSplitter — Markdown heading 계층

**용도**: 구조가 살아있는 Markdown / HTML heading 기반 문서.

**검증 (smoke)**:
```
input:  "# Title\n\n## Section A\nbody A\n\n## Section B\nbody B"
output: 2개 청크 (## level 단위)
```

heading 계층을 보존하므로 retrieval 결과가 "어느 섹션에서 왔는가" 답할 수 있음.

## 5. 호출 패턴

```python
from chat.ingest.pipeline import ingest_path
from chat.ingest.splitters import splitter_by_name

# 사규 PDF 를 조항 단위로 ingest
ingest_path(
    "/path/to/사규_v3.pdf",
    splitter=splitter_by_name("clause"),
    source_uri_override="upload://사규_v3.pdf",
)

# 구조화된 docs (예: 매뉴얼) 을 heading 단위로
ingest_path(
    "/path/to/manual.md",
    splitter=splitter_by_name("heading"),
)
```

기존 호출자 영향:
- `build_vectors` (CLI default sources) — splitter 안 줘서 자동 dispatch
  유지 (csv→row, xlsx→row). 영향 없음.
- `IngestUploadAPIView._ingest_uploaded_file` — splitter 안 주는 형태라
  자동 dispatch. PDF/DOCX 가 올라와도 recursive. clause/heading 으로 가려면
  업로드 시 사용자 선택 UI 필요 (별도 PR).

## 6. 검증 결과

```
registered names: ['recursive', 'row', 'heading', 'clause']
default mappings: {csv:row, excel:row, pdf:recursive, docx:recursive,
                   html:recursive, txt:recursive, md:recursive}
opt-in policy: pdf/html still default=recursive  ✓
explicit clause: ClauseSplitter
explicit heading: HeadingSplitter
clause split smoke:  1 chunks, sections=['제1조']
heading split smoke: 2 chunks
```

테스트:
```bash
./venv/bin/python -m pytest chat/tests/ingest/test_clause_splitter.py \
                            chat/tests/ingest/test_heading_splitter.py
```

(테스트 실행은 다음 세션에서 — 이 doc 은 통합 검토 단계)

## 7. 일관성 노트

- **Protocol 준수**: 두 클래스 모두 `split(doc: RawDoc) -> Iterable[RawDoc]`
  시그니처 ✓
- **`source_type` 보존**: 청크가 부모 RawDoc 의 source_type 그대로 유지 ✓
- **`section` 필드 채워짐**: clause 는 "제N조", heading 은 heading text ✓
- **`metadata['chunk_index']`**: 두 splitter 모두 chunk_index 부여하는지 코드
  확인 필요 (테스트로 검증 권장)

## 8. 안 한 것 (의도적)

- **자동 dispatch 매핑** — 결정적으로 opt-in. 추후 `pdf-legal` 같은
  source_type 세분화가 필요하면 그때 추가.
- **chunk_lab UI 의 splitter 옵션 확장** — 현재 `frontend/pages/chunk_lab.py`
  의 selectbox 가 `["recursive", "row"]` 만. clause/heading 추가해야 운영자가
  Lab 에서 비교 가능. 별도 PR.
- **Upload API 의 splitter 선택 UI** — 사용자가 업로드 시 splitter 명시할
  수단 부재. 사규 업로드 시 RecursiveSplitter 가 적용됨 → 추후 metadata 옵션 추가.
- **clause regex 정밀도** — "제 39 조" 띄어쓰기, "제39조의2" 가지조, 영문
  "Article" 다양한 표기 — 한계가 어디까지 잡히는지는 테스트 fixture 확인
  필요 (Codex 가 작성).

## 9. 다음 단계 — chunk_lab 에 클래스 노출

지금 chunk_lab UI 의 splitter 옵션은 `["recursive", "row"]` 만. Phase 4 의
가치를 손에 익히려면 UI 에 clause/heading 추가:

```python
# frontend/pages/chunk_lab.py
splitter_name = st.selectbox(
    "전략", ["recursive", "row", "heading", "clause"],
    help="recursive=길이 / row=표 1행 / heading=md계층 / clause=조항"
)
```

backend `_resolve_splitter` 는 이미 `splitter_by_name` 호출이므로 코드 변경
불필요 — UI selectbox 옵션 한 줄만 늘리면 됨.

---

## 관련 문서

- [ingest_layer.md](ingest_layer.md) — 전체 설계 (분류 1/2/3/4, splitter 전략)
- [ingest_phase3_integration.md](ingest_phase3_integration.md) — dispatch 통합 (Phase 4 가 기반)
- [chunk_testing_page.md](chunk_testing_page.md) — chunk_lab 페이지 설계
- [chunk_lab_page.md](chunk_lab_page.md) — chunk_lab 구현 기록
- [core_concepts.md](core_concepts.md) — 청킹 전략 (B2)
- [work_distribution.md](work_distribution.md) — Codex 가 splitter 알고리즘 담당
