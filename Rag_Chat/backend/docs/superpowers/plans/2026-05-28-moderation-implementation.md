# Plan — Moderation 3-Layer 구현 (Phase A → B → C)

> **Status**: Draft (2026-05-28). Spec 동반 문서.
> **Spec**: [../specs/2026-05-28-moderation-architecture.md](../specs/2026-05-28-moderation-architecture.md) — 본 plan은 spec의 결정을 시간순으로 실행 가능한 단계로 분해한다.
>
> **사용 대상**: executor agent · 다른 Claude Code 세션 · 사람 엔지니어. 각 단계는 독립적으로 검증 가능해야 한다.

---

## 0. 사전 준비

### 0.1 환경
- Python 3.11 (`backend/venv/` 사용 중)
- Postgres 16 또는 sqlite (현재 dev = sqlite — phase A에서도 sqlite OK)
- Django 5.x
- 작업 전 `git status` 깨끗한지 확인. 작업 브랜치 `feature/moderation-3layer` 권장

### 0.2 학습 의존성
구현 시작 전 반드시 읽기:
1. [learn.md](../../features/moderation/learn.md) — 왜 이렇게 가는지
2. [spec](../specs/2026-05-28-moderation-architecture.md) §3, §4 — 데이터 모델 결정

### 0.3 estimated effort
- Phase A: 2~3시간 (모델·마이그레이션·테스트)
- Phase B: 3~4시간 (filter.py 리팩토링·테스트)
- Phase C: 2~3시간 (Presidio 통합·한국 recognizer)
- 합계 ~9시간. 한 번에 다 하지 말고 phase별 commit.

---

## Phase A — Label-based ACL (가장 큰 ROI)

> **목표**: `Document.sensitivity` + `User.access_level` + retrieval 필터. 라벨이 모든 layer의 1차 신호.
> **Spec 참조**: §3.1 Layer 1·2 · §4.2 · §4.3

### A.1 모델 변경

**1) `knowledge/models.py` — Document에 sensitivity 추가**
```python
from django.db import models

class Sensitivity(models.TextChoices):
    PUBLIC       = "public",       "공개"
    INTERNAL     = "internal",     "사내 공유"
    CONFIDENTIAL = "confidential", "대외비"
    RESTRICTED   = "restricted",   "기밀"

class Document(models.Model):
    # ... 기존 필드
    sensitivity = models.CharField(
        max_length=20, choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL, db_index=True,
    )
    sensitivity_set_by = models.ForeignKey(
        "chat.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="docs_classified",
    )
    sensitivity_set_at = models.DateTimeField(auto_now=True)
```

**2) `chat/models.py` — User에 access_level 추가**
```python
from knowledge.models import Sensitivity  # 또는 공통 enum으로 분리

class User(AbstractUser):
    # ... 기존 필드
    access_level = models.CharField(
        max_length=20, choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
    )
```

**3) 공통 ladder helper — `moderation/levels.py` (신규)**
```python
SENSITIVITY_LEVEL = {
    "public": 0, "internal": 1, "confidential": 2, "restricted": 3
}

def can_access(user_level: str, content_level: str) -> bool:
    return SENSITIVITY_LEVEL[user_level] >= SENSITIVITY_LEVEL[content_level]
```

### A.2 마이그레이션

```bash
cd backend
python manage.py makemigrations knowledge chat
# 검토:
#   knowledge/migrations/0NNN_document_sensitivity.py
#   chat/migrations/0NNN_user_access_level.py
python manage.py migrate
```

**기존 데이터**: default=INTERNAL로 자동 채워짐. 운영자가 admin에서 검수 필요. 시드 스크립트(`seed_demo.py`) 업데이트 — 기존 PRODUCTS의 sensitivity는 모두 `internal`로.

### A.3 Vector store 인덱싱 필터 (Layer 1)

`chat/build_vector_store.py` 또는 `ingest/` 파이프라인:
```python
def should_index(doc: Document) -> bool:
    if doc.sensitivity == "restricted":
        AuditLog.objects.create(
            user=doc.uploaded_by,
            action="ingest.skipped_restricted",
            resource="Document",
            resource_id=str(doc.id),
            detail={"name": doc.name},
        )
        return False
    return True
```

추가로 chunk metadata에 sensitivity 복사:
```python
chunk_meta["sensitivity"] = doc.sensitivity
```

### A.4 Retrieval 필터 (Layer 2)

`chat/views.py` 또는 `chat/pipeline/` retrieval 함수:
```python
from moderation.levels import can_access

# vector search → 결과
raw_hits = vector_store.search(query, top_k=20)

filtered = []
redacted = 0
for hit in raw_hits:
    chunk_sens = hit.metadata.get("sensitivity", "internal")
    if can_access(user.access_level, chunk_sens):
        filtered.append(hit)
    else:
        redacted += 1
        ModerationLog.objects.create(
            user=user, chat=chat,
            detected_words=[hit.metadata.get("chunk_id")],
            matched_categories=[chunk_sens],
            action="REDACTED",  # 새 액션 추가 필요 (§ B에서)
            source="retrieval",
            original_excerpt="",
            sanitized_excerpt="",
        )

# response에 redacted 포함
return {"hits": filtered, "redacted_count": redacted}
```

### A.5 테스트

`moderation/tests/test_acl.py` (신규):
```python
from django.test import TestCase
from moderation.levels import can_access

class AclLevelTest(TestCase):
    def test_strict_ordering(self):
        assert can_access("internal", "public")
        assert can_access("internal", "internal")
        assert not can_access("internal", "confidential")
        assert not can_access("public", "internal")

    def test_restricted_only_restricted(self):
        assert can_access("restricted", "confidential")
        assert not can_access("confidential", "restricted")
```

Integration test — retrieval에서 필터링:
```python
class RetrievalAclTest(TestCase):
    def setUp(self):
        self.user_internal = User.objects.create(access_level="internal")
        self.doc_conf = Document.objects.create(sensitivity="confidential", ...)
        # 인덱싱
    def test_internal_user_cannot_see_confidential(self):
        response = self.client.post("/api/v1/triple/chat/", ...)
        assert response.json()["redacted_count"] >= 1
```

### A.6 Phase A Exit Criteria
- [ ] migration 적용 성공 (`./manage.py migrate`)
- [ ] 기존 ForbiddenWord 데이터 손실 없음 (`ForbiddenWord.objects.count() >= 15`)
- [ ] AclLevelTest 통과
- [ ] retrieval response에 `redacted_count` 키 포함
- [ ] `internal` 사용자가 `confidential` chunk를 못 봄 (integration test 통과)
- [ ] frontend는 아직 표시 안 해도 OK (Phase C 후 UI 통합)
- [ ] commit: `feat(moderation): Phase A — sensitivity label + access_level + retrieval filter`

---

## Phase B — ModerationRule 확장 (4 boundary + pattern_type)

> **목표**: ForbiddenWord에 pattern_type · boundaries 추가. filter.py를 boundary 기반으로 리팩토링. dry_run 모드 지원.
> **Spec 참조**: §4.4 · §5.3

### B.1 모델 변경

`moderation/models.py`:
```python
class ForbiddenWord(models.Model):
    class PatternType(models.TextChoices):
        KW  = "KW",  "키워드"
        RE  = "RE",  "정규식"
        EMB = "EMB", "임베딩 prototype"

    class Severity(models.TextChoices):  # 기존 그대로
        MASK = "MASK", "마스킹"
        WARNING = "WARNING", "경고"
        BLOCK = "BLOCK", "차단"

    word = models.CharField(max_length=240)  # 120 → 240
    pattern_type = models.CharField(max_length=3, choices=PatternType.choices, default="KW")
    category = models.CharField(max_length=50)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    boundaries = models.JSONField(default=list)
    mask_replacement = models.CharField(max_length=80, default="[REDACTED]")
    embedding_threshold = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)
    # direction은 deprecated (Phase D 제거)
    direction = models.CharField(max_length=10, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

`ModerationLog`에 `boundary` + `rule` ForeignKey 추가. Action choices에 `REDACTED` 추가.

### B.2 데이터 마이그레이션

`moderation/migrations/0NNN_boundaries_and_pattern_type.py`:
```python
def migrate_direction_to_boundaries(apps, schema_editor):
    FW = apps.get_model("moderation", "ForbiddenWord")
    for fw in FW.objects.all():
        if fw.direction == "INBOUND":
            fw.boundaries = ["query"]
        elif fw.direction == "OUTBOUND":
            fw.boundaries = ["answer"]
        else:  # BOTH or empty
            fw.boundaries = ["query", "answer"]
        fw.save(update_fields=["boundaries"])

class Migration(migrations.Migration):
    dependencies = [...]
    operations = [
        migrations.AddField(...),  # pattern_type
        migrations.AddField(...),  # boundaries (default=[])
        migrations.AddField(...),  # embedding_threshold
        migrations.AlterField(...), # word max_length 240
        migrations.RunPython(migrate_direction_to_boundaries, migrations.RunPython.noop),
    ]
```

ModerationLog도 동일하게:
- INBOUND → boundary=query
- OUTBOUND → boundary=answer

### B.3 filter.py 리팩토링

```python
def apply(text, *, boundary: str, user=None, chat=None, dry_run: bool = False) -> ModerationResult:
    """
    boundary: "upload" | "query" | "retrieval" | "answer"
    dry_run: True면 ModerationLog 기록 안 함 (admin 테스트 패널용)
    """
    rules = ForbiddenWord.objects.filter(is_active=True, boundaries__contains=[boundary])
    # ... pattern_type 분기:
    #   KW  → 기존 substring 매칭
    #   RE  → re.finditer 매칭
    #   EMB → embedding cosine (Phase C에서 구현, 지금은 raise NotImplementedError or skip)

    # severity 처리 (BLOCK → MASK → WARN) 기존과 동일
    if not dry_run:
        # ModerationLog 기록 (boundary 포함)
        ...
    return result
```

기존 호출처 (`chat/views.py` 등)에서 `source=INBOUND` → `boundary="query"`, `source=OUTBOUND` → `boundary="answer"`로 교체.

### B.4 Admin UI 업데이트

`moderation/admin.py`:
- `list_display`에 `pattern_type`, `boundaries`, `fired_count` 추가
- `list_filter`에 `pattern_type`, `boundaries`, `severity`
- inline 편집: pattern_type을 KW에서 RE로 바꿀 때 word 필드 검증 (정규식 컴파일)

### B.5 테스트

```python
class FilterBoundaryTest(TestCase):
    def test_query_boundary_only(self):
        FW.objects.create(word="비밀", pattern_type="KW", boundaries=["query"], severity="BLOCK")
        with self.assertRaises(BlockedByModerationError):
            apply("비밀이야", boundary="query")
        # answer boundary는 통과
        r = apply("비밀이야", boundary="answer")
        assert not r.blocked

    def test_dry_run_no_log(self):
        FW.objects.create(word="원가", pattern_type="KW", boundaries=["answer"], severity="MASK")
        before = ModerationLog.objects.count()
        apply("원가는 1000원", boundary="answer", dry_run=True)
        assert ModerationLog.objects.count() == before

    def test_regex_pattern(self):
        FW.objects.create(word=r"\d{4}-\d{4}", pattern_type="RE",
                          boundaries=["query"], severity="MASK")
        r = apply("연락처는 1234-5678", boundary="query")
        assert "[REDACTED]" in r.sanitized
```

### B.6 Phase B Exit Criteria
- [ ] migration 적용, 기존 데이터 무손실 + boundaries 자동 채움
- [ ] `python manage.py shell` 에서 `ForbiddenWord.objects.first().boundaries`가 list
- [ ] dry_run=True 호출이 ModerationLog 0행 생성
- [ ] pattern_type=RE 룰이 정상 매칭
- [ ] 기존 chat 파이프라인이 새 시그너처로 호출 (`boundary="query"`)
- [ ] commit: `feat(moderation): Phase B — pattern_type + 4 boundaries + dry_run`

---

## Phase C — Presidio PII + 한국 recognizer

> **목표**: 진짜 PII 보호. 한국 주민번호·전화·계좌·신용카드를 regex/체크섬으로.
> **Spec 참조**: §3.1 Layer 3 · §4.4

### C.1 의존성

`backend/requirements.txt` 추가:
```
presidio-analyzer~=2.2
presidio-anonymizer~=2.2
```

spaCy 한국어 모델:
```bash
python -m spacy download ko_core_news_md
# 또는 가벼운 다국어:
python -m spacy download xx_ent_wiki_sm
```

### C.2 한국 recognizer 정의

`moderation/presidio_recognizers.py` (신규):
```python
from presidio_analyzer import PatternRecognizer, Pattern

KR_RRN = PatternRecognizer(
    supported_entity="KR_RRN",
    patterns=[Pattern(name="rrn",
                     regex=r"\b\d{6}[-]?[1-4]\d{6}\b", score=0.9)],
    supported_language="ko",
)

KR_PHONE = PatternRecognizer(
    supported_entity="KR_PHONE",
    patterns=[Pattern(name="phone",
                     regex=r"\b01[016-9][-]?\d{3,4}[-]?\d{4}\b", score=0.85)],
    supported_language="ko",
)

KR_ACCOUNT = PatternRecognizer(
    supported_entity="KR_ACCOUNT",
    patterns=[Pattern(name="account",
                     regex=r"\b\d{3,6}[-]\d{2,6}[-]\d{2,8}\b", score=0.6)],
    supported_language="ko",
)

CARD = PatternRecognizer(
    supported_entity="CREDIT_CARD",
    patterns=[Pattern(name="card_loose",
                     regex=r"\b(?:\d[ -]?){13,19}\b", score=0.4)],
    supported_language="ko",
)  # Luhn 체크는 별도 함수로 보정 (score ↑)


def build_analyzer():
    from presidio_analyzer import AnalyzerEngine
    engine = AnalyzerEngine(supported_languages=["ko"])
    engine.registry.add_recognizer(KR_RRN)
    engine.registry.add_recognizer(KR_PHONE)
    engine.registry.add_recognizer(KR_ACCOUNT)
    engine.registry.add_recognizer(CARD)
    return engine
```

### C.3 filter.py 통합

`moderation/filter.py`:
```python
from .presidio_recognizers import build_analyzer

_ANALYZER = None
def _get_analyzer():
    global _ANALYZER
    if _ANALYZER is None:
        _ANALYZER = build_analyzer()
    return _ANALYZER

def apply(text, *, boundary, user=None, chat=None, dry_run=False):
    # ... 기존 ForbiddenWord 로직 (Phase B에서 추가됨)

    # Presidio PII 매칭 (별도 카테고리 "PII"로 통합)
    analyzer = _get_analyzer()
    pii_results = analyzer.analyze(text=text, language="ko",
                                   entities=["KR_RRN","KR_PHONE","KR_ACCOUNT","CREDIT_CARD"])
    if pii_results:
        # 마스킹 처리 + ModerationLog
        for hit in pii_results:
            text = text[:hit.start] + f"[{hit.entity_type}]" + text[hit.end:]
        # log 기록 (boundary, action=MASKED, category="PII")
```

### C.4 시드 데이터

`seed_demo.py` 또는 신규 `seed_moderation_v2.py`:
- 한국 코드네임 KW 10+ (`Project Titan-K`, `M&A-Phoenix` 등 가상)
- 욕설 KW 30+ (한국어 — 형식적 리스트는 별도 yaml 권장)
- PII는 Presidio가 처리 (시드 불필요)
- 자체 카테고리 (경쟁사) 유지

### C.5 테스트

`moderation/tests/test_pii.py`:
```python
class KoreanPIITest(TestCase):
    def test_rrn_detected(self):
        result = apply("내 정보는 901101-1234567 이야", boundary="query")
        assert "[KR_RRN]" in result.sanitized
        assert not result.blocked  # MASK이므로 통과

    def test_phone_detected(self):
        result = apply("연락처 010-1234-5678", boundary="query")
        assert "[KR_PHONE]" in result.sanitized

    def test_no_false_positive(self):
        result = apply("배송번호는 123-456 입니다", boundary="query")
        # 일반 숫자는 잡지 않음
        assert "[KR_RRN]" not in result.sanitized
```

### C.6 Phase C Exit Criteria
- [ ] `pip install -r requirements.txt` 성공
- [ ] `python -m spacy download ko_core_news_md` 성공
- [ ] `KoreanPIITest` 모두 통과
- [ ] `apply("내 정보는 901101-1234567", boundary="query")`가 KR_RRN 마스킹 (learn.md § 8.2 실험 통과)
- [ ] 시드 데이터 추가됨 (`seed_demo`에서 `ForbiddenWord.objects.count() >= 50`)
- [ ] commit: `feat(moderation): Phase C — Presidio + Korean PII recognizers + seed v2`

---

## Phase D — UI 통합 (frontend) · 별도 plan

`[수정됨·N건]` ribbon · admin 운영자 UI · upload sensitivity dropdown 은 frontend 작업. 본 plan 범위 밖. Streamlit 작업 분리:
- `Rag_Chat/frontend/pages/admin_moderation.py` (신규)
- `Rag_Chat/frontend/chat.py`에 citation ribbon redacted badge 통합
- mockup: [../../../docs/design/preview.html](../../../docs/design/preview.html) 09 섹션 + 05 섹션

---

## 5. Risks · 미리 예상되는 함정

| 리스크 | 영향 | 완화 |
|--|--|--|
| Presidio 의존성 대형 (spaCy 모델 ~700MB) | Docker image 비대 | multi-stage build · 모델은 별도 volume |
| 한국 PII regex false positive | 배송번호 등이 RRN으로 잡힘 | Luhn-like 체크섬 보정 함수 · confidence score |
| 마이그레이션 중 데이터 일관성 깨짐 | Phase B 마이그레이션에서 direction → boundaries 변환 누락 | RunPython + 검증 query `assert all(fw.boundaries for fw in FW.objects.all())` |
| 기존 chat/views.py가 source= 시그너처에 의존 | Phase B 후 깨짐 | grep으로 모든 호출처 찾아 `boundary=` 변환 — sed/script |
| restricted 사용자 별도 인덱스 결정 미룸 | Phase A에서 임시로 같은 vector store 사용 | 인덱싱 차단으로 회피 — 결정 사항 명시화 |

---

## 6. Rollback 계획

각 phase 별로:
- Phase A: migration revert (`./manage.py migrate knowledge 0NNN-1 ; ./manage.py migrate chat 0NNN-1`). 데이터 손실 없음 (필드 drop만)
- Phase B: migration revert 가능하나 direction/boundaries 정보가 한쪽만 남음 → A 전 백업 권장
- Phase C: requirements 롤백 + filter.py 이전 버전 복원

Postgres prod 환경에서는:
- migration apply 전 `pg_dump` 백업
- staging에서 phase 전체 dry-run

---

## 7. Cross-link

| 문서 | 역할 |
|--|--|
| [spec](../specs/2026-05-28-moderation-architecture.md) | 결정의 근거 |
| [learn.md](../../features/moderation/learn.md) | 학습 노트 |
| [references.md](../../features/moderation/references.md) | 외부 도구·문서 |
| [security.md](../../architecture/security.md) | 보안 일반 (Phase 1 = keyword-only) |
| [DESIGN.md](../../../../DESIGN.md) | UI 단일 출처 |
| [docs/design/preview.html](../../../docs/design/preview.html) | UI mockup |
