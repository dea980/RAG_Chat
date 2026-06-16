# 외부 자료 큐레이션 — 대외비·PII·금칙어

> **목적** — [learn.md](learn.md)에서 참조한 시스템·도구의 원문 링크와 한 줄 요약. 깊게 들어가기 전에 어디부터 읽으면 가성비가 가장 높은지 표시.
>
> **읽는 순서 추천**
> 1. § 1 표준이 무엇인가 (Microsoft Purview)
> 2. § 2 한국 시장 맥락 (Fasoo)
> 3. § 3 곧 import할 도구 (Microsoft Presidio)
> 4. § 4 phase 2 검토 도구 (NeMo · Guardrails AI · Llama Guard)
> 5. § 5 패턴/케이스 스터디

---

## 1. Microsoft Purview — sensitivity label 표준

| 자료 | 우리에게 핵심 |
|--|--|
| **Microsoft Learn → "Sensitivity labels"** (검색어: `microsoft purview sensitivity labels overview`) | 4단계 라벨(Public/General/Confidential/Highly Confidential) 구조. 우리 `Document.sensitivity`의 직접 모델 |
| **Microsoft Learn → "DLP policy reference"** (검색어: `microsoft purview dlp policy reference`) | block / warn / audit-only 액션 매핑. 우리 BLOCK/MASK/WARN과 1:1 |
| **Microsoft 365 Copilot data protection** (검색어: `microsoft 365 copilot data protection inherits permissions`) | "사용자 ACL을 그대로 LLM에 전달" 시그니쳐 원칙. Layer 2 설계 근거 |

**우리에게 적용**
- 4단계 라벨 그대로 차용 (이름만 한국어로 — `public/internal/confidential/restricted`)
- "권한 상속" 원칙 = `User.access_level ≥ chunk.sensitivity`
- DLP policy 액션 3종 그대로 유지

---

## 2. Fasoo — Data-Centric DRM (한국 엔터프라이즈)

| 자료 | 우리에게 핵심 |
|--|--|
| **fasoo.com → "대외비 문서 관리 및 보안 솔루션"** (원본 저장: [refs/fasoo_원본.html](refs/fasoo_원본.html)) | 대외비 정의 + Fasoo 솔루션 라인업 (Cataloger AI · DRM · FILM · AI-R DLP). 한국 시장이 어떻게 정의하는지 |
| **fasoo.com → "AI-R DLP / 생성형 AI 정보유출방지"** (검색어: `Fasoo AI-R DLP GenAI`) | LLM 채널에서 데이터 유출 차단하는 3가지 패턴 (네트워크 패킷, sandbox 격리, 채널 단일화). Layer 3 outbound의 한국 벤더 관점 |

**우리에게 적용 가능 / 불가**
- ✅ **분류 → 라벨 → 정책** 흐름 (Cataloger AI 패턴): chunk metadata로 미니 버전 재현
- ✅ **추적 (FILM)**: 이미 우리 `ModerationLog` + `AuditLog`가 같은 역할
- ✅ **GenAI 채널 인지**: outbound moderation으로 LLM 응답 검사
- ❌ **DRM 암호화**: 풀 엔터프라이즈 시스템 필요. 부트캠프 RAG에 oversized
- ❌ **외부 PC 추적**: 사내 RAG 범위 밖

---

## 3. Microsoft Presidio — Phase C에 import할 도구

| 자료 | 우리에게 핵심 |
|--|--|
| **github.com/microsoft/presidio** | PII detection/anonymization 표준. spaCy NER + regex 결합. 한국어 약함 — recognizer custom 추가 필요 |
| **microsoft.github.io/presidio** (공식 docs) | Analyzer · Anonymizer 분리 구조. 우리는 Analyzer만 import 후 자체 anonymizer 연결 가능 |
| **microsoft.github.io/presidio → "Supported entities"** | 미국 PII 25종 사전 제공 (SSN, credit card, ITIN 등). 한국 entity는 직접 추가 |
| **Presidio Korean PII community forks** (검색어: `presidio korean recognizer`) | 주민번호·전화·계좌 regex 모음. Phase C 시드의 출발점 |

**Phase C 도입 계획**
1. `pip install presidio-analyzer presidio-anonymizer`
2. spaCy 한국어 모델 (`ko_core_news_md` 또는 `xx_ent_wiki_sm`)
3. Custom recognizer 등록:
   ```python
   from presidio_analyzer import PatternRecognizer, Pattern
   krn_rrn = PatternRecognizer(
       supported_entity="KR_RRN",
       patterns=[Pattern(name="rrn", regex=r"\b\d{6}[-]?[1-4]\d{6}\b", score=0.9)],
   )
   ```
4. `moderation/filter.py`에 `pattern_type="RE"` 룰 매처 시 Presidio analyzer 호출

---

## 4. Phase 2 검토 도구

| 자료 | 한 줄 평가 | 도입 시점 |
|--|--|--|
| **NVIDIA NeMo Guardrails** (`github.com/NVIDIA/NeMo-Guardrails`) | Colang DSL로 LLM 입출력 가드레일. 토픽 차단·jailbreak 방지 강력. 학습 곡선 있음 | Stage 2 (사내 Ollama 후) |
| **Llama Guard** (Meta · HF에서 모델 가중치 배포, 검색어: `llama guard model card`) | 작은 LLM이 1차 검열. GPU 필요. LLM-as-judge 패턴의 표준 | Stage 3 (vLLM 인프라 후) |
| **Guardrails AI** (`github.com/guardrails-ai/guardrails`) | validator 프레임워크 — schema·PII·profanity. RAIL spec로 룰 정의 | Phase C 끝나면 답변 self-check 라이브러리로 검토 |
| **LangChain Constitutional AI** (`python.langchain.com` → "constitutional ai") | LLM이 자기 답변 재검토. critique → revision. 가벼움 | Phase C에 옵셔널 wrap |
| **OWASP LLM Top 10** (검색어: `owasp llm top 10`) | LLM-specific 위협 분류 표준. prompt injection · sensitive info disclosure 등. moderation spec 작성 시 위협 모델 cross-check 용도 | spec 작성 단계 |

---

## 5. 패턴 / 케이스 스터디 (가볍게 읽기)

- **Slack Enterprise DLP** — "send 버튼 회색화" UX 패턴 (검색어: `slack enterprise dlp message blocking`)
- **Google Workspace Confidence-based DLP** (검색어: `google workspace dlp confidence likelihood`) — high/med/low 점수로 false positive 억제 방식
- **Apple/Meta 코드네임 운영** — 정식 백서 없음. 업계 블로그·이직 인터뷰 통해 알려진 패턴
- **OWASP API Security Top 10** (검색어: `owasp api security top 10`) — API 보안 일반. AuditLog 미들웨어 설계 시 참조
- **GDPR Article 32 / 한국 개인정보보호법** — 법적 요건. PII 마스킹·암호화 의무 근거. CTO/보안담당자 협의 시 인용

---

## 6. 우리 repo 내 cross-link

| 파일 | 역할 |
|--|--|
| [learn.md](learn.md) | 한국어 학습 노트 (이 문서의 본문) |
| [learn.html](learn.html) | 시각 학습 페이지 (DESIGN.md 톤) |
| [refs/fasoo_원본.html](refs/fasoo_원본.html) | 파수 페이지 원본 보존 |
| [../../architecture/security.md](../../architecture/security.md) | 기존 보안 아키텍처 (keyword-only 한계 포함) |
| [../../superpowers/specs/2026-05-28-moderation-architecture.md](../../superpowers/specs/2026-05-28-moderation-architecture.md) | 3-layer label-based 설계 spec |
| [../../superpowers/plans/2026-05-28-moderation-implementation.md](../../superpowers/plans/2026-05-28-moderation-implementation.md) | Phase A→B→C 실행 plan |
| [../../../../DESIGN.md](../../../../DESIGN.md) | UI/UX 단일 출처 (admin moderation 화면 명세 포함) |
| [../../../docs/design/preview.html](../../../docs/design/preview.html) | design system mockup (09 섹션 = admin moderation UI) |

---

## 7. URL 보존 정책

이 문서의 외부 링크는 **저자 도메인 + 검색어** 형식으로 적었다. 이유:

- Microsoft Learn · Google Workspace docs URL은 자주 재구성됨 (deep link rot 빈번)
- 검색어가 더 안정적 — 같은 페이지 찾기 가능
- 도메인은 확실한 곳만 (`github.com`, `python.langchain.com`, `microsoft.github.io`)

원본을 영구 보존하고 싶으면:
1. archive.org (Wayback Machine)에 archive request 후 archive URL을 본 문서에 추가
2. 또는 PDF로 저장해서 `refs/` 디렉토리에 둠 (파수 페이지 같은 방식)
