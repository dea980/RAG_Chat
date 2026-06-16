# B2 — seed_test_users 관리 명령

## 한 줄 요약
`auth_dummy_email.md` 의 7 더미 계정을 `python manage.py seed_test_users` 로 idempotent 하게 DB 에 박는 명령.

## 비유
**리허설 무대의 마네킹들.**

연극 리허설을 시작하기 전 배우들 자리에 옷 입은 마네킹을 미리 세워둔다 — 동선·조명·소품 점검용. 진짜 배우가 들어오기 전 무대가 제대로 돌아가는지 확인하기 위해.

`seed_test_users` 도 같은 역할. 진짜 사용자(=프로덕션) 가 들어오기 전 7개 마네킹(=권한·역할 조합) 을 박아 RBAC/ACL 이 제대로 동작하는지 확인. 명령을 두 번 실행해도 마네킹은 7개 그대로 (`get_or_create`) — 무대가 망가지지 않는다.

<div class="analogy">
한 번 박은 마네킹의 권한(role/access_level) 만 바뀌어도 같은 슬롯에서 update — 이게 <strong>idempotent</strong>. 매번 처음부터 다시 깔지 않고 차이만 반영. dev 환경에서 코드를 고치고 다시 실행해도 user_id (PK) 가 그대로 유지된다.
</div>

## 왜 이게 필요한가

| 항목 | 수동 admin 생성 | seed 명령 |
|---|---|---|
| 7 계정 전부 생성 | 7번 클릭, 비밀번호 7번 입력 | 1번 명령 |
| 재현성 | 사람마다 다른 이메일/권한 | 매트릭스가 코드 → 항상 동일 |
| CI/CD 통합 | 불가 | `migrate && seed_test_users` |
| 권한 매트릭스 변경 | 7개 수동 수정 | SEED_USERS 리스트 1줄 수정 |
| prod 사고 방지 | 사람이 실수 가능 | `DEBUG=False` 시 거부 (`--force` 필요) |

## 핵심 코드

```python
# chat/management/commands/seed_test_users.py — 5줄 핵심
for email, role, access_level, dept, is_active in SEED_USERS:
    defaults = {"role": role, "access_level": access_level, ...}
    user, was_created = User.objects.get_or_create(email=email, defaults=defaults)
    user.set_password(PASSWORD)  # idempotent — 매 실행마다 password 갱신
    user.save()
```

- `get_or_create` → 존재하면 fetch, 없으면 INSERT (race-safe)
- `set_password()` → 평문 → pbkdf2 해시
- defaults dict 만 갱신 — `user_id` 등 자동 PK 는 보존

## 데이터 흐름

```
python manage.py seed_test_users
   │
   ▼
Command.handle()
   │ DEBUG 체크 (prod 차단)
   │ Department.get_or_create (Sales/Engineering)
   ▼
for each SEED_USERS row:
   │ User.objects.get_or_create(email=...)
   │ defaults dict 로 role/access_level/dept/is_active 세팅
   │ user.set_password("Triple!23") → 해시
   │ user.save()
   ▼
"seed_test_users: 7 created, 0 updated (total=7)"
```

## 확인 방법

```bash
# 테스트
python manage.py test chat.tests.test_seed_users -v 2
# → Ran 5 tests in 7.8s / OK (5/5)

# dev DB 에 실제 시드
python manage.py seed_test_users
# → seed_test_users: 7 created, 0 updated (total=7)

# 재실행해도 안전
python manage.py seed_test_users
# → seed_test_users: 0 created, 7 updated (total=7)
```

수동 검증:
```bash
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> U = get_user_model()
>>> U.objects.get(email="admin@triplechat.test").access_level
'restricted'
>>> U.objects.get(email="inactive@triplechat.test").is_active
False
```

## 보안 가드 — 왜 DEBUG=False 시 거부하나

prod DB 에 `Triple!23` 비밀번호로 admin 계정이 박히면 24시간 내 침투당함. 자동 시드 명령은:
1. `settings.DEBUG=False` 일 때 `CommandError` 로 abort
2. `--force` 플래그로만 우회 가능 (의식적 행위)
3. CI/test runner 는 `DEBUG=False` 라도 `--force` 로 명시 호출 → 명령어 자체에 의도 박힘

## 연습 문제

1. **새 등급 추가**: SEED_USERS 매트릭스에 `("auditor@triplechat.test", "MANAGER", "confidential", None, True)` 한 줄을 추가하고 `python manage.py seed_test_users` 재실행해보자. 기존 7명은 그대로인가? (힌트: get_or_create.)
2. **비밀번호 강제 변경 시그널**: 첫 로그인 시 강제로 비밀번호를 바꾸게 하려면? User 모델에 `must_change_password = BooleanField(default=True)` 추가하고, seed 명령에서 dummy 계정은 `False` 로 둔다면 prod 시드는 무엇이 다를까? (힌트: dummy 와 prod 시드 분리.)
