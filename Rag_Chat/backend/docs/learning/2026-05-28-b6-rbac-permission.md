# B6 — RBAC custom permission (`IsModerationAdmin` / `IsManager`)

## 한 줄 요약
DRF `BasePermission` 두 개 — ADMIN 만 통과시키는 `IsModerationAdmin`, MANAGER 이상 통과시키는 `IsManager` — 를 추가하고 `/api/v1/triple/moderation/rules/` (rule CRUD) 와 `/logs/` (감사 read-only) 에 붙여, "관리자가 코드 없이 튜닝" 을 실제로 강제했다.

## 비유
**아파트 출입증 vs 관리실 열쇠.**

- 모든 입주민(=USER)은 출입증으로 단지에 들어올 수 있다 — `IsAuthenticated` (B4).
- 동대표(=MANAGER)는 관리비 영수증·CCTV 로그를 볼 수 있다 — `IsManager`.
- 관리사무소장(=ADMIN)만 출입통제 규정 자체를 바꾼다 — `IsModerationAdmin`.

같은 건물이지만 "들어올 수 있는가" 와 "규정을 바꿀 수 있는가" 는 완전히 다른 권한. DRF 의 permission_classes 는 이 두 검사를 따로 적용한다.

<div class="analogy">
ADMIN 은 MANAGER 가 할 수 있는 모든 것을 할 수 있어야 한다 (위계 = 상속). 그래서 <code>IsManager</code> 가 ADMIN+MANAGER 둘 다 허용하도록 set 으로 비교한다 — 매번 if 분기를 늘리지 않기 위한 작은 디자인 선택.
</div>

## 왜 이게 필요한가

| 항목 | 이전 (B1~B5) | 이후 (B6) |
|---|---|---|
| 인증 | `IsAuthenticated` 만 — 누구나 로그인하면 통과 | `IsAuthenticated` + role 기반 |
| Rule 수정 권한 | 코드 한 줄도 없음 | ADMIN 만 (`IsModerationAdmin`) |
| 감사 로그 열람 | 없음 | MANAGER 이상 (`IsManager`) |
| 권한 위반 시 | 403 + `permission_denied` (기본 메시지) | 403 + 한국어 사유 (`message` 속성) |
| 비활성 사용자 | 인증만 막힘 (is_authenticated=False) | role 가져도 `is_active=False` 면 거부 |

CLAUDE.md 의 핵심 요구사항 — **운영자가 코드 없이 튜닝** — 은 단순히 admin UI 가 있는 것만으로는 부족하다. 그 UI 의 backend API 자체가 평사원에게 막혀있어야 한다. B6 는 그 게이트.

## 핵심 코드

```python
# moderation/permissions.py — 5줄 핵심
def _has_role(request, allowed: set[str]) -> bool:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_active:
        return False                                # ① 익명 / 비활성 거부
    return getattr(user, "role", None) in allowed   # ② 역할 set 매칭

class IsModerationAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        return _has_role(request, {User.Role.ADMIN})           # ADMIN 만
class IsManager(BasePermission):
    def has_permission(self, request, view) -> bool:
        return _has_role(request, {User.Role.ADMIN, User.Role.MANAGER})  # ADMIN ⊇ MANAGER
```

- ① 인증·활성 게이트를 **헬퍼 한 곳**에 모음 → 두 클래스가 같은 규칙으로 작동
- ② set 비교 — 위계 확장 시 새 set 만들면 끝 (예: `IsAuditor = {ADMIN, MANAGER, AUDITOR}`)

```python
# moderation/views.py — viewset 에 정확한 한 줄로 적용
class ForbiddenWordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsModerationAdmin]  # AND 결합

class ModerationLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsManager]
```

DRF 는 `permission_classes` 의 모든 항목이 True 일 때만 통과 (논리 AND). `IsAuthenticated` 는 익명 거부 + sessionid 검증, custom permission 은 role 검증 — 책임을 쪼개서 누가 봐도 의도가 보이도록.

## 데이터 흐름

```
[브라우저] POST /api/v1/triple/moderation/rules/
   Cookie: sessionid=...
        ▼
[Django session middleware]
   request.user = User(...)  ← B3
        ▼
[DRF View dispatch]
   permission_classes 순회:
     1) IsAuthenticated.has_permission(req, view)
        - user.is_authenticated 인가? → True
     2) IsModerationAdmin.has_permission(req, view)
        - user.is_active 인가? → True
        - user.role == "ADMIN" 인가? → ?
              │
              ├─ True  → ViewSet.create() 실행 → 201
              └─ False → 403 + "운영자 권한 (ADMIN) 이 필요합니다."
```

`MeAPIView`/`LoginAPIView` 가 만들어두는 sessionid 가 모든 후속 호출을 자동 인증한다는 점은 B3·B4 에서 이미 다뤘다. B6 는 그 위에 "권한 분리" 한 겹을 더한다.

## 확인 방법

```bash
# 단위 테스트
cd Rag_Chat/backend
venv/bin/python manage.py test moderation.tests.test_permissions -v 2
# 10/10 OK

# 통합 테스트 (실제 endpoint round-trip)
venv/bin/python manage.py test moderation.tests.test_rules_endpoint -v 2
# 9/9 OK
```

수동 확인 (서버 실행 후):

```bash
# 1) 일반 사용자 로그인 → rule 열람 거부
curl -c /tmp/u.jar -X POST http://localhost:8000/api/v1/triple/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"user.internal@triplechat.test","password":"Triple!23"}'
curl -b /tmp/u.jar http://localhost:8000/api/v1/triple/moderation/rules/
# → {"detail":"운영자 권한 (ADMIN) 이 필요합니다."}  HTTP 403

# 2) 운영자 로그인 → rule 생성 성공
curl -c /tmp/a.jar -X POST http://localhost:8000/api/v1/triple/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@triplechat.test","password":"Triple!23"}'
curl -b /tmp/a.jar -X POST http://localhost:8000/api/v1/triple/moderation/rules/ \
  -H 'Content-Type: application/json' \
  -d '{"word":"대외비","category":"기밀","severity":"BLOCK"}'
# → 201 Created
```

## 함정 — `IsAuthenticated` 만 쓰면 보안 극장

B1~B5 까지는 `IsAuthenticated` 만으로 충분히 안전해 보였다. 하지만 **로그인만 한 사용자는 자기 역할을 알 수 있다 — 그리고 그 역할이 ADMIN 이 아닌데도 같은 endpoint 에 접근할 수 있다면** "관리자 전용 UI" 는 클라이언트 측 가림막에 불과하다.

permission_classes 에 `IsModerationAdmin` 을 끼우지 않으면, Streamlit 사이드바에서 admin 메뉴를 숨기는 정도가 전부. curl 한 줄이면 우회. B6 는 backend 에서 강제하는 게이트 = single source of truth.

## 연습 문제

1. **새 권한 클래스 추가**: 부서 책임자(`DEPARTMENT_LEAD`) 역할이 추가됐다고 가정. `IsDepartmentLead` 를 만들고 `IsManager` 가 ADMIN/MANAGER/DEPARTMENT_LEAD 모두 통과시키도록 확장하라. 힌트: `chat.models.User.Role` 에 새 choice 추가 + permissions.py 의 set 두 줄 수정 + 마이그레이션 1개.

2. **object-level 권한**: 부서장이 *자기 부서* 사용자의 ModerationLog 만 보게 하려면? 힌트: `IsManager` 에 `has_object_permission(self, request, view, obj)` 를 추가 → `obj.user.department_id == request.user.department_id` 일 때만 True. ViewSet 의 `get_queryset` 도 같이 좁혀야 list endpoint 가 안 새어나간다.

3. **로그 좁히기 보너스**: ADMIN 은 전체 로그, MANAGER 는 자기 부서 로그만 보도록 `ModerationLogViewSet.get_queryset()` 을 한 줄로 바꿔보라. (`if request.user.role == User.Role.ADMIN: return qs; return qs.filter(user__department=request.user.department)`.)
