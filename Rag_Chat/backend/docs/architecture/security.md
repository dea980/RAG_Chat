# 보안 아키텍처 — 대외비 데이터 대응

## 1. 위협 모델 (현재 시점)

이 시스템은 사내 제품/영업 데이터(부분적으로 대외비)를 다루며, 다음 위협을 우선으로 다룬다.

| 위협 | 영향 |
|------|------|
| **민감 데이터 외부 LLM 전송** | Gemini/Qwen API로 raw 컨텍스트 평문 송신 → 데이터 유출 |
| **금지어/PII 노출** | 고객명·미공개 가격·경쟁사 언급이 프롬프트/응답에 그대로 |
| **무인증 API** | `/api/v1/triple/chat/`을 누구나 호출 가능 |
| **감사 부재** | 누가 무엇을 물었는지 추적 불가 |

## 2. 다층 방어 (구현된 것)

```
사용자 요청
   │
   ▼
[1] CORS 화이트리스트     ── env-driven (CORS_ALLOWED_ORIGINS)
   │
   ▼
[2] AuditLogMiddleware    ── 모든 API 호출 → AuditLog
   │
   ▼
[3] INBOUND moderation    ── BLOCK/MASK/WARN
   │     │
   │     ├─ BLOCK → 403 즉시 반환, ModerationLog.BLOCKED
   │     ├─ MASK  → 마스킹 후 통과, ModerationLog.MASKED
   │     └─ WARN  → 통과, ModerationLog.WARNED
   │
   ▼
[4] RAG retrieve → reasoning → generation (Gemini/Qwen)
   │
   ▼
[5] OUTBOUND moderation   ── 동일 정책, 응답에도 적용
   │
   ▼
응답
```

### 구현된 컨트롤

| 레이어 | 파일 | 동작 |
|--------|------|------|
| **SECRET_KEY 가드** | [settings.py](../triple_chat_pjt/settings.py) | DEBUG=0 + 기본 키 조합 booting 거부 |
| **CORS** | [settings.py](../triple_chat_pjt/settings.py) | `CORS_ALLOWED_ORIGINS` 화이트리스트만 |
| **금지어 필터** | [moderation/filter.py](../moderation/filter.py) | INBOUND/OUTBOUND 다단계 적용 |
| **검수 페이지** | [moderation/admin.py](../moderation/admin.py) | Django Admin `/admin/moderation/` |
| **감사 로그** | [audit/middleware.py](../audit/middleware.py) | 모든 mutating call 기록 |
| **세션 정합성** | [chat/redis_manager.py](../chat/redis_manager.py) | Redis TTL ↔ DB expired_datetime 단일 윈도우 |

## 3. PII / 금지어 마스킹 운영

운영자(C-Level/Admin)는 Django Admin에서:
1. `/admin/moderation/forbiddenword/` — 단어 추가, severity 설정
   - **MASK**: 고객명, 사번 같은 PII → `[REDACTED]`로 치환되어 LLM에 전송
   - **WARNING**: 경쟁사명 등 → 통과시키되 로그
   - **BLOCK**: 기밀 키워드 → 즉시 차단, LLM 호출 0
2. `/admin/moderation/moderationlog/` — 탐지 이력 검수
   - `reviewed=True` 체크박스로 관리자 확인 처리
   - `reviewer_note`에 메모 가능

### 예시 시드 (운영 시작 전)
```
# severity=MASK
김OO         → category=고객명
010-XXXX-XXXX → category=PII

# severity=WARNING
삼성전자 → category=경쟁사   (자사 비교 발언 모니터링)

# severity=BLOCK
프로젝트 X      → category=미공개 코드네임
인수합병 대상   → category=M&A 기밀
```

## 4. 로컬 LLM 전환 경로 (대외 LLM 의존 제거)

현재는 Gemini/Qwen API를 사용해 데이터가 외부로 송출된다. 대외비 등급이 올라가면 **자체 호스팅 LLM**으로 전환이 필요하다. 다행히 [provider 추상화](provider_architecture.md)가 이미 있어서, 새 provider 클래스만 추가하면 된다.

### 후보 스택

| 옵션 | 설치 | 비용/성능 |
|------|------|----------|
| **Ollama** | `ollama serve` + 모델 pull (llama3.1, qwen2.5-7b) | 단일 GPU 1대로 PoC, 로컬에서 OpenAI 호환 API 노출 |
| **vLLM** | `vllm serve <model>` | 동시 요청 처리량 큼, A100/H100 등 데이터센터 GPU 필요 |
| **사내 API gateway** | LiteLLM / Bedrock VPC 엔드포인트 | 클라우드 LLM이지만 VPC 안에서만 호출, 데이터 reside는 회사 계정 |

### Provider 추가 절차 (예: Ollama)

1. `backend/chat/providers/ollama.py` 작성
   ```python
   class OllamaReasoningProvider:
       name = "ollama"
       def __init__(self):
           from langchain_openai import ChatOpenAI
           self.model = ChatOpenAI(
               base_url=os.getenv("OLLAMA_BASE", "http://localhost:11434/v1"),
               api_key="ollama",  # placeholder
               model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
           )
   ```
2. `backend/chat/providers/manager.py`에 등록
3. `.env`에 `REASONING_PROVIDER=ollama`
4. `embedding`은 자체 호스팅이 필요하면 `sentence-transformers` 기반으로 또 한 layer 추가 (벡터스토어가 임베딩과 묶여 있으니 재인덱싱 필요)
5. CI에서 챗 응답이 더 이상 외부로 나가지 않는지 네트워크 정책으로 검증

### 마이그레이션 단계 (권장 순서)

1. **Stage 1 (현재)**: 외부 LLM + INBOUND 마스킹으로 PII 보호. 자소서 단계는 여기까지로 충분.
2. **Stage 2**: 사내 Ollama 인스턴스 PoC, 영업팀 10명 대상 베타. Gemini와 응답 품질 A/B.
3. **Stage 3**: vLLM + 멀티 GPU. 완전 사내망. Gemini provider는 fallback only.

## 5. Phase 1 모더레이션의 한계 (왜 Phase 2가 필요한가)

본 문서가 작성된 시점의 모더레이션(`moderation/filter.py` + `ForbiddenWord`)은 **keyword substring 매칭만** 한다. 첫 분기에 죽는 이유:

- **PII 보호 불가**: "주민등록번호"란 단어를 검색하는 게 아니라 `901101-1234567` 같은 **패턴**을 잡아야 한다. 현재 모델은 못 잡는다 — 잘못된 안전감만 준다.
- **4 boundary 표현 못 함**: CLAUDE.md 명세는 *업로드 · 질문 · 검색결과 · 답변* 4 군데에 다른 정책 적용 가능해야 한다. 현재는 INBOUND/OUTBOUND 2-방향뿐.
- **권한 부재**: `User`가 문서·chunk의 sensitivity 라벨로 검색을 제한할 메커니즘이 없다. retrieval은 사용자 권한 무관하게 모든 chunk를 노출한다.
- **Silent drop**: 모더레이션이 차단해도 사용자 화면에 노출되지 않는다 → "수정됨·N건"으로 가시화 필요.

→ 학습 노트와 spec/plan으로 분리:
| 문서 | 역할 |
|--|--|
| [features/moderation/learn.md](../features/moderation/learn.md) | 왜 3-layer label-based인가 — Fasoo · MS Purview · Presidio 비교 |
| [features/moderation/learn.html](../features/moderation/learn.html) | 시각 학습 페이지 |
| [features/moderation/references.md](../features/moderation/references.md) | 외부 자료 큐레이션 |
| [superpowers/specs/2026-05-28-moderation-architecture.md](../superpowers/specs/2026-05-28-moderation-architecture.md) | Phase 2 설계 spec — schema 변경, layer별 동작 |
| [superpowers/plans/2026-05-28-moderation-implementation.md](../superpowers/plans/2026-05-28-moderation-implementation.md) | Phase A → B → C 실행 plan |

### 5.1 Phase 2 한 화면 요약 (3-layer label-based)

```
Layer 1 · 업로드 경계
  Document.sensitivity 라벨 (public/internal/confidential/restricted)
  restricted → vector store 진입 차단

Layer 2 · retrieval 경계
  User.access_level ≥ chunk.sensitivity 인 chunk만 반환
  필터된 결과 → citation에 [수정됨·N건] 가시화

Layer 3 · 입출력 검사
  PII = Presidio + 한국 recognizer (KR_RRN/KR_PHONE/KR_ACCOUNT)
  대외비/코드네임/욕설 = ModerationRule (pattern_type: KW/RE/EMB · 4 boundary)
  inbound + outbound 양방향
```

자세한 schema·마이그레이션·rollback 계획은 위 spec/plan 참조.

---

## 6. 명시적으로 *아직 안 한 것*

- JWT 강제 (simplejwt는 requirements에 있지만 endpoint protection은 미적용 — Phase 1에서 강제 예정)
- 응답 스트리밍 (SSE)
- HTTPS 강제 / HSTS / SecureCookie (reverse proxy 구성과 함께 다음 단계)
- Redis AUTH / TLS
- 데이터베이스 컬럼 암호화 (Chat.response_text는 평문 — Stage 2에서 PII 컬럼 암호화 검토)
