# ACL 필터 전체 배선 — 모든 retrieval 경로에 user_access_level 전달하기

## 한 줄 요약

RAG 검색 결과를 사용자에게 돌려주기 전에, **사용자의 접근 등급(access_level)과 문서의 민감도(sensitivity)를 비교**해서 볼 수 없는 chunk를 걸러내는 ACL 필터를 모든 호출 경로에 연결한 작업.

## 비유 — 도서관 열람 카드

도서관에 가면 책마다 색띠가 붙어있다고 상상해보자:

| 색띠 | 의미 | 숫자 등급 |
|------|------|-----------|
| 흰색 | 공개 (public) | 0 |
| 파랑 | 사내 공유 (internal) | 1 |
| 노랑 | 대외비 (confidential) | 2 |
| 빨강 | 기밀 (restricted) | 3 |

- **열람 카드** = `User.access_level` — 네가 열어볼 수 있는 최대 색띠
- **책의 색띠** = chunk metadata의 `sensitivity` — 이 문서가 얼마나 민감한지

**규칙은 딱 한 줄**: 내 카드 숫자 >= 책 색띠 숫자 → 열람 가능.

신입사원(카드=파랑=1)이 검색하면, 노랑(2)과 빨강(3) 책은 결과에서 빠진다. 대신 "2건이 권한 밖이라 가려졌습니다"라는 메시지가 나온다 — 이게 `redacted_count`.

## 왜 이게 필요한가

| | 변경 전 | 변경 후 |
|---|---------|---------|
| **검색 함수** | `get_rag_context(question)` — 누가 물어보든 같은 결과 | `get_rag_context(question, user_access_level="internal")` — 사용자 등급에 따라 필터링 |
| **민감 문서 노출** | 신입이 기밀 chunk도 볼 수 있음 | 등급 미달 chunk는 자동 제거 |
| **사용자 인지** | 결과가 왜 적은지 모름 | `redacted_count`로 "N건 가려짐" 표시 |
| **test endpoint** | ACL 없이 raw 결과 반환 | 동일 ACL 적용 |

## 핵심 코드

필터의 핵심은 `moderation/levels.py`의 이 함수 하나:

```python
# moderation/levels.py:28-30
SENSITIVITY_LEVEL = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}

def can_access(user_level: str, content_level: str) -> bool:
    """사용자 등급 숫자 >= 문서 등급 숫자면 True"""
    return SENSITIVITY_LEVEL[user_level] >= SENSITIVITY_LEVEL[content_level]
```

- `SENSITIVITY_LEVEL` — 문자열 등급을 숫자로 변환하는 사전. 숫자가 클수록 높은 권한.
- `user_level` — 요청한 사용자의 접근 등급 (User 모델의 `access_level` 필드)
- `content_level` — chunk metadata에 박힌 민감도 라벨
- 비교 한 줄 (`>=`)로 "이 사용자가 이 문서를 볼 수 있는가?" 판정 끝.

## 데이터 흐름

```
사용자 요청 (POST /api/chat/)
    │
    ▼
views.py ── user_obj = User.objects.filter(user_id=...).first()
    │         user_access_level = user_obj.access_level  (없으면 "internal")
    │
    ▼
ModuleContext(user_access_level=...)      ← base.py
    │
    ▼
RetrieveModule.run()                      ← modules.py
    │  RAGUtils.get_rag_context(
    │      question,
    │      user_access_level=context.user_access_level  ← 여기서 전달!
    │  )
    ▼
RAGUtils.get_rag_context()                ← utils.py
    │  vector_store.similarity_search(question, k=20)
    │  RAGUtils.process_search_results(results, user_access_level)
    ▼
RAGUtils.process_search_results()         ← utils.py
    │  apply_acl_filter(results, user_access_level)
    ▼
apply_acl_filter()                        ← moderation/levels.py
    │  각 chunk의 metadata["sensitivity"] vs user_level 비교
    │  → kept (통과), redacted_count (걸러진 수)
    ▼
응답: { response, images, redacted_count }
```

**이번 작업에서 추가 배선한 경로들:**

```
views.py:43        get_rag_context() 레거시 래퍼 ─── user_access_level 파라미터 추가
views.py:520       _test_similarity_search() ─────── 명시적 "internal" 전달
vector_metadata.py enhance_vector_search() ────────── user_access_level 시그니처 추가 + forward
ingest/pipeline.py ingest_paths() ─────────────────── sensitivity forward to ingest_path()
```

## 확인 방법

```bash
# backend 디렉토리에서 실행
cd Rag_Chat/backend

# ACL 단위 테스트 15개 실행
DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings python3 -m pytest moderation/tests/test_acl.py -v

# 기대 결과: 15 passed
```

테스트가 검증하는 것:
- `internal` 사용자 → `confidential` chunk 차단됨
- `restricted` 사용자 → 모든 chunk 통과
- `public` 사용자 → `public` chunk만 통과
- metadata에 `sensitivity` 키 없는 옛 chunk → `internal`로 간주
- `redacted_count`가 정확히 걸러진 수와 일치

## 연습 문제

### 연습 1: 새 등급 추가해보기

"top-secret" (등급 4)을 추가하려면 어디를 고쳐야 할까?

**힌트**: `moderation/levels.py`의 `SENSITIVITY_LEVEL` dict에 한 줄 추가하면 `can_access`와 `apply_acl_filter`가 자동으로 작동한다. 하지만 User 모델의 `access_level` choices와 knowledge 모델의 `Sensitivity` choices에도 추가해야 DB에 저장 가능.

### 연습 2: 빠진 호출처 찾기

아래 명령으로 `process_search_results`를 호출하는 곳을 전부 찾아보자:

```bash
grep -rn "process_search_results" --include="*.py" Rag_Chat/backend/
```

각 호출처에 `user_access_level`이 전달되고 있는지 확인하고, 빠진 곳이 있으면 고쳐보자. (힌트: 테스트 파일의 호출은 테스트 목적이라 default "internal"이 맞을 수 있다.)
