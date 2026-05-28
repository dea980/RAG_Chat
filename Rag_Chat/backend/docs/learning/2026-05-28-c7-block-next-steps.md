# C7 — Block 응답 + "다음 단계" 안내

## 한 줄 요약
차단(`BlockedByModerationError`)이 발생한 chat 응답이 단순 "blocked" 메시지로 끝나던 것을, CLAUDE.md 의 명시 패턴(**warning border + 사유 + 다음 단계**) 에 맞춰 카테고리별 다음 단계 (예: "대외비 → 관리자에게 공개 신청") 를 backend payload + amber 보더 ribbon UI 로 표면화했다.

## 비유
**식당 입구의 거절 vs 안내.** 손님이 드레스 코드 위반으로 입장 거부될 때, "안 됩니다" 만 하면 손님은 어디로 가야 할지 모른다. "재킷이 없으셔서요. 대여 카운터는 좌측 3m" 같은 안내가 있으면 손님은 다음 행동을 안다. C7 은 chat 의 차단 응답에 그 "좌측 3m" 을 추가한다.

<div class="analogy">
"빨강 배너 금지" 는 CLAUDE.md 가 단호히 정한 디자인 룰. 사용자가 죄지은 느낌이 아니라 <strong>경고 + 안내</strong> 톤이어야 함. 그래서 <code>st.error</code> (빨강) 대신 amber 보더(<code>#D9A441</code>) + 본문 + bullet 안내 구조.
</div>

## 왜 이게 필요한가

| 항목 | C7 전 | C7 후 |
|---|---|---|
| 차단 응답 body | `{error, blocked_words, chat_id}` | `+ categories, next_steps` |
| 사용자 다음 행동 | 없음 — 막막함 | 카테고리별 1-2 문장 안내 |
| 프론트 시각 패턴 | `st.error` 빨강 배너 (CLAUDE.md 위반) | amber `#D9A441` 보더 + mono small-caps `BLOCKED · MODERATION` |
| CLAUDE.md 거절 패턴 준수 | ❌ | ✅ |

## 핵심 코드

```python
# moderation/messages.py — 카테고리 → 안내 매핑 (소량의 코드)
_CATEGORY_NEXT_STEPS = {
    "대외비": ["관리자에게 공개 신청...", "기밀 표현을 빼고 다시 질문..."],
    "PII":   ["개인정보를 빼고 다시 질문...", "보안팀 승인 절차..."],
    "욕설":  ["정제된 표현으로 다시 시도...", "사내 챗봇은 욕설 미전달..."],
    "경쟁사": ["영업 정책상 답변 안 함...", "영업팀 slack 문의..."],
}
def next_steps_for(categories: Iterable[str]) -> list[str]:
    """카테고리 중복 제거 + dedup 라인 + fallback."""
```

```python
# moderation/filter.py — BLOCK 시점에 이미 계산된 categories 를 exception 으로 전달
class BlockedByModerationError(Exception):
    def __init__(self, words, categories=None, ...):
        self.categories = categories or []
...
raise BlockedByModerationError(words=words, categories=categories)
```

```python
# chat/views.py — 응답 payload 확장 (총 2줄 추가)
from moderation.messages import next_steps_for
return Response({
    "error": "...",
    "blocked_words": exc.words,
    "categories": exc.categories,          # ← 신규
    "next_steps": next_steps_for(exc.categories),  # ← 신규
    "chat_id": ...,
}, status=403)
```

```python
# frontend/app.py — amber 보더 (DESIGN.md 의 warning #D9A441)
if response_data.get("blocked"):
    block_html = f"""
    <div style="border:1px solid #D9A441; background:rgba(217,164,65,0.08);
                border-radius:6px; padding:12px 16px;">
      <div style="font-weight:500;color:#D9A441;
                  font-family:'Geist Mono',monospace;font-size:11px;
                  letter-spacing:0.09em;text-transform:uppercase;">
        BLOCKED · MODERATION
      </div>
      <div>질문에 차단된 표현이 포함되어 답변이 중단되었습니다.</div>
      <div>Words: {words_chip} · Categories: {cat_chip}</div>
    </div>"""
    st.markdown(block_html, unsafe_allow_html=True)
    st.markdown("**다음 단계**")
    st.markdown("\n".join(f"- {s}" for s in next_steps))
```

## 데이터 흐름

```
[사용자 입력: "대외비 문서 알려줘"]
   ▼
[chat/views.py — ChatAPIView.post()]
   moderate_text(question, source=INBOUND)
     │
     ▼
[moderation/filter.py — apply()]
   blocked_hits ← _find_matches([..."대외비"])
   categories  ← {"대외비"}
   ModerationLog.objects.create(action=BLOCKED, ...)  ← 감사 로그
   raise BlockedByModerationError(words=[..."대외비"], categories=["대외비"])
     │
     ▼
[chat/views.py — except 분기]
   next_steps_for(["대외비"]) → ["관리자에게 공개 신청...", "기밀 표현을 빼고..."]
   Return 403 + {error, blocked_words, categories, next_steps, chat_id}
     │
     ▼
[frontend/send_chat_request]
   status_code == 403 → 그대로 dict 반환 + blocked=True 마커
     │
     ▼
[frontend chat panel]
   amber 보더 + Words/Categories chip + bullet next_steps
```

## 확인 방법

```bash
cd Rag_Chat/backend

# 단위 + 통합
venv/bin/python manage.py test moderation.tests.test_next_steps -v 1
# → 8/8 OK (helper 6 + exception 1 + endpoint 1)

# 회귀
venv/bin/python manage.py test moderation chat.tests.test_chat_auth_gate -v 1
# → 86/86 OK
```

수동 확인 (브라우저):
1. `python manage.py seed_forbidden_words` (C4 — `대외비` BLOCK 규칙이 포함됨)
2. `streamlit run app.py`
3. `user.internal@triplechat.test` 로 로그인
4. 챗에 "대외비 문서 알려줘" 입력 → amber 보더 + `Words: 대외비 · Categories: 대외비` + 다음 단계 2줄
5. 빨강(`st.error`)이 아니라 amber(`#D9A441`)인지 시각 확인

## 함정 — `send_chat_request` 의 `raise_for_status`

이전엔 `response.raise_for_status()` 가 403 도 RequestException 으로 던져서 `st.error("Failed to get response...")` 만 떴고, 본문의 `next_steps` 가 통째로 사라졌다. 403 분기를 raise 직전에 가로채는 한 줄로 해결.

```python
if response.status_code == 403:
    payload = response.json()
    payload["blocked"] = True
    return payload
response.raise_for_status()  # 그 외 (500 등) 은 그대로 raise
```

이 패턴은 "예상되는 HTTP 코드 (403/422 등) 는 raise 가 아닌 정상 return 으로" 라는 일반 원칙의 사례. 외부 API 가 422 의미 codes 을 잘 정의했다면 같은 분기가 늘어남.

## 함정 — `unsafe_allow_html=True` 의 위험

`st.markdown(block_html, unsafe_allow_html=True)` 는 HTML 직접 삽입을 허용 — XSS 위험. 다행히 이 자리에 들어가는 값들 (`blocked_words`, `categories`) 은 모두 backend ForbiddenWord 테이블 에서 온 운영자 등록 데이터로, 사용자 입력 아님. 만약 사용자 입력을 chip 으로 표시하려면 `html.escape()` 필수.

## 함정 — 카테고리에 매핑이 없을 때

`_FALLBACK = ["운영자가 차단으로 분류한 표현입니다 — 표현을 바꿔 다시 시도하거나 관리자에게 문의해 주세요."]` — 매핑 누락 시 침묵하지 않고 일반 안내. 새 카테고리 등록 후 `messages.py` 매핑 추가를 잊어도 사용자는 막막함 없음.

## 연습 문제

1. **DB 기반 next_steps**: 현재 `_CATEGORY_NEXT_STEPS` 가 코드에 하드코딩. 운영자가 admin UI 에서 카테고리별 안내문을 편집하려면? 힌트: 새 모델 `CategoryGuidance(category, next_steps[])` + admin 페이지에 탭 추가 + `next_steps_for` 이 DB 조회로 바뀜.

2. **i18n**: 사내 사용자가 한국어/영어 섞여 있다면? 힌트: `_CATEGORY_NEXT_STEPS` 를 `{cat: {locale: [...]}}` 로 확장 + `request.LANGUAGE_CODE` 또는 사용자 프로필의 `locale` 칼럼.

3. **frontend 차단 분석 카운터**: 차단 이벤트가 같은 사용자에게 5분 내 3번 발생 시 자동으로 "관리자에게 알림 보내기" 버튼 표시하려면? 힌트: 프론트엔드 측 `st.session_state` 에 timestamp 큐 + 5분 슬라이딩 윈도. CLAUDE.md 의 trigger_count 카테고리 관리 의도와 비슷.
