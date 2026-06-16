# B5 — Streamlit 로그인 흐름

## 한 줄 요약
Streamlit frontend 가 backend `/auth/login/` 으로 로그인 → `requests.Session` 이 sessionid 쿠키를 보관 → 이후 chat 호출이 자동으로 인증됨 + `redacted_count` 배지 표시.

## 비유
**놀이공원 매표소 + 손목띠 (Phase A·B 후속).**

이전엔 입구에서 임의 user_id 종이쪽지 보여주면 통과. B4 후 백엔드 입구에 카드 리더 박혔다 — frontend 도 카드(=session cookie) 를 가지고 다녀야 한다. B5 는 매표소 UI (=login form) + 손목띠 보관함 (=`st.session_state.auth_session = requests.Session()`) 을 추가한 것.

<div class="analogy">
손목띠 보관함이 필요한 이유 — Streamlit 은 사용자가 버튼을 누를 때마다 스크립트를 처음부터 다시 실행한다. <code>requests.Session()</code> 을 매번 새로 만들면 쿠키가 사라져 매번 다시 로그인해야 한다. <code>st.session_state</code> 에 박아두면 reruns 사이에 살아남는다.
</div>

## 왜 이게 필요한가

| 항목 | 이전 (auto fetch_user_id) | 이후 (login flow) |
|---|---|---|
| 신원 출처 | 클라이언트 자동 할당 (서버가 새 user 발급) | 사용자가 이메일+비밀번호 입력 |
| 권한 위조 | 누구나 새 user 받아 자기 access_level 선택? | 운영자가 만든 계정만 접근 |
| 쿠키 관리 | 안 함 | `requests.Session` 이 sessionid 보관 |
| 권한 표시 | 없음 | 사이드바에 role/access_level 표시 |
| redacted_count | 무시 | amber 배지로 사용자에게 노출 |

## 핵심 코드

```python
# frontend/auth.py — 5줄 핵심
def _ensure_session() -> requests.Session:
    sess = st.session_state.get("auth_session")  # reruns 사이 생존
    if sess is None:
        sess = requests.Session()
        st.session_state["auth_session"] = sess
    return sess

# frontend/app.py — chat 호출 부
sess = auth_mod.get_session()
response = sess.post(f"{API_BASE_URL}/chat/", json={"question": prompt})
# sessionid 쿠키 자동 전송. user_id payload 제거 — 백엔드 (B4) 가 거부.
```

- `requests.Session()` → 쿠키 jar 보관, login 후 다음 호출에 자동 첨부
- `st.session_state["auth_session"]` → Streamlit rerun 사이 객체 보존
- chat payload 에서 user_id 제거 — B4 가 무시하므로 보낼 필요 없음

## 데이터 흐름

```
[Streamlit 로딩]
   init_session()
   ▼
auth.is_authenticated() ? 
   │ False → render_login_form() + st.stop()  ← 화면 멈춤
   │ True  → 계속
   ▼
[Login form 제출]
   auth.login(email, password)
       │ sess.post(/auth/login/) → 200 + sessionid 쿠키
       ▼
   st.session_state.auth_user = {email, role, access_level, ...}
   st.rerun()
   ▼
[chat input]
   send_chat_request(prompt)
       │ sess.post(/chat/, {question})  ← Cookie: sessionid=...
       ▼
   백엔드: request.user (B4) → access_level → ACL 필터 (Phase A)
       ▼
   {response, redacted_count, images}
   ▼
[표시]
   st.write(response)
   if redacted_count > 0: st.warning("[수정됨·N건] ...")
```

## 확인 방법 (수동 — Streamlit UI 검증)

1. `docker compose up` 또는 host 에서:
   ```bash
   # backend (host)
   source venv/bin/activate && python manage.py runserver
   # frontend (별 터미널)
   cd Rag_Chat/frontend && streamlit run app.py
   ```
2. 브라우저 `http://localhost:8501`:
   - "Sign in" form 표시 확인
   - `user.internal@triplechat.test` / `Triple!23` 입력 → 로그인 성공 토스트
3. 사이드바 user chip 확인:
   - `email · role=USER · access=internal` 표시
   - "Sign out" 버튼
4. 채팅 한 줄:
   - 질의 → 답변 + redacted_count > 0 이면 amber 배지
5. Sign out 클릭 → 로그인 화면 복귀

## 함정 — Streamlit rerun & requests.Session

Streamlit 은 buttom 클릭/입력마다 스크립트를 처음부터 다시 실행. 이때:
- 모듈 레벨 변수는 reset
- `st.session_state` 만 reruns 사이 살아남음

따라서 `requests.Session()` 을 모듈 레벨에서 만들면 **매 rerun 마다 새 인스턴스 = 쿠키 jar 비어있음 = 로그인 풀림**. `st.session_state["auth_session"]` 에 박아 해결.

## docker 환경 주의

`docker-compose.yml` 의 frontend 컨테이너는 `BACKEND_URL=http://backend:8000` 으로 컨테이너 간 통신. localhost (브라우저↔frontend) 와 다름. `frontend/auth.py` 가 `os.getenv("BACKEND_URL", ...)` 따라가므로 환경 변수만 맞으면 동작.

## 연습 문제

1. **Remember me 체크박스**: 로그인 form 에 `st.checkbox("Remember me")` 추가하고, 체크 시 Django 쪽 SESSION_COOKIE_AGE 를 2주로 늘리려면? (힌트: backend `LoginAPIView` 에 `request.session.set_expiry(2*7*86400)` 추가. frontend 는 어떻게 그 flag 를 전달할까?)
2. **권한별 UI 분기**: `auth.current_user()["role"]` 에 따라 사이드바의 "Upload knowledge" 버튼을 ADMIN 만 보이게 하려면? (힌트: `if user["role"] == "ADMIN": st.sidebar.file_uploader(...)`. 운영자만 업로드 권한 → CLAUDE.md "관리자가 코드 없이 튜닝" 의 frontend 표현.)
