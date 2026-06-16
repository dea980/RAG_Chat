# B1 — chat.User 를 AbstractBaseUser 로 마이그레이션

## 한 줄 요약
Django 의 표준 인증 시스템에 우리 `User` 모델을 끼워 넣어 비밀번호·세션·로그인 기능을 무료로 받기.

## 비유
**호텔 객실 키 vs 사진 박힌 출입증.**

이전 `chat.User` 는 호텔 객실 키 같았다 — `user_id=U0123...` 라고 적힌 종이만 들고 가면 누구든 그 방에 들어갈 수 있다. 키 자체가 신원 증명이 아니라 단순 식별자일 뿐.

`AbstractBaseUser` 로 바꾼 후엔 **사진 박힌 출입증 + 비밀번호** 다. 누군가 user_id 를 알아내도 비밀번호 모르면 못 들어간다. Django 가 출입증 검사(=`authenticate`), 잠금장치(=session), 로그(=`last_login`) 를 전부 표준으로 제공한다.

<div class="analogy">
열쇠를 흉내내는 것 = identifier. 사진 + 비밀번호 = authentication. Phase A 의 ACL 은 "이 사람이 어디까지 들어갈 수 있나" 의 출입증 색깔(=access_level) 인데, 사진(=인증)이 없으면 색만 봐도 의미가 없다. 누가 그 출입증을 들고 있는지 알 수 없으니까.
</div>

## 왜 이게 필요한가

| 항목 | 이전 (Plain Model) | 이후 (AbstractBaseUser) |
|---|---|---|
| 신원 검증 | client 가 `user_id` 평문 전달 → 위조 가능 | `authenticate(email, password)` → 해시 비교 |
| 비밀번호 저장 | 없음 | pbkdf2 해시 자동 |
| 세션 관리 | 직접 구현 필요 | Django session middleware 자동 |
| 로그인 시각 | `last_activity` 만 직접 갱신 | `last_login` Django 가 자동 |
| 권한 mixin | 없음 | `PermissionsMixin` → `groups`/`user_permissions` |
| DRF 연동 | 별도 wiring | `request.user`, `IsAuthenticated` 즉시 사용 |

키 포인트: **이전 코드도 ACL/access_level 비교는 정확히 동작했지만, "누구냐" 가 위조 가능했다.** 인증이 빠지면 권한 비교는 보안 환상.

## 핵심 코드

```python
# chat/models.py — 5줄 핵심
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)   # USERNAME_FIELD 로 사용
    is_active = models.BooleanField(default=True)
    USERNAME_FIELD = "email"                 # 로그인 시 이메일로 식별
    objects = UserManager()                  # create_user / create_superuser
```

- `AbstractBaseUser` → `password`, `last_login`, `check_password()`, `set_password()` 무료
- `PermissionsMixin` → `is_superuser`, `groups`, `has_perm()` 무료
- `email = unique=True` → `USERNAME_FIELD` 이 되려면 unique 필수
- `UserManager` → `set_password(password)` 를 자동 호출하는 헬퍼
- `settings.AUTH_USER_MODEL = "chat.User"` → 전 프로젝트가 이 User 를 인식

## 데이터 흐름

```
[client]
   │ POST /api/v1/auth/login/ {email, password}
   ▼
authenticate(email, password)
   │ User.objects.get(email=...)  → user 객체
   │ user.check_password(password)  → True/False (해시 비교)
   ▼
session 생성 → 쿠키 sessionid 반환
   │
   │ 이후 모든 request 에 sessionid 쿠키 동봉
   ▼
SessionMiddleware → request.user 주입
   │
   ▼
[ChatAPIView]  request.user.access_level → ACL 필터
```

## 확인 방법

```bash
cd Rag_Chat/backend
source venv/bin/activate
python manage.py test chat.tests.test_auth.UserModelContractTest -v 2
# → Ran 9 tests in 1.7s / OK
```

수동 확인:
```bash
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> u = User.objects.create_user(email="test@triplechat.test", password="Triple!23")
>>> u.check_password("Triple!23")   # True
>>> u.check_password("wrong")        # False
>>> u.password[:7]                   # 'pbkdf2_'
```

## 트러블슈팅 노트

makemigrations 실행 시 `EOFError: input()` 만나면 → 기존 row 에 password 컬럼 채울 default 가 없어서 Django 가 대화형으로 물어보는데 비-tty 환경이라 실패한 것. dev DB 이라 `db.sqlite3` 백업 후 삭제 + `printf "1\n''\n" | makemigrations` 로 빈 문자열 default 답변.

prod 에선 데이터 마이그레이션 작성:
```python
def set_unusable_passwords(apps, _):
    User = apps.get_model("chat", "User")
    for u in User.objects.all():
        u.set_unusable_password()
        u.save(update_fields=["password"])
```

## 연습 문제

1. **USERNAME_FIELD 를 email 대신 user_id 로 바꾸면?** `chat/models.py` 의 `USERNAME_FIELD = "email"` 을 `"user_id"` 로 바꾸고 테스트를 실행해보자. 무엇이 깨지나? (힌트: `User.objects.create_user()` 의 첫 인자가 user_id 가 되어, 자동 생성 로직과 충돌. UX 도 박살 — 사용자가 `U01230001 4567` 을 외워야 함.)
2. **password 만 가져가는 새 BaseUserManager 메서드 추가**: `create_inactive_user(email)` — 비밀번호 없이 user 만 생성하고 `set_unusable_password()` 호출. 사용 케이스는? (힌트: SSO 외부 인증을 우선 쓰고 자체 로그인은 막을 때.)
