# B3 — Login / Logout 엔드포인트

## 한 줄 요약
이메일+비밀번호로 인증 → Django 세션 쿠키 발급 → 이후 모든 요청에 `request.user` 자동 주입.

## 비유
**놀이공원 손목띠.**

매표소(=`/auth/login/`) 에서 표(=이메일+비밀번호) 를 보여주면 손목띠를 채워준다. 그 후엔 놀이기구마다 표를 다시 안 꺼내도 손목띠만 보여주면 통과. 손목띠 = session cookie. 손목띠를 자르면(=`/auth/logout/`) 다시 매표소부터.

<div class="analogy">
손목띠 색깔 = role/access_level (Phase A). 매표소가 비싼 표(=ADMIN) 가족인지 일반 표(=USER) 인지 확인하고 손목띠 색을 정해 채워준다. 이후 놀이기구 입구(=ChatAPIView, MeAPIView)가 손목띠 색만 보면 즉시 통과/차단 결정.
</div>

## 왜 이게 필요한가

| 항목 | 기존 (user_id payload) | 이후 (session cookie) |
|---|---|---|
| 신원 위조 | 누구나 다른 user_id 보내면 통과 | 비밀번호 모르면 세션 못 받음 |
| 매 요청 비용 | DB 에서 user_id lookup | session middleware 캐시 |
| 로그아웃 | 클라이언트가 잊기만 함 | 서버가 session row 삭제 |
| 자동화 | DRF `IsAuthenticated` 안 됨 | DRF 표준 permission 즉시 사용 |
| 다중 디바이스 | 추적 불가 | session row 별 별도 추적 |

## 핵심 코드

```python
# chat/auth_views.py — 5줄 핵심
user = authenticate(request, username=email, password=password)  # pbkdf2 비교
if user is None:
    return Response({"error": "invalid credentials"}, status=401)
login(request, user)        # session 생성 → set-cookie sessionid
return Response(_user_payload(user))  # user_id/role/access_level
```

- `authenticate()` → wrong password OR `is_active=False` 이면 None
- `login()` → `request.session` 에 `_auth_user_id` 박고 cookie 발급
- `logout()` → session row 삭제 + 쿠키 무효화

## 데이터 흐름

```
[client]
   │ POST /api/v1/triple/auth/login/
   │ Content-Type: application/json
   │ {"email": "...", "password": "..."}
   ▼
LoginAPIView.post
   │ authenticate(username=email, password=...)
   │   └ ModelBackend.get_user(email) → User
   │   └ User.check_password(password) → True
   │   └ user.is_active 검사 → True
   ▼
login(request, user)
   │ → Session row 생성 (django_session table)
   │ → Set-Cookie: sessionid=abc123; HttpOnly
   ▼
Response 200 {user_id, email, role, access_level}

  ↓ 이후 요청들 ↓

[client]
   │ POST /api/v1/triple/chat/
   │ Cookie: sessionid=abc123
   ▼
SessionMiddleware → session row 조회 → user_id 추출
   │
   ▼
AuthenticationMiddleware → request.user = User.objects.get(...)
   │
   ▼
[ChatAPIView] request.user.access_level → ACL 필터 (B4)
```

## 확인 방법

```bash
python manage.py test chat.tests.test_auth.LoginEndpointTest -v 2
# → Ran 4 tests / OK (login success, wrong pw 401, inactive 401, logout 204)
```

cURL 수동 확인 (서버 기동 후):
```bash
# 1) login → cookie 저장
curl -c cookies.txt -X POST http://localhost:8000/api/v1/triple/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"email":"user.internal@triplechat.test","password":"Triple!23"}'
# 응답: {"user_id":"U...","role":"USER","access_level":"internal",...}

# 2) me 호출 → cookie 사용
curl -b cookies.txt http://localhost:8000/api/v1/triple/auth/me/
# 응답: 같은 user 정보

# 3) logout
curl -b cookies.txt -X POST http://localhost:8000/api/v1/triple/auth/logout/
# 응답: 204

# 4) me 다시 → 401
curl -b cookies.txt http://localhost:8000/api/v1/triple/auth/me/
```

## 함정 — authenticate() 가 None 반환하는 두 경우

`authenticate()` 내부:
1. user 없거나 비밀번호 불일치 → None
2. `user.is_active == False` → None (Django 4.x ModelBackend 기본 동작)

둘 다 같은 None 으로 묶이므로 에러 메시지를 똑같이 "invalid credentials" 로 통일. **이게 보안 best practice** — "이메일은 맞는데 비밀번호 틀림" vs "이메일 없음" 을 구분해주면 attacker 가 user enumeration 가능.

## 연습 문제

1. **CSRF 보호**: Django session 인증은 기본적으로 CSRF token 을 요구한다. DRF `APIView` 는 어떻게 우회되고 있나? (힌트: `SessionAuthentication` 의 `enforce_csrf` 와 `csrf_exempt` 데코레이터, REST_FRAMEWORK 설정의 DEFAULT_AUTHENTICATION_CLASSES.)
2. **로그인 실패 횟수 제한**: 같은 이메일로 5분 안에 5번 실패하면 잠그려면? `LoginAPIView.post` 어디에 카운터를 박을까? (힌트: Redis incr + TTL, 또는 `django-axes` 라이브러리.)
