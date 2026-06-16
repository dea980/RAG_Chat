# B4 — ChatAPIView 인증 게이트 + request.user 사용

## 한 줄 요약
`ChatAPIView` 가 세션 인증을 요구하고, user 신원과 `access_level` 을 `request.user` 에서 읽도록 변경 — Phase A ACL 이 비로소 진짜 보안이 된다.

## 비유
**도서관 출입 카드 리더.**

이전엔 출입구에 종이쪽지에 본인 이름 적어 내는 방식이었다 (`{"user_id": "U..."}`). 누구든 다른 사람 이름 적고 그 사람 권한으로 검색 가능. 출입증 색깔(=access_level) 이 빨강(=restricted) 이라 적으면 통과.

B4 후엔 카드 리더가 출입구에 박혔다. 카드(=session cookie) 없으면 입구에서 차단 (`403`). 카드 있는 사람의 정보는 리더가 직접 DB 에서 읽어옴 — 누구도 다른 사람으로 위장 못 함.

<div class="tip">
출입증 색깔 검사(ACL/Phase A)와 카드 리더(인증/B4)는 다른 층이다. 색깔만 검사하고 카드는 안 보면 — Phase A 가 했던 일은 보안 환상. B4 가 실질적 보안 경계를 박는 곳.
</div>

## 왜 이게 필요한가

| 항목 | 이전 (payload user_id) | 이후 (request.user) |
|---|---|---|
| 신원 출처 | client → JSON | server → session row |
| 권한 위조 | `{"user_id": "<admin's id>"}` | 비밀번호 모르면 불가 |
| 익명 접근 | 가능 (user_id 만 알면) | `403` |
| 표준 미들웨어 | 안 됨 | DRF `IsAuthenticated` 즉시 |
| audit trail | client 가 적은 user_id | session 의 실제 인증 user |

## 핵심 코드

```python
# chat/views.py — 5줄 핵심 변경
class ChatAPIView(APIView):
    permission_classes = [IsAuthenticated]  # ← 추가, 핵심 보안 경계

    def post(self, request):
        user_obj = request.user             # session → User
        user_id = user_obj.user_id          # 클라이언트 payload 무시
        # ... user_obj.access_level 이 ModuleContext 로 전달
```

- `permission_classes` → 미인증 요청은 view 진입 전 `403`
- `request.user` → `AuthenticationMiddleware` 가 session 으로 채워줌
- 기존 `request.data.get('user_id')` 줄을 통째로 제거 → escalation 표면 차단

## 데이터 흐름 (B1~B4 종합)

```
[로그인]
   POST /api/v1/triple/auth/login/  {email, password}
       │ authenticate → User
       │ login(request, user) → Session row + Set-Cookie
       ▼
   200 {user_id, role, access_level}

[질의]
   POST /api/v1/triple/chat/  {question}   ← user_id 안 보냄
       │ Cookie: sessionid=...
       ▼
   SessionMiddleware → session 조회 → user PK 얻음
       ▼
   AuthenticationMiddleware → request.user = User.objects.get(...)
       ▼
   IsAuthenticated.has_permission → request.user.is_authenticated
       │ False → 403 (anonymous 차단)
       │ True  → view 진입
       ▼
   ChatAPIView.post
       user_obj = request.user            ← 세션이 진실의 원천
       ModuleContext(user_access_level=user_obj.access_level)
       ▼
   RetrieveModule → apply_acl_filter (Phase A) → redacted_count
       ▼
   Response 200 {response, redacted_count}
```

## 확인 방법

```bash
# 단위 + 통합 + Phase A 회귀
python manage.py test chat.tests.test_chat_auth_gate chat.tests.test_auth \
    chat.tests.test_seed_users moderation -v 1
# → Ran 36 tests / OK
```

수동:
```bash
# 1) 익명으로 chat 호출 → 차단
curl -X POST http://localhost:8000/api/v1/triple/chat/ \
     -H "Content-Type: application/json" \
     -d '{"question":"M&A 자료"}'
# 응답: 403 Forbidden

# 2) 로그인 후 다시
curl -c cookies.txt -X POST http://localhost:8000/api/v1/triple/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email":"user.internal@triplechat.test","password":"Triple!23"}'

curl -b cookies.txt -X POST http://localhost:8000/api/v1/triple/chat/ \
     -H "Content-Type: application/json" \
     -d '{"question":"M&A 자료","user_id":"U00000000000"}'  # 위조 시도
# 응답: 200, redacted_count > 0 (internal 권한이라 confidential chunk 가려짐)
# user_id 위조는 무시되고 session 의 user.internal 권한으로 처리됨
```

## 함정 — 401 vs 403

DRF 가 `IsAuthenticated` 실패 시 반환하는 코드:
- **401 Unauthorized** — `WWW-Authenticate` 헤더가 있는 auth class (TokenAuthentication 등) 가 등록되어 있을 때
- **403 Forbidden** — 그 외 (SessionAuthentication 만 있을 때)

표준 HTTP 의미상 401="너 누구야 모름", 403="아는데 권한 부족" 이지만, DRF 는 단순히 위 규칙을 따른다. 둘 다 "인증 안 됨" 신호로 받아들이는 게 실무.

## 다른 endpoint 는?

`ChatUserAPIView`, `UpdateActivityAPIView`, `MetaDataAPIView` 등 다른 views 에는 아직 `IsAuthenticated` 미적용. Phase 다음 작업으로 분리 — chat 만 해도 RAG 메인 표면은 막힘.

## 연습 문제

1. **다른 endpoint 도 막기**: `views.py:ChatRagAPIView`, `MetaDataAPIView` 에도 `permission_classes = [IsAuthenticated]` 를 박으면? 어떤 사이드 이펙트? (힌트: 헬스체크 `/health/` 는 익명이어야 함. `AllowAny` 명시.)
2. **role 기반 게이트**: `MeAPIView` 는 누구나 자기 정보 보면 되지만, moderation rule 편집 endpoint 는 `ADMIN` 만 가능해야 한다. DRF custom permission `IsModerationAdmin` 을 어디에 두고 어떻게 작성하나? (힌트: `rest_framework.permissions.BasePermission`, `has_permission(self, request, view)` 안에서 `request.user.role == "ADMIN"` 검사.)
