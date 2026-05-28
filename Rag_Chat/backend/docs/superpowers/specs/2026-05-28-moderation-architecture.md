# Spec — Triple Chat Moderation Architecture (3-layer label-based)

> **Status**: Draft (2026-05-28). 학습 노트와 함께 작성됨 — 구현 전 D 단계.
>
> **Cross-link 우선**
> - 학습 노트: [../../features/moderation/learn.md](../../features/moderation/learn.md)
> - 외부 참조: [../../features/moderation/references.md](../../features/moderation/references.md)
> - 실행 plan: [../plans/2026-05-28-moderation-implementation.md](../plans/2026-05-28-moderation-implementation.md)
> - 기존 보안 문서: [../../architecture/security.md](../../architecture/security.md) (Phase 1 = keyword-only, 이 spec이 Phase 2)
> - UI mockup: [../../../docs/design/preview.html](../../../docs/design/preview.html) (09 섹션)

---

## 1. Context · 왜 이 spec이 필요한가

### 1.1 현재 상태의 부족
- **Layer 부재**: 모더레이션이 INBOUND/OUTBOUND 2-방향만. CLAUDE.md 명세인 4 경계(업로드·질문·검색결과·답변)를 표현 못 함.
- **Pattern type 단일**: lowercase substring 매칭만. PII는 keyword 매칭으로 못 잡음 — 잘못된 안전감.
- **권한 부재**: `User`가 chunk·문서 sensitivity를 기준으로 retrieval을 제한할 메커니즘이 없음.
- **Silent drop**: ModerationLog에 기록만 되고 사용자 화면에 차단 사실이 노출되지 않음.

### 1.2 CLAUDE.md 명세 (재인용)
> 4경계 방어, 모두 운영자가 코드 없이 튜닝. 하드코딩 필터는 첫 분기에 죽음. 무성 드롭 금지 · retrieval에서 차단된 chunk는 citation에 `[수정됨·N건]`으로 가시화.

### 1.3 비-목표 (Non-goals)
- **Fasoo급 풀 DRM** 도입 — 비용·범위 초과
- **외부 vendor (Nightfall·BigID) 통합** — outbound dependency 회피
- **자체 호스팅 LLM 도입** — `architecture/security.md` Stage 2에서 별도로 다룸
- **prompt injection 방어** — OWASP LLM Top 10의 별도 항목, 본 spec 범위 밖

---

## 2. Threat Model

| ID | 위협 | 현재 방어 | 본 spec 후 |
|--|--|--|--|
| T1 | 사용자 질문에 포함된 PII (주민번호·신용카드)가 외부 LLM에 송출 | keyword "주민등록번호" 단어만 잡음 | Layer 3 PII regex (Presidio) |
| T2 | retrieval이 사용자 권한 외 chunk 노출 | 없음 | Layer 2 ACL 매칭 |
| T3 | LLM 답변이 권한 외 chunk를 재구성하여 출력 | OUTBOUND keyword | Layer 3 outbound + 라벨 인지 |
| T4 | 코드네임·M&A 키워드가 답변에 leak | OUTBOUND keyword BLOCK | 유지 + boundary 명시화 |
| T5 | 업로드 시 `restricted` 문서가 vector store에 인덱싱 | 없음 | Layer 1 인덱싱 차단 |
| T6 | 운영자가 새 패턴 추가하려면 코드 변경 필요 | Django Admin 일부 가능 (word 추가) | 동일, 단 pattern_type · boundary 차원 추가 |
| T7 | 사용자가 결과 누락 사실을 모름 → 가짜 답변 신뢰 | Silent | citation에 `[수정됨·N건]` |

---

## 3. Decision · 3-layer label-based

### 3.1 한 화면 요약

```
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 1 · 업로드 경계                                                 │
│  Document.sensitivity 라벨 부여                                        │
│  restricted → vector store 진입 차단                                   │
└──────────────┬─────────────────────────────────────────────────────────┘
               │ (chunk metadata에 라벨 상속)
┌──────────────▼─────────────────────────────────────────────────────────┐
│  Layer 2 · retrieval 경계                                              │
│  User.access_level ≥ chunk.sensitivity 인 것만 반환                    │
│  필터된 결과 → citation에 [수정됨·N건] 배지                            │
└──────────────┬─────────────────────────────────────────────────────────┘
               │
┌──────────────▼─────────────────────────────────────────────────────────┐
│  Layer 3 · 질문/답변 경계                                              │
│  PII (KR_RRN, PHONE, CARD) → Presidio regex 매처                       │
│  대외비/코드네임/욕설 → ModerationRule (KW / RE / EMB)                 │
│  inbound + outbound 양방향                                             │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 핵심 원칙
1. **라벨이 1차 분류 신호**. 모든 layer가 라벨을 1순위로 본다.
2. **권한 매칭은 단조함수**. `User.access_level`이 정수 ladder, sensitivity도 정수 ladder. 비교 한 줄.
3. **silent drop 금지**. 차단·필터링은 사용자에게 가시화한다 (`[수정됨·N건]`).
4. **모든 boundary 동일 audit 스키마**. 사고 조사 시 boundary와 무관하게 동일 쿼리.
5. **운영자 UI는 boundary x category 매트릭스**. 코드 변경 없이 운영.

---

## 4. Schema 변경

### 4.1 Sensitivity ladder

```python
class Sensitivity(models.TextChoices):
    PUBLIC       = "public",       "공개"
    INTERNAL     = "internal",     "사내 공유"
    CONFIDENTIAL = "confidential", "대외비"
    RESTRICTED   = "restricted",   "기밀 (인덱싱 차단)"

# 정수 비교를 위해 ordering helper
SENSITIVITY_LEVEL = {
    "public": 0, "internal": 1, "confidential": 2, "restricted": 3
}
```

### 4.2 `knowledge.Document` 변경 (Layer 1)

```python
class Document(models.Model):
    # ... 기존 필드
    sensitivity = models.CharField(
        max_length=20,
        choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
        db_index=True,
        help_text="업로드 시 부여. restricted = vector store 진입 차단",
    )
    sensitivity_set_by = models.ForeignKey(
        "chat.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="docs_classified",
    )
    sensitivity_set_at = models.DateTimeField(auto_now=True)
```

마이그레이션: 기존 행은 모두 `default=INTERNAL`로 채움. 운영자 검수 필요.

### 4.3 `chat.User` 변경 (Layer 2)

```python
class User(AbstractUser):
    # ... 기존 필드
    access_level = models.CharField(
        max_length=20,
        choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
        help_text="이 레벨 이하 sensitivity의 chunk만 retrieval 가능",
    )
```

**규칙**:
- `access_level >= chunk.sensitivity` 만 retrieval 통과
- `restricted` 사용자만 `restricted` chunk 검색 가능 (그러나 Layer 1에서 인덱싱 차단되므로 사실상 별도 인덱스/별도 store 필요 — Phase 2 결정)

### 4.4 `moderation.ModerationRule` (기존 ForbiddenWord 확장 또는 신모델)

**선택지 A — ForbiddenWord 확장**
```python
class ForbiddenWord(models.Model):
    class PatternType(models.TextChoices):
        KW  = "KW",  "키워드 substring"
        RE  = "RE",  "정규식"
        EMB = "EMB", "임베딩 prototype 유사도"

    word = models.CharField(max_length=240)  # 240으로 확장 (regex/긴 표현)
    pattern_type = models.CharField(max_length=3, choices=PatternType.choices, default="KW")
    category = models.CharField(max_length=50)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    boundaries = models.JSONField(
        default=list,
        help_text='["upload","query","retrieval","answer"] 중 적용 경계',
    )
    mask_replacement = models.CharField(max_length=80, default="[REDACTED]")
    embedding_threshold = models.FloatField(null=True, blank=True,
        help_text="pattern_type=EMB일 때 cosine 임계값",
    )
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 데이터 이관: direction → boundaries
    #   INBOUND  → ["query"]
    #   OUTBOUND → ["answer"]
    #   BOTH     → ["query","answer"]
```

**선택지 B — 신모델 ModerationRule, ForbiddenWord deprecate**
- 깨끗하지만 마이그레이션·코드 영향 큼
- filter.py·admin.py·seed 코드 다시 작성

**결정**: **A**. 이유: 기존 filter.py 시그너처 유지 + 운영 데이터 손실 없음. `direction` 필드는 deprecated 마크 후 `boundaries`로 자동 마이그레이션.

### 4.5 `moderation.ModerationLog` 확장

```python
class ModerationLog(models.Model):
    # ... 기존 필드
    boundary = models.CharField(
        max_length=20, db_index=True,
        choices=[("upload","upload"),("query","query"),("retrieval","retrieval"),("answer","answer")],
    )
    rule_id = models.ForeignKey(
        "moderation.ForbiddenWord", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="logs",
    )
```

**이관**: 기존 `source=INBOUND` → `boundary=query`, `source=OUTBOUND` → `boundary=answer`.

---

## 5. Layer 별 동작 명세

### 5.1 Layer 1 — 업로드
**입력**: 파일 + 업로더 + 사용자가 선택한 sensitivity (default=INTERNAL)
**동작**:
1. `Document.sensitivity` 저장
2. `restricted`이면 vector store 인덱싱 **skip** + `AuditLog(action="ingest.skipped_restricted")`
3. 모든 chunk record에 `metadata.sensitivity = doc.sensitivity` 복사

**Phase 2 자동 분류 (선택)**: 업로드된 텍스트를 sample → ModerationRule(EMB) 또는 Llama Guard로 sensitivity 제안 → 운영자 확인 후 commit.

### 5.2 Layer 2 — Retrieval
**입력**: 사용자 query + `User.access_level`
**동작**:
1. vector search top_k=20
2. 결과를 filter: `SENSITIVITY_LEVEL[user.access_level] >= SENSITIVITY_LEVEL[chunk.sensitivity]`
3. 필터로 제거된 갯수를 카운트 → `redacted_count`
4. reranker 통과
5. response에 `redacted_count` 포함 → frontend가 citation에 `[수정됨·N건]` 표시

**audit**: `ModerationLog(boundary="retrieval", action="REDACTED", detected_words=[chunk_ids])`

### 5.3 Layer 3 — 입출력 검사

**입력 (boundary=query)**:
1. 사용자 text → Presidio analyzer (PII)
2. Active rules (boundaries 포함 "query") 매칭
   - BLOCK → 403 + ModerationLog + frontend에 사유 표시
   - MASK → 치환 후 통과 + ModerationLog
   - WARN → 통과 + ModerationLog
3. LLM 호출 with sanitized text

**출력 (boundary=answer)**:
1. LLM 응답 → 동일 처리, boundary="answer"
2. 차단된 답변은 사용자에게 "보안 정책에 의해 일부 응답이 가려졌습니다" + `[수정됨·N건]` 노출

**Dry-run 모드 (실시간 테스트 패널용)**:
```python
def apply(text, *, source=None, boundary=None, user=None, chat=None, dry_run=False):
    # dry_run=True → ModerationLog 기록 안 함, 결과만 반환
```

---

## 6. UI 통합

### 6.1 Citation Ribbon (mockup 05 섹션)
- `redacted_count > 0` → 마지막 chip 위치에 amber badge `[수정됨·N건]`
- hover → tooltip "보안 정책에 따라 N개 chunk가 가려졌습니다. 권한 확인은 관리자에게."

### 6.2 Admin Moderation (mockup 09 섹션)
- 4 boundary 탭: 업로드 · 질문 · 검색결과 · 답변
- 규칙 컬럼: category · pattern_type(KW/RE/EMB) · boundaries · severity · fired·7d
- 우측: 실시간 테스트 패널 (`apply(text, boundary=tab, dry_run=True)` 결과 표시)

### 6.3 Document upload 화면 (신규)
- 파일 선택 후 sensitivity 드롭다운 (default=INTERNAL)
- restricted 선택 시 경고: "이 문서는 검색 인덱스에 들어가지 않습니다"

---

## 7. Audit Log 통합

모든 boundary가 동일 스키마. 사고 조사 쿼리 예시:

```python
ModerationLog.objects.filter(
    user__email="user@example.com",
    created_at__gte=incident_start,
    action__in=["BLOCKED", "MASKED"],
).order_by("created_at")
```

→ 시간순으로 사용자가 어떤 경계에서 무엇이 어떻게 처리됐는지 한 줄로 본다.

---

## 8. 의사결정 로그

| 결정 | 이유 |
|--|--|
| 4단계 sensitivity (Purview 차용) | 글로벌 표준 + 한국어 매핑(공개/사내/대외비/기밀) 자연스러움 |
| `User.access_level` 단일 필드 (RBAC 아님) | 부트캠프 범위. 부서·역할 RBAC은 phase 3 |
| `restricted` 인덱싱 차단 (Layer 1) | 보안 ↔ 검색 가능성 트레이드오프 — 잠재 누설 비용이 검색 가치보다 큼 |
| ForbiddenWord 확장 (신모델 X) | 기존 filter.py 시그너처 유지, 데이터 손실 없음 |
| Presidio (자체 PII 구현 X) | 검증된 표준. spaCy NER 무료 차용. 한국 recognizer만 custom |
| Dry-run 모드 명시화 | 운영자 실시간 테스트 패널 — 로그 오염 없이 정책 실험 |
| `[수정됨·N건]` 가시화 | silent drop 금지 (CLAUDE.md). 신뢰 유지 |
| LLM-as-judge (Llama Guard)는 후순위 | Ollama/vLLM 인프라 필요. security.md Stage 2 의존 |

---

## 9. 명시적으로 *안 하는 것* (이 spec에서)

- 부서/역할 기반 ACL (RBAC) — `access_level` 단일 필드만
- Document 단위 다른 retention policy
- 외부 vendor 통합 (Nightfall 등)
- chunk 단위 encryption-at-rest
- 사용자별 access_level 자동 평가 (HR 시스템 연동)
- restricted 별도 인덱스 — Phase 2 결정 사항으로 미룸

---

## 10. Verification Checklist (구현 후 통과 기준)

- [ ] migration `0NNN_document_sensitivity.py` · `0NNN_user_access_level.py` · `0NNN_forbiddenword_expand.py` 적용됨
- [ ] 기존 ForbiddenWord 행이 boundaries=["query","answer"]로 자동 이관
- [ ] `apply(text, boundary="query", dry_run=True)`가 ModerationLog 0행 생성
- [ ] Presidio가 `901101-1234567`을 KR_RRN으로 감지 (learn.md § 8.2 실험 통과)
- [ ] retrieval response에 `redacted_count` 포함
- [ ] citation ribbon에 `[수정됨·N건]` 렌더 (frontend Streamlit + 미래 Next.js)
- [ ] admin /admin/moderation/forbiddenword/ 에서 pattern_type · boundaries 편집 가능
- [ ] `python manage.py shell` 에서 `restricted` 사용자가 `confidential` 문서를 search → 통과, `internal` 사용자는 차단
- [ ] AuditLog 쿼리 한 줄로 사용자별 boundary별 통계 조회

---

## 11. Cross-link 다시

| 문서 | 역할 |
|--|--|
| [learn.md](../../features/moderation/learn.md) | 학습 노트 — 왜 이 설계인가 |
| [learn.html](../../features/moderation/learn.html) | 시각 학습 페이지 |
| [references.md](../../features/moderation/references.md) | 외부 자료 큐레이션 |
| [security.md](../../architecture/security.md) | 보안 일반 (Phase 1 = keyword-only) |
| [plans/2026-05-28-moderation-implementation.md](../plans/2026-05-28-moderation-implementation.md) | 실행 plan (A→B→C) |
| [DESIGN.md](../../../../DESIGN.md) | UI/UX 단일 출처 (admin moderation 명세) |
| [docs/design/preview.html](../../../docs/design/preview.html) | UI mockup (09 섹션 = admin) |
