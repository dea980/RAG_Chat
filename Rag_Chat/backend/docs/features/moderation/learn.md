# 사내 RAG에서 대외비·PII·금칙어를 어떻게 다뤄야 하나
> **이 문서의 목적** — Triple Chat에 어떤 모더레이션 구조를 박을지 결정하기 전에, "다른 곳은 어떻게 하는지"와 "왜 그렇게 하는지"를 먼저 학습한다. 만든 다음에야 spec/구현을 한다.
>
> **읽는 순서**
> 1. § 1 TL;DR
> 2. § 2 왜 이게 어려운가 (개념 정립)
> 3. § 3 글로벌 패턴 한눈에 (벤치마크)
> 4. § 4 오픈소스 도구 (실전 적용 가능 후보)
> 5. § 5 공통 패턴 추출 — "라벨 + 권한 + 추적"
> 6. § 6 Triple Chat 결정 — 왜 3-layer label-based
> 7. § 7 비유로 다시 정리
> 8. § 8 실습 노트 — 직접 만져보기

---

## 1. TL;DR

- **키워드 매칭만으로는 PII·대외비 보호가 안 된다.** 키워드는 "주민등록번호"란 단어가 들어있는지를 보지만, 진짜 PII는 `901101-1234567` 같은 **패턴**으로 나타난다. 잘못된 안전감이 가장 큰 위험이다.
- 글로벌 표준은 **3종 세트**다 — *sensitivity label · DLP rule · audit log*. Microsoft Purview, Google Workspace, Slack Enterprise, Atlassian 전부 같은 구조.
- **Fasoo**는 한 단계 더 나아가 *문서 자체에 정책을 박는다 (Data-Centric DRM)*. 우리는 이만큼 갈 수 없지만 **"라벨이 chunk 메타데이터를 따라다닌다"** 는 아이디어는 그대로 가져올 수 있다.
- **Triple Chat 결정**: 3-layer label-based (Layer 1 = 업로드 시 라벨 부여, Layer 2 = retrieval에서 권한 vs 라벨 비교, Layer 3 = 입출력 모더레이션). 키워드/regex/embedding 매처는 Layer 3 안에서 도구로 사용.

---

## 2. 왜 이게 어려운가

### 2.1 "대외비"는 보안 등급의 중간 지대다
공공 부문 정의(파수 페이지 인용):
> 대외비 문서란 비밀(secret) **외에 직무 수행상 특별히 보호가 필요한 사항**.

핵심은 **"직무 수행상"** 이다. 비밀은 금고에 넣고 안 꺼내면 되지만, 대외비는 **써야 한다**. 안 쓰면 업무가 안 돌아간다. 그래서:

> **보안 ↔ 생산성** 트레이드오프가 본질이다. 너무 막으면 사용자가 우회한다 (개인 메일·Slack DM·메모장에 복붙).

이 트레이드오프를 푸는 방식이 회사마다 다르다 — 그게 § 3.

### 2.2 LLM이 끼면 문제가 더 어려워진다
기존 DLP는 "사람이 파일을 첨부해서 외부로 보냈는지"를 본다. RAG는:

1. 사용자가 **자기 권한 안의** chunk만 검색해야 한다 → ACL 매칭
2. LLM **답변이 권한 밖 chunk를 재구성** 할 수 있다 → 출력 검사 필요
3. **사용자 질문 자체**가 민감 정보를 LLM에 송출한다 → 입력 검사 필요
4. 외부 LLM(OpenAI·Gemini)에 보내는 raw context = **회사 밖으로 데이터 전송**

→ 모더레이션 경계는 한 곳이 아니라 **4 군데**다 — 업로드 · 질문 · 검색결과 · 답변 (CLAUDE.md 명세와 일치).

### 2.3 "그냥 금칙어 사전 두면 되지 않나요?"
이게 첫 분기에 죽는 이유:
- **PII**: 키워드 매칭은 `901101-1234567` 같은 실제 데이터를 못 잡는다. 잡으려면 regex.
- **대외비**: 코드네임은 자주 바뀐다. 키워드 리스트는 분기에 한 번 update 해야 하는데, 운영자가 코드 배포 권한이 없으면 죽은 사전이 된다 → **DB-driven 운영자 UI 필수**.
- **맥락 의존**: "원가"란 단어는 발표 자료에선 OK, 영업팀 답변에선 BLOCK. 단순 사전으론 표현 못 함 → **boundary 분리** 필요.

---

## 3. 글로벌 패턴 한눈에

### 3.1 Fasoo — Data-Centric DRM (엔터프라이즈 한국)
**철학**: 보안은 네트워크/엔드포인트가 아니라 **문서 자체** 에 박는다.

| 구성 | 동작 |
|--|--|
| **분류 (Cataloger AI)** | 문서 스캔 → 자동 라벨 부여 |
| **DRM 암호화** | 파일이 자기 정책 들고 다님. 외부 컴퓨터에서도 권한 검증 |
| **권한 제어** | 열람·복사·캡처·인쇄·배부 각각 별도 권한 |
| **추적 (FILM)** | 모든 사용 로그 영구 기록. 누가 언제 어디서 열었는지 |
| **GenAI DLP (AI-R DLP)** | LLM 채널 별도 차단 (네트워크 패킷 분석, sandbox 격리) |

**우리에게 적용**: 풀 DRM은 못 한다 (엔터프라이즈 시스템 도입 비용). 단, **"라벨이 컨텐츠를 따라다닌다"** 는 원칙은 chunk metadata로 재현 가능. → Layer 2의 본질.

### 3.2 Microsoft Purview — 표준 sensitivity label
**철학**: 모든 컨텐츠에 라벨이 있고, 라벨이 정책을 결정한다.

```
라벨 4단계:  Public  →  General  →  Confidential  →  Highly Confidential
정책:        없음     워터마크     암호화+DLP        암호화+공유차단+보존
```

**M365 Copilot 시그니쳐 동작**: 사용자가 가진 ACL을 **그대로** LLM context에 전달한다. 사용자가 못 보는 파일은 Copilot도 못 본다. → **권한 상속**이 핵심.

**우리에게 적용**: `User.access_level` ↔ `Document.sensitivity` 비교 모델 = 같은 구조. 4단계 라벨도 그대로 차용.

### 3.3 Google Workspace DLP
- **Predefined detectors**: SSN, 신용카드, 여권번호 등 ~150 종. 즉시 사용 가능.
- **Confidence**: high / medium / low — Luhn 같은 체크섬 검증으로 false positive 줄임.
- **Actions**: block · warn · audit only — 우리 BLOCK/MASK/WARN과 1:1 매핑.
- **Gemini Workspace**: 라벨 기반 검색 제한. 권한 없는 doc은 retrieval에서 제외.

**우리에게 적용**: confidence 점수는 phase 2. 일단 actions/severity 매핑만.

### 3.4 Slack Enterprise / Atlassian — 통합 DLP
- 자체 구현 안 하고 **Nightfall · BigID · Polymer** 같은 third-party를 통합.
- 메시지 송신 직전 스캔, **send 버튼이 회색으로** 비활성화 (사용자 학습).
- 채널 단위 sensitivity label — `#exec-only` 같은 채널은 자체로 라벨링.

**우리에게 적용**: 답변 송신 전 시각 차단(`[수정됨·N건]` ribbon) = 같은 UX 원칙. 사용자가 **무엇이 차단됐는지** 알아야 한다.

### 3.5 Apple / Meta 내부 (코드네임 운영)
- 모든 미공개 프로젝트에 **코드네임** 부여 (Apple "Titan", Meta "Quest").
- 코드네임은 **자동 키워드 블랙리스트**에 등록 — 외부 송신 시 차단.
- 사내 LLM도 동일 키워드 룰 상속.

**우리에게 적용**: 시드 데이터로 코드네임 카테고리 운영. ForbiddenWord(`category="코드네임"`)로 이미 시작점 있음.

---

## 4. 오픈소스 도구

| 도구 | 역할 | 도입 난이도 | Triple Chat 적합도 |
|--|--|--|--|
| **Microsoft Presidio** [github.com/microsoft/presidio](https://github.com/microsoft/presidio) | PII detection (regex + spaCy NER) + anonymization | 중 (spaCy 모델 다운로드) | **★★★★★** Layer 3 표준 |
| **NVIDIA NeMo Guardrails** | LLM 입출력 가드레일 — 토픽 차단, jailbreak | 중 (Colang DSL 학습) | ★★★ — phase 2 |
| **Guardrails AI** | validator 프레임워크 — schema·PII·profanity | 낮음 (pip install) | ★★★★ — 답변 검증에 좋음 |
| **Llama Guard** (Meta) | 작은 LLM이 1차 검열 (LLM-as-judge) | 높음 (GPU 필요) | ★★ — Ollama 추가 후 |
| **LangChain Constitutional AI** | LLM 자기검증 chain | 낮음 | ★★★ — 답변 self-check |
| **presidio-analyzer-ko** (community fork) | 한국 PII recognizer (주민번호·전화·계좌) | 낮음 | **★★★★★** |

**우리 phase 별 선택**:
- Phase C에 **Presidio + 한국 recognizer**. PII 표준 매처.
- Phase D 검토: **Llama Guard** (Ollama 자체 호스팅 후 — security.md Stage 2 끝나면).

---

## 5. 공통 패턴 추출 — "라벨 + 권한 + 추적"

위의 모든 시스템이 다음 3종을 공유한다:

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  ① 라벨      │  →   │  ② 권한 매칭  │  →   │  ③ 추적 로그  │
│ sensitivity  │       │  ACL · DLP    │       │  audit trail │
└──────────────┘       └──────────────┘       └──────────────┘
```

| 패턴 | 역할 | 누가 가짐 |
|--|--|--|
| ① **Sensitivity label** | 컨텐츠가 얼마나 민감한지 | Document(파일)·chunk·메시지 |
| ② **ACL / DLP rule** | 누가 / 어떤 boundary에서 그 라벨에 접근 가능한지 | User·Role·Boundary 조합 |
| ③ **Audit log** | 누가 언제 어떤 시도를 했고 어떻게 처리됐는지 | ModerationLog·AuditLog |

**왜 셋이 다 필요한가?**
- 라벨만 있고 권한 매칭 없으면 → 그냥 메타데이터 (보호 안 됨)
- 권한만 있고 라벨 없으면 → 매번 ad-hoc 키워드 매칭 = false negative 폭증
- 추적 없으면 → 사고 사후 조사 불가능 + 운영자가 룰 튜닝 못 함

---

## 6. Triple Chat 결정 — 왜 3-layer label-based

### 6.1 결론
```
Layer 1 — 인덱싱 (업로드 경계)
  Document.sensitivity 라벨 부여 (사용자 선택 → phase 2에 자동분류)
  restricted = vector store 진입 차단

Layer 2 — 검색 (retrieval 경계)
  User.access_level ≥ chunk.sensitivity 인 chunk만 반환
  필터된 결과 → citation에 [수정됨·N건] 가시화 (silent drop 금지)

Layer 3 — 입출력 검사 (질문·답변 경계)
  PII: Presidio + 한국 regex
  대외비 키워드/regex: ModerationRule (확장된 ForbiddenWord)
  답변에 대해서도 동일 적용 (outbound)
```

### 6.2 왜 라벨이 첫 단추인가
**라벨이 없으면 모든 layer가 ad-hoc 키워드 매칭에 의존하게 된다.** 그게 첫 분기에 죽는 이유다 (CLAUDE.md 메모리). 라벨이 있으면:

- Layer 2는 단순 비교 (`user.level >= chunk.level`)
- Layer 3은 라벨에 따라 **다른 룰셋** 적용 (예: `restricted` 답변에는 PII 마스킹 + 외부 LLM 차단)
- 운영자는 라벨 단위로 정책을 관리 → UI가 단순해짐

### 6.3 왜 키워드/regex/embedding은 "도구"이지 "전략"이 아닌가
- 키워드: 정확하지만 누락 많음 (변형·오타·동의어)
- regex: 형식이 고정된 데이터 (주민번호·전화) 강점, 자연어엔 약함
- embedding: 자연어 의미 잘 잡지만 비용·지연·해석 어려움

→ 각각 **특정 카테고리에서만 강함**. 전체 전략은 라벨이 잡고, 각 layer가 알맞은 도구를 고른다.

### 6.4 왜 4 boundary인가
한 boundary에서만 막으면 우회로가 생긴다:
- 업로드만 막으면 → 민감 데이터가 이미 인덱스에 있는 경우 검색됨
- 검색만 막으면 → LLM이 학습된 지식으로 재구성
- 답변만 막으면 → 검색 결과로 사용자가 raw chunk 봄 (사이드패널)

→ **4 boundary 동일 카테고리/severity 로 운영자 UI 일관성** 도 중요. 모더레이션 패널 한 곳에서 모든 boundary 관리.

### 6.5 거부한 옵션과 이유
| 옵션 | 거부 이유 |
|--|--|
| 키워드 사전만 풍부히 (현재 ForbiddenWord 확장만) | § 2.3에서 다룸 — 잘못된 안전감 |
| Fasoo급 풀 DRM 도입 | 비용·복잡도. 부트캠프 RAG에 oversized |
| LLM이 self-judge (Constitutional AI만) | 라벨 없으면 LLM 판단 일관성 없음. 또 외부 LLM에 raw 송신 = 본질 해결 안 됨 |
| 외부 vendor (Nightfall·BigID) | 사내 RAG에 outbound dependency 추가 = 회피 |

---

## 7. 비유로 다시 정리

### 7.1 도서관 비유
| 시스템 | 도서관 |
|--|--|
| Document | 책 |
| sensitivity | 책 표지의 등급 스티커 (일반 · 청소년 · 성인 · 금서) |
| User.access_level | 도서관 카드의 등급 |
| Layer 1 (업로드) | 사서가 신간을 받을 때 스티커 붙임 |
| Layer 2 (retrieval) | 사용자 카드 보고 열람 가능 책만 진열 |
| Layer 3 (입출력) | 책장에서 페이지 찢는지 감시 + 사진 촬영 차단 |
| audit log | 대출 기록 |

### 7.2 여권 비유 (Fasoo DRM의 본질)
- 일반 파일 = 종이 메모. 복사하면 그만.
- Fasoo DRM 파일 = **여권을 들고 다니는 파일**. 어디로 가든 출입국 검사 받음.
- 우리 chunk metadata = **여권 미니 버전**. vector store에서 꺼낼 때마다 검사.

### 7.3 이중 자물쇠 비유 (왜 boundary 4 군데인가)
- 한 자물쇠는 도구만 있으면 따짐.
- 자물쇠 4개를 다른 메커니즘으로 → 한 곳 뚫려도 나머지가 잡음.
- 업로드(물리 잠금) · 질문(키 확인) · 검색(지문) · 답변(망보는 사람).

---

## 8. 실습 노트

### 8.1 현재 ForbiddenWord 테이블 확인
```bash
docker compose exec backend python manage.py shell -c "
from moderation.models import ForbiddenWord
for w in ForbiddenWord.objects.all()[:10]:
    print(f'{w.severity:8s} {w.direction:8s} {w.category:10s} {w.word}')
"
```

**관찰 포인트**: severity·direction·category·word 4축뿐. pattern_type·boundary 없음 → Phase A 마이그레이션 필요.

### 8.2 현재 PII 처리 한계 실험
```bash
docker compose exec backend python manage.py shell -c "
from moderation.filter import apply
from moderation.models import ModerationLog
# 키워드 매칭 (현재 동작)
print(apply('주민등록번호를 알려주세요', source=ModerationLog.Source.INBOUND))
# 실제 PII 데이터 (현재는 못 잡음 — 잘못된 안전감!)
print(apply('내 정보는 901101-1234567 이야', source=ModerationLog.Source.INBOUND))
"
```

→ 첫 줄은 잡히고 둘째 줄은 통과한다. 이게 § 2.3에서 말한 문제. **Phase C에서 Presidio + regex로 해결**.

### 8.3 한국 PII regex 직접 테스트
```python
import re

patterns = {
    '주민번호': r'\b\d{6}[-]?[1-4]\d{6}\b',
    '휴대전화': r'\b01[016-9][-]?\d{3,4}[-]?\d{4}\b',
    '이메일':   r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b',
    '신용카드': r'\b(?:\d[ -]?){13,19}\b',
}

text = '연락처는 010-1234-5678 / 901101-1234567 / kim@example.com'
for name, pat in patterns.items():
    hits = re.findall(pat, text)
    print(f'{name:8s}: {hits}')
```

**연습 과제**: Luhn 알고리즘으로 신용카드 false positive 줄이기 (Google DLP가 쓰는 방식).

### 8.4 라벨 기반 retrieval 시뮬레이션 (코드 없이)
```
사용자: access_level = "internal"
chunk A: sensitivity = "public"        → 통과 ✓
chunk B: sensitivity = "internal"      → 통과 ✓
chunk C: sensitivity = "confidential"  → 차단 (citation에 [수정됨·1건] 표시)
chunk D: sensitivity = "restricted"    → 인덱스 진입 안 함 (Layer 1)
```

→ Layer 2 핵심 동작. **차단된 게 있다는 사실은 보여줘야** 한다 (silent drop 금지).

### 8.5 모더레이션 UI 목업 보기
`Rag_Chat/docs/design/preview.html` 09 섹션 — 운영자 검수 화면. 4 boundary 탭 · 카테고리/pattern_type/severity 컬럼 · 실시간 테스트 패널. 구현은 phase A·B·C 끝난 후.

---

## 9. 다음 읽을거리

- [references.md](references.md) — 외부 문서 큐레이션 (Fasoo · MS Purview · Presidio · NeMo 등 링크)
- [refs/fasoo_원본.html](refs/fasoo_원본.html) — 파수 페이지 원본 보존
- [../../architecture/security.md](../../architecture/security.md) — 기존 보안 아키텍처 (현재 keyword-only 한계 포함)
- [../../superpowers/specs/2026-05-28-moderation-architecture.md](../../superpowers/specs/2026-05-28-moderation-architecture.md) — 3-layer 설계 spec (D)
- [../../superpowers/plans/2026-05-28-moderation-implementation.md](../../superpowers/plans/2026-05-28-moderation-implementation.md) — 실행 plan (A→B→C)
- [../../../docs/design/preview.html](../../../docs/design/preview.html) — design system mockup (admin/moderation 09 섹션)
