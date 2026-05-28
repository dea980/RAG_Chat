# B7 (C1) — 4경계 ForbiddenWord 키워드 필터 연결

## 한 줄 요약
`ForbiddenWord` 규칙이 이미 작동하던 chat **inbound/outbound** 두 경계에 더해, 이번에는 **upload (ingest)** 와 **retrieval** 경계까지 동일한 필터 파이프라인을 통과시키도록 코드를 연결했다. CLAUDE.md 의 4경계 방어가 코드 레벨에서 모두 닫혔다.

## 비유
**아파트 분리수거장 비유.** 한 단지에 들어오고 나가는 쓰레기 흐름이 4개 있다:

| 경계 | 비유 | 흐름 방향 | 이번에 닫힌 곳 |
|---|---|---|---|
| Inbound | 입주민이 분리수거 카드를 단지에 가져옴 | 외부→시스템 | (B5 까지) |
| Outbound | 환경미화원이 차에 실어 외부로 반출 | 시스템→외부 | (B5 까지) |
| Upload  | 새 가구가 트럭으로 들어옴 | 외부→창고 | ✅ B7 |
| Retrieval | 창고에서 꺼내 입주민에게 전달 | 창고→내부 | ✅ B7 |

전에는 입구·출구만 검색대였는데, 창고로 들어가는 트럭(=업로드)과 창고에서 꺼내는 손수레(=검색)는 무검색으로 통과했다. 이번에 같은 검색대 규칙(=`ForbiddenWord`)을 4개 경계 모두에 박았다.

<div class="analogy">
한 가지 규정(= "대외비" 같은 키워드)을 4 곳에서 다 검사하지만 <b>방향성</b>이 있다. <code>direction=INBOUND</code> 는 "들어오는 쪽" 만 (chat 질문 + upload), <code>direction=OUTBOUND</code> 는 "나가는 쪽" 만 (chat 답변 + retrieval). <code>BOTH</code> 는 4 경계 모두. <code>filter._directions_for(source)</code> 한 매핑이 이걸 한 곳에 모은다.
</div>

## 왜 이게 필요한가

| 시나리오 | 4경계 안 막혔을 때 | B7 후 |
|---|---|---|
| 영업팀원이 "대외비.pdf" 업로드 | 그대로 벡터화 → 다른 사원이 RAG 로 조회 가능 | upload 시점에 BLOCK → 인덱싱 안 됨, 감사 로그 1건 |
| 운영자가 BLOCK 키워드를 사후 추가 | 이미 인덱싱된 청크가 retrieval 로 나가버림 | retrieval 시점에 또 BLOCK → 청크 드롭 + redacted_count++ |
| 부서별 마스킹 정책 변경 | 재인덱싱 필요 | retrieval 의 MASK 가 즉시 반영, 청크 데이터는 그대로 |
| 4경계 별도 운영자 추적 | source 칼럼이 INBOUND/OUTBOUND 뿐 → 어디서 새는지 모름 | `Source.UPLOAD/RETRIEVAL` 분리 → 감사 인사이트 |

핵심: **방어선이 한 곳뿐이면 그 한 곳이 뚫리는 순간 끝난다.** 다중 경계는 한 곳에서 운영자가 규칙을 잠시 잘못 푼다 해도 다른 경계에서 잡힐 여지를 둔다.

## 핵심 코드

```python
# moderation/filter.py — 새로 추가된 매핑 한 곳
_SOURCE_TO_DIRECTIONS = {
    "INBOUND":   ("BOTH", "INBOUND"),
    "UPLOAD":    ("BOTH", "INBOUND"),   # 업로드는 들어오는 텍스트
    "OUTBOUND":  ("BOTH", "OUTBOUND"),
    "RETRIEVAL": ("BOTH", "OUTBOUND"),  # 검색결과는 사용자에게 나가는 텍스트
}
def _directions_for(source): return _SOURCE_TO_DIRECTIONS.get(source, ("BOTH", "OUTBOUND"))
```

```python
# chat/utils.py — retrieval 경계 (process_search_results 안)
for doc in kept_acl:
    try:
        mod = moderate_text(doc.page_content, source=ModerationLog.Source.RETRIEVAL)
    except BlockedByModerationError:
        redacted_count += 1       # BLOCK 청크는 드롭, redacted ribbon 으로 사용자에게 표시
        continue
    if mod.sanitized != doc.page_content:
        doc.page_content = mod.sanitized  # MASK 는 그 자리에서 치환
    kept.append(doc)
```

```python
# chat/ingest/pipeline.py — upload 경계 (loader.load 직후, splitter 호출 전)
for d in raw_docs:
    try:
        mod = moderate_text(d.content, source=_ML.Source.UPLOAD)
    except BlockedByModerationError:
        logger.info(f"upload-block: dropped doc from {d.source_file}")
        continue                  # BLOCK 문서는 청킹·인덱싱 자체를 안 함
    if mod.sanitized != d.content:
        d.content = mod.sanitized
    filtered.append(d)
```

세 곳 모두 동일한 패턴: `try → BlockedByModerationError → 드롭`, `MASK → 본문 치환`, `WARN → log only`. 한 머리(=filter.apply)에 네 손이 붙은 형태.

## 데이터 흐름 (4 경계 전체)

```
┌───────────── INBOUND ─────────────┐         ┌────────── OUTBOUND ──────────┐
│ chat/views.py:135                  │         │ chat/views.py:199             │
│   moderate_text(question, INBOUND) │         │   moderate_text(resp, OUTBOUND)
└────────────┬───────────────────────┘         └─────────────┬─────────────────┘
             │ sanitized question                            ▲ sanitized response
             ▼                                               │
   ┌──────────────────────┐    retrieval     ┌───────────────┴───────────┐
   │ pipeline.run(context)│ ───────────────▶ │ chat/utils.py:166         │
   └──────────┬───────────┘                  │   ACL filter + keyword scan
              ▲                              │   moderate_text(chunk, RETRIEVAL)
              │ context_text                 └────────────────┬──────────┘
              │                                               │
              │                                               ▼
        ┌─────┴────────┐  upload   ┌──────────────────────────────────────┐
        │ vector_store │ ◀───────  │ chat/ingest/pipeline.py:103          │
        └──────────────┘           │   moderate_text(raw_doc, UPLOAD)     │
                                   └──────────────────────────────────────┘

모든 경계 → 같은 ForbiddenWord 테이블 → `direction` 으로 자동 라우팅 → ModerationLog 에 source 별 기록
```

## 확인 방법

```bash
cd Rag_Chat/backend

# C1.1 — Source enum + direction 매핑
venv/bin/python manage.py test moderation.tests.test_filter_sources -v 1
# → 7/7 OK

# C1.2 — retrieval 경계
venv/bin/python manage.py test moderation.tests.test_retrieval_keyword_filter -v 1
# → 5/5 OK

# C1.3 — upload 경계
venv/bin/python manage.py test moderation.tests.test_upload_keyword_filter -v 1
# → 4/4 OK

# 회귀 — 50 moderation + 16 chat 인증 통과
venv/bin/python manage.py test chat.tests.test_auth chat.tests.test_chat_auth_gate moderation -v 1
# → 66/66 OK
```

수동 확인:

```bash
# 1) ADMIN 으로 로그인 후 BLOCK rule 추가
curl -c /tmp/a.jar -X POST http://localhost:8000/api/v1/triple/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin.root@triplechat.test","password":"Triple!23"}'
curl -b /tmp/a.jar -X POST http://localhost:8000/api/v1/triple/moderation/rules/ \
  -H 'Content-Type: application/json' \
  -d '{"word":"대외비","severity":"BLOCK","direction":"BOTH","category":"기밀"}'

# 2) 이제 upload 시 "대외비" 포함 문서 → 스킵 (logger.info)
#    retrieval 시 이미 인덱싱된 청크에 "대외비" 있으면 → 드롭 + redacted_count
#    chat 시 질문/응답에 있으면 → 403 / sanitized
```

## 함정 — `RawDoc.content` mutability

`RawDoc` 은 `@dataclass` (frozen=False). 업로드 boundary 에서 `d.content = mod.sanitized` 로 직접 덮어쓰는데, dataclass 의 기본은 mutable 이라 작동한다. 만약 미래에 `@dataclass(frozen=True)` 로 굳히게 되면, 여기 라인이 immutable 에러로 깨질 거다. 그땐 `replace(d, content=mod.sanitized)` 로 바꿔야 한다.

## 함정 — chat/utils.py 의 List import

`kept: List = []` 라인은 `typing.List` 를 쓴다. `from typing import Dict, Any, List, Optional, Union` 이 이미 파일 상단에 있으므로 신규 import 불필요. 모르고 새 모듈에 옮길 때 누락 주의.

## 함정 — ACL 가 먼저, 키워드가 나중

`process_search_results` 는 **순서가 중요하다**:
1. `apply_acl_filter` 로 sensitivity 초과 청크 제거 (redacted_count = ACL drops)
2. 남은 청크에 키워드 스캔 → BLOCK 이면 redacted_count++ (같은 카운터)

만약 순서를 뒤집으면, sensitivity=restricted 청크에 키워드 스캔이 먼저 일어나서 로그가 두 번 쌓이거나 (drop 사유가 헷갈리는) 문제. 1→2 순서 유지가 핵심.

## 연습 문제

1. **regex 패턴 지원**: `ForbiddenWord.word` 가 정규식이면 (예: `\d{6}-\d{7}` 주민번호) 어떻게 확장할까? 힌트: `Severity` 처럼 `Kind` (`LITERAL`/`REGEX`) 칼럼 추가 + `_find_matches` 에 `re.finditer` 분기. 마이그레이션 한 개 + 테스트 두 개면 충분.

2. **임베딩 유사도 기반 필터**: 정확 매칭으로는 "대외비"는 잡지만 "기밀 사항"은 못 잡는다. retrieval 경계에서 chunk embedding 과 "기밀 패턴" embedding 의 코사인 유사도가 임계치 이상이면 드롭하려면? 힌트: 이건 새 모델(예: `EmbeddingRule(threshold, pattern_text)`) + retrieval 시점에 같은 임베더로 계산. 작업량 ↑.

3. **upload 거부 응답 표면화**: 현재 BLOCK 된 raw_doc 은 `logger.info` 만 남고 사용자에게는 "ingested 0 chunks" 로 보임. 운영자에게 "이 파일은 키워드 차단" 이라고 명확히 전달하려면 `ingest_path` 가 어떤 반환값을 더 줘야 할까? 힌트: 단순 int 대신 dataclass `IngestSummary(count, blocked_docs, masked_docs)` 로 확장.
