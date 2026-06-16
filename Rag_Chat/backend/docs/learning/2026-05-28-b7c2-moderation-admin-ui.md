# B7-C2 — 운영자 Moderation Admin UI

## 한 줄 요약
ADMIN 만 접근 가능한 Streamlit 페이지 `frontend/pages/moderation_admin.py` 를 추가해, 운영자가 (1) ForbiddenWord 규칙 CRUD, (2) 샘플 텍스트로 4경계 규칙 작동을 즉시 확인하는 실시간 테스트 패널, (3) 최근 20건 감사 로그 — 세 작업을 코드 변경 없이 수행할 수 있게 했다. 백엔드 쪽엔 `/moderation/test/` (dry-run) endpoint 를 추가했다.

## 비유
**아파트 관리실에 설치된 콘솔.** 출입통제 규칙(=ForbiddenWord)을 4경계(=출입문 4곳)에 적용하는 시스템은 이미 깔려있다. 하지만 그동안 관리소장은 새 규칙을 추가하려면 코드를 직접 만져야 했다 — 차단 단어 1개 늘리는 데 git push + 배포가 필요한 셈. C2 는 그 콘솔의 패널이다. 버튼 한 번으로 규칙을 켜고 끄고, "이 단어를 차단하면 어디서 어떻게 잡힐까" 를 즉시 미리보기.

<div class="analogy">
실시간 테스트 패널 (= dry-run) 의 핵심은 <strong>감사 로그를 남기지 않는다</strong>는 것. 진짜 사고가 났을 때만 ModerationLog 가 늘어나야지, 운영자가 사이드에서 100번 테스트한 흔적이 같은 테이블에 섞이면 사고 추적이 망가진다. <code>filter.apply(..., dry_run=True)</code> 가 그 분기 한 줄.
</div>

## 왜 이게 필요한가

| 항목 | 이전 (B7까지) | 이후 (C2) |
|---|---|---|
| 규칙 추가 | 코드 직접 수정 + 마이그레이션 + 배포 | Streamlit UI 폼 — 추가 즉시 4경계 적용 |
| 규칙 테스트 | 실제 chat 호출 → 감사 로그 오염 | dry-run endpoint — 로그 안 남기고 결과만 |
| 일반 사원이 UI 접근 | endpoint 자체 403, 페이지는 빌드되어 있어도 OK | 페이지가 role 체크 후 `st.stop()` — UX 친화적 거부 |
| 감사 로그 열람 | DB shell 또는 Django admin | Streamlit 페이지에서 최근 20건 즉시 |
| 운영자가 "이 단어 추가하면 어떻게 될까" | 별도 시뮬레이션 없음 | 테스트 패널 + severity chip 색상 (BLOCK=빨강 / MASK=노랑 / WARN=파랑) |

CLAUDE.md 의 4경계 모더레이션 요구사항에서 코드 레벨은 B7 이 닫았다. C2 는 "관리자가 코드 없이 튜닝" 을 표면화한다 — 실제 사람이 만질 인터페이스. 이게 없으면 B7 은 운영자에게 보이지 않는 기능이다.

## 핵심 코드

```python
# moderation/filter.py — dry_run 추가 (전체 3 곳의 ModerationLog.create 우회)
def apply(text, *, source, user=None, chat=None, dry_run: bool = False):
    ...
    if blocked_hits:
        if not dry_run:                      # ← 로그 기록은 실제 트래픽에만
            ModerationLog.objects.create(...)
        raise BlockedByModerationError(...)  # 동작 자체는 dry_run 도 동일
```

```python
# moderation/views.py — ModerationTestAPIView
class ModerationTestAPIView(APIView):
    permission_classes = [IsAuthenticated, IsModerationAdmin]
    def post(self, request):
        try:
            result = moderate_text(text, source=source, dry_run=True)
        except BlockedByModerationError as exc:
            return Response({"action": "BLOCKED", ...})
        return Response({"action": action_for(result), "sanitized": result.sanitized, ...})
```

```python
# frontend/pages/moderation_admin.py — ADMIN 게이트 한 줄
def _require_admin():
    if not auth_mod.is_authenticated():
        auth_mod.render_login_form(); st.stop()
    user = auth_mod.current_user() or {}
    if user.get("role") != "ADMIN":
        st.error("운영자(ADMIN) 권한이 필요합니다."); st.stop()
    return user
```

세 부분을 `st.tabs([...])` 로 묶음 — Rules / Test panel / Audit logs.

## 데이터 흐름

```
[Streamlit pages/moderation_admin.py]
   _require_admin()
     │   is_authenticated()  ─── (B3 sessionid)
     │   role == "ADMIN"     ─── (B6 frontend gate, UX)
     ▼
   tab "Rules"      ──▶ GET /moderation/rules/      (IsModerationAdmin)
                    ──▶ POST /moderation/rules/     (ADMIN 만 통과)
                    ──▶ DELETE /moderation/rules/N/
   tab "Test panel" ──▶ POST /moderation/test/      ← C2.1 신규
                          │
                          ▼
                     filter.apply(text, source, dry_run=True)
                          │ (BLOCK→raise / MASK→sanitized / WARN→log skipped)
                          ▼
                     {action, sanitized, blocked_words, masked_words, warned_words, categories}
                          │  (로그 안 남음)
                          ▼
                     Streamlit chip 렌더 (BLOCK 빨강 / MASK 노랑 / WARN 파랑)
   tab "Audit logs" ──▶ GET /moderation/logs/       (IsManager — ADMIN 도 통과)
                          ▼
                     최근 20건 테이블
```

## 확인 방법

1. 백엔드 + 프론트 기동
```bash
cd Rag_Chat/backend && venv/bin/python manage.py runserver &
cd Rag_Chat/frontend && streamlit run app.py
```
2. 브라우저 `http://localhost:8501`
3. 로그인 — `admin@triplechat.test` / `Triple!23` (시드 사용자)
4. 좌측 사이드바에서 **moderation_admin** 페이지 이동
5. **Rules 탭** — "규칙 추가" 펼침 → `대외비` / `기밀` / `BLOCK` / `BOTH` 입력 → "추가". 표에 즉시 행 추가
6. **Test panel 탭** — `이건 대외비 문서입니다` 입력, source = `INBOUND` → `실행`
   - 결과: `Action: BLOCKED`, `Blocked: 대외비`
   - 감사 로그 탭에 새 이벤트 **안 생김** (dry-run 확인)
7. **Audit logs 탭** — 실제 chat 에서 BLOCK 일어난 이벤트만 표시
8. 다른 계정 (예: `user.internal@triplechat.test`) 로 로그인 → 같은 페이지 열면 `운영자(ADMIN) 권한이 필요합니다.` + `st.stop()`

백엔드 단위 검증:
```bash
cd Rag_Chat/backend
venv/bin/python manage.py test moderation.tests.test_test_endpoint -v 1
# → 7/7 OK
venv/bin/python manage.py test moderation -v 1
# → 57/57 OK (전체 moderation 회귀)
```

## 함정 — `dry_run` 의 3 곳 일관성

`filter.apply` 안에 `ModerationLog.objects.create(...)` 호출이 **3 곳**(BLOCK / MASK / WARN) 있다. dry_run 분기를 1 곳만 막으면 BLOCK 은 깔끔하지만 MASK/WARN 테스트가 silently 로그를 만들어버린다. 3 곳 모두 `if not dry_run:` 으로 감싸야 함. 테스트 `test_no_audit_log_written` 가 그 회귀 안전망.

## 함정 — Streamlit `st.set_page_config` 위치

`st.set_page_config(...)` 는 페이지 내 **가장 첫 Streamlit 명령**이어야 한다. import 직후, `_require_admin()` 전에 호출. 만약 import 단계에서 에러가 나거나 한 줄 `st.write` 가 위로 올라가면 `StreamlitAPIException` 으로 페이지 전체가 안 뜬다.

## 함정 — `requests.Session` 의 sessionid 쿠키

B5 의 트랩이 그대로 적용 — admin 페이지도 `auth_mod.get_session()` 으로 같은 세션 객체를 받아야 sessionid 쿠키가 따라간다. 새 `requests.Session()` 직접 만들면 인증 안 됨.

## 연습 문제

1. **`trigger_count` 칼럼 추가**: 각 ForbiddenWord 가 지금까지 몇 번 trip 됐는지 표시하려면? 힌트: `ModerationLog.objects.filter(detected_words__contains=[word]).count()` 를 serializer 에 `SerializerMethodField` 로 노출. N+1 위험 — `annotate` 로 줄여보라.

2. **BLOCK 다음 단계 안내**: 사용자가 차단 응답을 받았을 때 "이 단어가 차단됐으니 관리자에게 신청하세요" 식 안내가 자동으로 뜨려면 (CLAUDE.md — "거절·차단 시각 패턴: warning border + 사유 + 다음 단계")? 힌트: chat 응답 payload 에 `next_steps` 추가 + frontend 가 색 토큰 #D9A441 으로 렌더.

3. **regex 패턴 칸 추가**: 운영자가 `\d{6}-\d{7}` (주민번호) 패턴을 등록하려면? 힌트: ForbiddenWord 에 `kind` (`LITERAL`/`REGEX`) 칼럼 + admin UI 에 라디오 + filter.\_find_matches 분기.
