# C5 — ForbiddenWord regex 패턴 타입

## 한 줄 요약
`ForbiddenWord` 에 `pattern_type` 칸을 추가해 운영자가 리터럴 키워드(`KW`) 외에 정규식(`RE`) 도 등록할 수 있게 했다. `\d{6}-\d{7}` (주민번호) 같은 형식 자체를 매칭하는 starter 두 개를 seed 에 포함시켰고, 잘못된 regex 는 한 줄도 깨뜨리지 않고 `logger.warning` 후 스킵.

## 비유
**문 앞 검색대의 두 종류 검사관.**
- KW 검사관은 가방에서 "대외비" 라벨이 붙은 폴더를 찾는다 — 정확한 글자만 일치.
- RE 검사관은 "13자리 숫자가 6-7 형태로 배열된 종이" 를 찾는다 — 형식 매칭. 누군가 가짜 이름의 폴더에 주민번호를 적어도 잡힌다.
두 검사관이 같은 검색대(=filter.apply) 에서 같은 ForbiddenWord 테이블의 규칙을 받아 자기 방식으로 검사.

<div class="analogy">
"한 가지 잘못된 규칙이 모든 검사를 멈추게 하면 안 된다" 가 보안 시스템의 첫 원칙. operator 가 admin UI 에서 <code>[unclosed</code> 같은 깨진 regex 를 실수로 저장했을 때 다음 사용자 요청이 전부 500 으로 죽으면 서비스 가용성이 결정된다. <code>try/except re.error → logger.warning + skip</code> 한 줄이 그 안전망.
</div>

## 왜 이게 필요한가

| 항목 | KW 만 (C5 전) | KW + RE (C5 후) |
|---|---|---|
| "대외비" 단어 차단 | ✅ | ✅ (동일) |
| `900101-1234567` 주민번호 매칭 | ❌ (문자열 "주민번호" 만 잡힘) | ✅ regex `\d{6}-\d{7}` |
| `1234-5678-9012-3456` 카드번호 | ❌ | ✅ regex `\d{4}-\d{4}-\d{4}-\d{4}` |
| 잘못된 regex 입력 시 | (해당 없음) | logger.warning + 다른 규칙 그대로 작동 |
| 운영자 학습 곡선 | "단어 등록" | KW=단어, RE=정규식. radio 선택 2개 |

핵심: PII 차단의 진짜 가치는 단어가 아니라 **형식 매칭**. 사용자가 "내 주민번호는 ..." 이라고 단어를 안 써도 형식만 맞으면 OUTBOUND 마스킹이 작동해야 한다.

## 핵심 코드

```python
# moderation/models.py — TextChoices 한 클래스 추가
class PatternType(models.TextChoices):
    KW = "KW", "키워드 (대소문자 무시 부분 일치)"
    RE = "RE", "정규식 (re.search)"

pattern_type = models.CharField(
    max_length=2, choices=PatternType.choices, default=PatternType.KW,
    help_text="KW=리터럴 부분 일치, RE=정규식 (예: \\d{6}-\\d{7})",
)
```

```python
# moderation/filter.py — _find_matches 가 rule.pattern_type 별 분기
def _find_matches(text, rules):                  # rules = [(word, kind), ...]
    for word, kind in rules:
        if kind == ForbiddenWord.PatternType.RE:
            try:
                pattern = re.compile(word, re.IGNORECASE)
            except re.error as exc:
                logger.warning("invalid regex %r — %s", word, exc)
                continue                          # ← 한 규칙 실패가 나머지를 막지 않음
            for m in pattern.finditer(text):
                hits.append((word, m.start(), m.end()))
        else:
            # 기존 KW 로직 (substring 반복 매칭)
            ...
```

```python
# starter regex (운영자가 처음 보는 예시 — copy-paste 가능)
(r"\d{6}-\d{7}",          "PII", MASK, OUTBOUND, "[주민번호REDACTED]", "...", RE),
(r"\d{4}-\d{4}-\d{4}-\d{4}", "PII", MASK, OUTBOUND, "[카드번호REDACTED]", "...", RE),
```

## 데이터 흐름

```
[운영자] admin UI Test panel
   "응답에 900101-1234567 포함" + source=OUTBOUND + 실행
        ▼
[backend POST /moderation/test/]
   filter.apply(text, source=OUTBOUND, dry_run=True)
        ▼
[filter.apply]
   _active_rules(("BOTH","OUTBOUND"))
   for r in rules:
       by_severity[r.severity].append((r.word, r.pattern_type))
        ▼
[_find_matches(text, [("주민번호", "KW"),
                      (r"\d{6}-\d{7}", "RE")])]
   KW 분기: "주민번호" 단어 매칭 → 없음
   RE 분기: re.compile(r"\d{6}-\d{7}", IGNORECASE).finditer(text)
       → hit at 900101-1234567 → start=N, end=N+13
        ▼
[MASK 치환 (right-to-left)]
   sanitized = "응답에 [주민번호REDACTED] 포함"
        ▼
[Response]
   action=MASKED, sanitized=..., masked_words=[r"\d{6}-\d{7}"]
```

## 확인 방법

```bash
cd Rag_Chat/backend

# 단위 + 통합
venv/bin/python manage.py test moderation.tests.test_pattern_type -v 1
# → 7/7 OK (default KW / KW match preserved / RE match / RE block /
#           KW with metachar doesn't false-positive / invalid regex skipped)

# seed 가 regex 룰 포함 확인
venv/bin/python manage.py test moderation.tests.test_seed_forbidden_words -v 1
# → 6/6 OK (count + categories + idempotent + edits + summary + regex seeded)

# 전체 moderation 회귀
venv/bin/python manage.py test moderation -v 1
# → 78/78 OK
```

수동 (브라우저):
1. `python manage.py seed_forbidden_words` 실행 (starter 18개 — KW 16 + RE 2)
2. Streamlit Moderation Admin → Rules 탭
3. 표에서 `\d{6}-\d{7}` 행의 type chip 이 amber **RE** 로 보임 (KW 는 회색)
4. Test panel → 텍스트 `주민번호 900101-1234567 입니다`, source=`OUTBOUND` → 실행
5. 결과: `Action: MASKED`, sanitized = `주민번호 [주민번호REDACTED] 입니다`
6. 새 RE 규칙 추가 시도 — `[unclosed` 입력 + RE 선택 + 추가
7. 다음 chat 호출이 여전히 정상 작동 (잘못된 regex 가 다른 규칙을 막지 않음 — backend log 에 warning)

## 함정 — KW 모드에서 정규식 metacharacter

운영자가 KW 모드로 `\d+` 라고 등록하면 그건 *문자열 "\\d+" 와 정확히 일치* 만 잡는다. "1234" 처럼 숫자만 있는 텍스트엔 안 잡힘. 만약 의도와 다르면 운영자가 pattern_type 을 RE 로 바꿔야 함. test `test_regex_rule_no_false_match_on_literal_metacharacter` 가 이 경계를 고정.

## 함정 — `re.IGNORECASE` 의 한정성

regex 매칭은 `IGNORECASE` 플래그를 강제로 켜놓았다. operator 가 대소문자 구분이 필요한 정규식을 등록하고 싶다면 미리 `(?-i:...)` 같은 그룹 플래그를 써야 한다. 이건 99% 사용 사례 (PII 형식 매칭) 가 대소문자와 무관하므로 OK — 운영자 학습 비용을 줄임.

## 함정 — DB 마이그레이션 + max_length=2

`pattern_type` 은 `max_length=2` 의 CharField. "KW"/"RE" 만 가능. 미래에 새 종류 추가 시 마이그레이션 + max_length 증가 필요. 현재는 2자리로 정확히 맞춰 인덱스 효율 + 명시.

## 함정 — `r"..."` 와 SQL 저장

regex 는 raw string 으로 작성하는 게 안전(`r"\d{6}-\d{7}"`). Django ORM 은 그 값을 그대로 저장하므로 DB 에 `\d{6}-\d{7}` 가 들어간다. 만약 운영자가 admin UI 에서 `\\d{6}` 처럼 백슬래시 두 번 입력하면 그건 *문자 그대로의 `\\d`* 매칭이 됨 — 사실상 매칭 안 됨. UI 의 help 문구 + placeholder 가 이걸 명시해야 함.

## 연습 문제

1. **regex 검증 라이브 미리보기**: admin UI 의 새 규칙 폼에서 RE 모드로 입력할 때, 입력 직후 `re.compile(pattern)` 을 시도해 invalid 면 빨간 보더로 즉시 표시하려면? 힌트: `st.text_input` 의 on_change 콜백 + `re.error` 캐치. 운영자가 저장 *전* 에 발견.

2. **임베딩 유사도 (Phase D 미리보기)**: `pattern_type=EMB` 를 추가해 "기밀과 의미상 유사한 문장" 도 잡으려면? 힌트: ForbiddenWord 에 임베딩 벡터 칼럼 + filter.apply 가 chunk 임베딩과 코사인 유사도. 무거우므로 retrieval boundary 에만 적용 권장.

3. **regex 성능 가드**: 운영자가 catastrophic backtracking 가능한 regex (예: `(a+)+b`) 를 등록하면 chat 한 번에 수 초 지연. 어떻게 막을까? 힌트: `signal.alarm(0.05)` 으로 컴파일·매칭 타임아웃 + 초과 시 logger.error + skip. Linux 전용이라 단순하진 않음.
