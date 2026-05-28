# Auth — Dummy Test Users

> 인증 + RBAC + Phase A ACL 검증용 더미 계정. **dev/test 환경 전용** — prod 시드에 절대 포함 금지.
> 비밀번호는 모두 `Triple!23` (12자 미만이지만 dev 한정). 운영자가 첫 로그인 시 강제 변경 시그널은 Phase 후순위.

## 빠른 복붙 (cheatsheet)

```
# 비밀번호 (전 계정 공통)
Triple!23

# 이메일 7개
user.public@triplechat.test          # USER / public
user.internal@triplechat.test        # USER / internal  ← 평사원 기본
manager.sales@triplechat.test        # MANAGER / confidential (Sales)
manager.eng@triplechat.test          # MANAGER / confidential (Engineering)
admin@triplechat.test                # ADMIN / restricted
moderation.admin@triplechat.test     # ADMIN / restricted (mod rule 편집용)
inactive@triplechat.test             # USER / internal, is_active=False
```

## 매트릭스

| email | password | role | access_level | department | 용도 |
|---|---|---|---|---|---|
| `user.public@triplechat.test` | `Triple!23` | USER | public | (없음) | 외부 협력사 시나리오 — public chunk 만 보여야 |
| `user.internal@triplechat.test` | `Triple!23` | USER | internal | Sales | 평사원 기본 — public+internal 까지 |
| `manager.sales@triplechat.test` | `Triple!23` | MANAGER | confidential | Sales | 부서장 — confidential 까지 |
| `manager.eng@triplechat.test` | `Triple!23` | MANAGER | confidential | Engineering | 부서 분리 RBAC 검증용 |
| `admin@triplechat.test` | `Triple!23` | ADMIN | restricted | (없음) | C-level — restricted 까지 전부 |
| `moderation.admin@triplechat.test` | `Triple!23` | ADMIN | restricted | (없음) | moderation rule 편집 권한 검증 |
| `inactive@triplechat.test` | `Triple!23` | USER | internal | Sales | `is_active=False` — 로그인 거부 검증 |

## role → access_level 매핑 규칙 (RBAC Phase)

```
USER     → internal       (기본 사내 직원)
MANAGER  → confidential   (부서장)
ADMIN    → restricted     (C-level)
```

위 매트릭스의 `user.public@triplechat.test` 는 매핑 규칙 예외 (외부 협력사). 운영자가 직접 access_level 을 override 한 케이스.

## 검증 시나리오

| 시나리오 | 입력 | 기대 출력 |
|---|---|---|
| 평사원이 대외비 자료 검색 | login `user.internal`, query "M&A" | 200 OK, `redacted_count >= 1`, confidential chunk 빠짐 |
| 부서장이 같은 검색 | login `manager.sales`, query "M&A" | 200 OK, `redacted_count == 0`, confidential 통과 |
| 외부 협력사가 사내 자료 검색 | login `user.public`, query "내부 정책" | 200 OK, `redacted_count >= 1`, internal chunk 빠짐 |
| 비활성 계정 로그인 시도 | login `inactive` | 401 또는 403 |
| 인증 없이 chat 호출 | POST /api/v1/chat/ (쿠키 없음) | 401 |
| ADMIN 만 가능한 endpoint 호출 | login `user.internal` → POST /api/v1/moderation/rules/ | 403 |
| 모더레이션 admin 의 rule 편집 | login `moderation.admin` → POST /api/v1/moderation/rules/ | 200 OK |

## 시드 명령 (구현 예정)

```bash
python manage.py seed_test_users
# → 위 7 계정 idempotent 생성 (이미 존재하면 skip)
```

management command: `chat/management/commands/seed_test_users.py` (B2 phase 에서 작성).

## 보안 메모

- 이 파일은 repo 에 commit 됨 → prod 환경에서 위 계정 자동 생성 금지. `DEBUG=True` 일 때만 seed 명령 실행 허용.
- 비밀번호 `Triple!23` 은 dev 한정. prod 시 환경변수 또는 `--password` 인자로 강제.
- 이메일 도메인 `@triplechat.test` 는 RFC 6761 reserved TLD `.test` 사용 — 실제 메일 발송 0 보장.
