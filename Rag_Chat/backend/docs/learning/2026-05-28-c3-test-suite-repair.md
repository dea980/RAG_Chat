# C3 — 전체 테스트 스위트 복구

## 한 줄 요약
B3 (`User → AbstractBaseUser`) 이후 발견된 7개 실패 (`User(username=...)` 호출 3개 + `@patch('backend.chat...')` 4개) 와 1개 모듈 로드 에러 (pytest 스타일 importorskip) 를 정리해 `manage.py test` 가 111/111 통과하도록 복구했다.

## 비유
**오래된 콘센트 모양이 바뀌면서 어댑터가 안 맞게 된 가전들.** B3 가 콘센트(=User 모델)를 바꿨는데, 옛 가전(=과거에 작성된 테스트들)이 옛 모양(`username=`)을 그대로 들고 있다가 불이 안 들어옴. 모양만 새 콘센트(`email=`)에 맞게 갈아끼우면 다시 작동한다.

<div class="analogy">
한 가지 더 — pytest 의 <code>importorskip</code> 은 pytest 만의 표지(=특정 모양의 어댑터). Django 의 unittest 러너는 그 표지를 못 알아보고 그냥 "고장 났다(ERROR)" 로 처리한다. <code>unittest.SkipTest</code> 라는 표준 표지로 바꿔야 둘 다 알아본다.
</div>

## 왜 이게 필요한가

| 항목 | C3 전 | C3 후 |
|---|---|---|
| `manage.py test` 결과 | FAILED (errors=7) | OK (skipped=1) — 111/111 |
| CI 게이트 가능? | ❌ | ✅ |
| 새 PR 회귀 감지 | 노이즈에 묻힘 | 새로 깨지는 7개 + 1개를 즉시 식별 |
| onnx-reranker 옵션 | 모듈 로드 자체가 실패 | torch 없으면 깔끔히 skip, 있으면 실행 |

## 핵심 코드

```python
# chat/tests/test_views.py — 사용자 생성 시 새 매니저 사용
- self.user = User.objects.create(username="testuser")
+ self.user = User.objects.create_user(email="testuser@triplechat.test")
```
`create()` 는 단순 INSERT 라 manager 의 `set_password` / `is_active` 기본값을 안 건다. 인증 흐름이 끼인 테스트라면 반드시 `create_user`.

```python
# chat/tests/test_views.py, test_utils.py — 패치 경로 수정
- @patch('backend.chat.views.SearchLog.objects.all')
+ @patch('chat.views.SearchLog.objects.all')
```
manage.py 가 `Rag_Chat/backend/` 에서 실행되므로 `chat.views` 가 정식 모듈 경로. 옛 `backend.chat.*` 은 외부 컨테이너 entrypoint 의 임포트 양식이었지만 지금 구조엔 없음.

```python
# chat/tests/test_onnx_bge.py — 모듈 레벨에서 unittest 식 스킵
for _mod in ("torch", "optimum.onnxruntime", "transformers"):
    try:
        importlib.import_module(_mod)
    except ImportError:
        raise unittest.SkipTest(f"{_mod} not installed — onnx reranker tests skipped")
```
`pytest.importorskip` 는 `pytest.Skipped` 를 던지는데 Django 의 unittest discover 가 이를 ERROR 로 카운트해 전체 빌드가 빨갛게 됨. `unittest.SkipTest` 로 던지면 둘 다 한 번에 "skip" 으로 처리.

## 데이터 흐름

```
manage.py test
  └─ Django test runner (unittest-based)
      └─ discover modules
          ├─ test_views.py   ← create_user(email=...) ✓
          ├─ test_utils.py   ← patch 'chat.utils.*' ✓
          └─ test_onnx_bge.py ← SkipTest at module level → 통째로 skip ✓
              ↑ 이전엔 pytest.importorskip(...) → "Skipped" exception
                 → unittest 가 못 알아봐서 ERROR 처리
```

## 확인 방법

```bash
cd Rag_Chat/backend
# 전체 — 1개 skip 외 전부 통과
venv/bin/python manage.py test -v 1
# Ran 111 tests in 17.003s
# OK (skipped=1)

# 회귀 — moderation 단독
venv/bin/python manage.py test moderation -v 1
# 57/57 OK
```

## 함정 — `User.objects.create` vs `create_user`

`AbstractBaseUser` 기반 모델에선 `objects.create(email=..., password=...)` 가 비밀번호를 평문으로 저장한다 (set_password 우회). 테스트가 인증 흐름을 안 건들면 (예: 이번처럼 단순 FK 채우기) 그래도 동작은 하지만, 운영 코드 어디서도 `User.objects.create` 직호출을 두면 안 됨. 항상 `create_user`/`create_superuser` 매니저 메서드.

## 함정 — patch path 는 *사용 위치 기준*

`@patch('chat.views.SearchLog.objects.all')` 의 의미는 "chat.views 모듈이 import 한 SearchLog 이름에 대한 .objects.all 을 mock" 이다. 만약 `chat.views` 가 `from .models import SearchLog as SL` 식으로 별칭을 썼다면 `chat.views.SL` 로 패치해야 한다. 정의 위치(`chat.models.SearchLog`) 가 아니라 **사용 위치**를 가리켜야 함.

## 연습 문제

1. **CI 게이트 도입**: GitHub Actions 에서 `manage.py test` 가 ERROR 1개라도 있으면 PR merge 차단하려면? 힌트: `.github/workflows/test.yml` + `python manage.py test --verbosity 2`. 새 워크플로 파일 한 개 + Postgres 서비스 컨테이너.

2. **failing test 패턴 grep 도구**: B3 같은 모델 변경 후 "지금 어떤 테스트가 옛 시그니쳐를 쓰고 있나" 를 자동 추출하려면? 힌트: `ast.parse` 로 `User.objects.create(*` 호출 노드를 모두 찾고 키워드 인자에 `username` 이 있으면 경고 출력. 30 줄짜리 pre-commit script 으로 가능.

3. **pytest 와 Django unittest 동시 지원**: 같은 디렉토리의 테스트가 두 러너 모두에서 깔끔히 돌게 하려면 pytest fixture 와 setUp/tearDown 을 어떻게 공존시킬까? 힌트: `pytest-django` 플러그인 + `@pytest.fixture` 와 `setUp` 의 책임 분리. pytest 가 fixture 를 먼저 해결, unittest 클래스는 setUp 만 본다.
