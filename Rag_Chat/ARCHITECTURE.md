# Internal Chat System — Architecture Design
> Version 1.0 | 2026-03-25 · 본 문서는 **목표 아키텍처(v1.0)**. 현 구현 상태는 §0 참고.

---

## 0. 현재 구현 상태 (Phase 0, 2026-05-18)

본 v1.0 설계 중 **데이터 모델·정책 레이어**는 기존 `triple_chat` Django 백엔드에 통합 구현되어 있다. Next.js 프론트엔드와 분리된 monorepo로의 이관(§3 폴더 구조)은 Phase 1에서 진행 예정.

| 도메인 | v1.0 설계 (이 문서) | 현재 상태 |
|--------|-------------------|----------|
| accounts (Role) | 별도 앱 + Django auth 확장 | ✅ `chat.User.role` (USER/MANAGER/ADMIN) + `department` FK |
| knowledge (Department/Contact/Product) | `apps/knowledge/` | ✅ `backend/knowledge/` 별도 앱 + Admin CRUD + 3 검색 API |
| moderation (ForbiddenWord/필터) | `apps/moderation/` | ✅ `backend/moderation/` — BLOCK/MASK/WARN, chat pipeline에 INBOUND·OUTBOUND 연결 |
| audit (AuditLog) | `apps/audit/` + middleware | ✅ `backend/audit/` — `AuditLogMiddleware` |
| chat (ChatSession/ChatMessage) | 신규 모델 | ⏳ 기존 `chat.Chat`/`SearchLog` 유지 — v1.0 모델 마이그레이션은 Phase 1 |
| Database | PostgreSQL 16 | ✅ Postgres 1차, SQLite dev fallback |
| Auth (JWT) | `simplejwt` + NextAuth | ⏳ 의존성만 추가, endpoint protection은 Phase 1 |
| Frontend | Next.js 14 + Tailwind + shadcn/ui | ❌ 현재 Streamlit 유지 (Phase 1 이관) |
| Container | Docker Compose | ✅ Postgres + Redis + backend + Celery + Streamlit |
| CI | (미정의) | ✅ GitHub Actions — lint / pg-redis 테스트 / chunk A/B / Docker build |

### 차이 요약
- **단일 백엔드 통합**: v1.0은 `internal-chat/` 별도 monorepo였으나, 현 구현은 `Rag_Chat/backend/`에 새 앱 4개를 추가하는 형태. Streamlit과 공존.
- **frontend 미이관**: Streamlit이 그대로 사용자 진입점. Phase 1에서 Next.js로 단계적 교체.
- **JWT/RBAC 강제 보류**: 데이터 모델은 있지만 API endpoint에 권한 검사가 아직 안 걸려 있음 — 영업팀 베타에서 위험.

### 관련 산출물
- 코드: [backend/chat/](backend/chat/), [backend/knowledge/](backend/knowledge/), [backend/moderation/](backend/moderation/), [backend/audit/](backend/audit/)
- 보안 / 대외비: [backend/docs/security.md](backend/docs/security.md)
- 검증: [backend/docs/chunk_experiment.md](backend/docs/chunk_experiment.md), [backend/chat/tests/evals/](backend/chat/tests/evals/)
- 전체 PRD: [prd.html](prd.html)
- 현황 스냅샷: [프로젝트현황.md](프로젝트현황.md)

이 §0 이하의 본문은 **목표 v1.0**이며 Phase 1 작업 가이드로 사용된다. 변경 시 ↑ 표를 동기화할 것.

---

## 1. 시스템 개요

내부 임직원용 RAG 기반 AI 채팅 + 검색 시스템.
- 역할 기반 접근 제어 (C-Level / Manager / User)
- 금기어 필터링 및 감사 로그
- 제품·서비스 정보 / 부서·담당자 조회
- AI 채팅 + 키워드/벡터 검색

---

## 2. 기술 스택

| 영역 | 기술 | 이유 |
|------|------|------|
| Backend | Django 4.x + DRF | 기존 RAG 파이프라인 유지 |
| Frontend | Next.js 14 (App Router) + TypeScript | SSR, 역할별 레이아웃, 스트리밍 |
| Auth (Backend) | djangorestframework-simplejwt | JWT accessToken / refreshToken |
| Auth (Frontend) | NextAuth.js v5 | 세션 관리, 나중에 SSO 확장 |
| Database | PostgreSQL 16 | 동시 접속 안정성, SQLite 대체 |
| Cache / Session | Redis 7 | 채팅 히스토리, Celery broker |
| Background Task | Celery + Celery Beat | 세션 정리, 주기적 인덱싱 |
| Vector DB | FAISS (기존 유지) | RAG 벡터 검색 |
| LLM | Gemini / Qwen (기존 유지) | provider 추상화 유지 |
| Styling | Tailwind CSS + shadcn/ui | 빠른 UI 구성 |
| Container | Docker + Docker Compose | 로컬/프로덕션 동일 환경 |

---

## 3. 프로젝트 폴더 구조 (Monorepo)

```
internal-chat/
├── backend/                          # Django API 서버
│   ├── config/                       # 프로젝트 설정
│   │   ├── settings/
│   │   │   ├── base.py               # 공통 설정
│   │   │   ├── local.py              # 개발 환경
│   │   │   └── production.py         # 프로덕션
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── accounts/                 # 사용자·역할·인증
│   │   │   ├── models.py             # User, Department
│   │   │   ├── serializers.py
│   │   │   ├── views.py              # login, refresh, me
│   │   │   ├── permissions.py        # IsAdmin, IsManager 등
│   │   │   └── admin.py
│   │   ├── chat/                     # 채팅 (기존 파이프라인 이전)
│   │   │   ├── models.py             # ChatSession, ChatMessage
│   │   │   ├── pipeline/             # 기존 retrieve→reasoning→generation
│   │   │   │   ├── base.py
│   │   │   │   ├── modules.py        # + filter 모듈 추가
│   │   │   │   └── runner.py
│   │   │   ├── providers/            # Gemini / Qwen
│   │   │   ├── redis_manager.py
│   │   │   ├── views.py
│   │   │   └── serializers.py
│   │   ├── knowledge/                # 제품·서비스·부서 지식베이스
│   │   │   ├── models.py             # Product, Service, Department, Contact
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── rag_indexer.py        # 문서 → 벡터 인덱싱
│   │   ├── moderation/               # 금기어 관리
│   │   │   ├── models.py             # ForbiddenWord, ModerationLog
│   │   │   ├── filter.py             # 필터 로직
│   │   │   └── views.py
│   │   └── audit/                    # 감사 로그
│   │       ├── models.py             # AuditLog
│   │       └── middleware.py
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── local.txt
│   │   └── production.txt
│   ├── Dockerfile
│   └── manage.py
│
├── frontend/                         # Next.js 앱
│   ├── src/
│   │   ├── app/                      # App Router
│   │   │   ├── (auth)/               # 인증 불필요 페이지
│   │   │   │   ├── login/
│   │   │   │   └── layout.tsx
│   │   │   ├── (dashboard)/          # 일반 유저 공통
│   │   │   │   ├── layout.tsx        # 로그인 체크
│   │   │   │   ├── chat/             # AI 채팅
│   │   │   │   ├── search/           # 제품·부서 검색
│   │   │   │   └── profile/
│   │   │   ├── (manager)/            # 중간관리자+
│   │   │   │   ├── layout.tsx        # MANAGER 역할 체크
│   │   │   │   ├── team/             # 팀원 관리
│   │   │   │   └── reports/          # 채팅 리포트
│   │   │   └── (admin)/              # C-Level (ADMIN)
│   │   │       ├── layout.tsx        # ADMIN 역할 체크
│   │   │       ├── users/            # 전체 사용자 관리
│   │   │       ├── departments/      # 부서 관리
│   │   │       ├── products/         # 제품·서비스 관리
│   │   │       ├── forbidden-words/  # 금기어 관리
│   │   │       ├── rag-documents/    # RAG 문서 업로드
│   │   │       └── audit-logs/       # 전체 감사 로그
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui 기본 컴포넌트
│   │   │   ├── chat/                 # ChatWindow, MessageBubble, StreamingText
│   │   │   ├── search/               # SearchBar, ResultCard
│   │   │   └── admin/                # DataTable, StatCard
│   │   ├── lib/
│   │   │   ├── api.ts                # Django API 클라이언트
│   │   │   ├── auth.ts               # NextAuth 설정
│   │   │   └── types.ts              # 공유 TypeScript 타입
│   │   └── middleware.ts             # 역할 기반 라우팅 보호
│   ├── Dockerfile
│   ├── next.config.ts
│   └── package.json
│
├── docker-compose.yml                # 전체 서비스 오케스트레이션
├── docker-compose.dev.yml            # 개발 환경 오버라이드
├── .env.example                      # 환경변수 템플릿
└── README.md
```

---

## 4. 데이터 모델

### 4-1. accounts 앱

```python
# User (AbstractUser 확장)
class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'C-Level Admin'),
        ('MANAGER', 'Middle Manager'),
        ('USER', 'Employee'),
    ]
    role        = CharField(choices=ROLE_CHOICES, default='USER')
    department  = ForeignKey('Department', null=True, blank=True)
    employee_id = CharField(max_length=20, unique=True, null=True)
    avatar_url  = CharField(max_length=500, null=True, blank=True)
    created_at  = DateTimeField(auto_now_add=True)
    updated_at  = DateTimeField(auto_now=True)

# Department (부서)
class Department(Model):
    name        = CharField(max_length=100)
    description = TextField(blank=True)
    manager     = ForeignKey(User, null=True, related_name='managed_dept')
    parent      = ForeignKey('self', null=True, blank=True)  # 상위 부서
    created_at  = DateTimeField(auto_now_add=True)
```

### 4-2. knowledge 앱

```python
# Product (제품·서비스)
class Product(Model):
    CATEGORY_CHOICES = [('PRODUCT', '제품'), ('SERVICE', '서비스'), ('SOLUTION', '솔루션')]
    name            = CharField(max_length=200)
    category        = CharField(choices=CATEGORY_CHOICES)
    description     = TextField()
    specs           = JSONField(default=dict)      # 기술 스펙 (key-value)
    department      = ForeignKey(Department)
    contact_person  = ForeignKey(User, null=True)  # 담당자
    is_active       = BooleanField(default=True)
    created_at      = DateTimeField(auto_now_add=True)
    updated_at      = DateTimeField(auto_now=True)

# RAGDocument (벡터 인덱싱 대상)
class RAGDocument(Model):
    SOURCE_CHOICES = [('PRODUCT', '제품'), ('MANUAL', '매뉴얼'), ('FAQ', 'FAQ'), ('OTHER', '기타')]
    title       = CharField(max_length=300)
    content     = TextField()
    source_type = CharField(choices=SOURCE_CHOICES)
    source_file = CharField(max_length=500, null=True)  # 업로드 파일명
    department  = ForeignKey(Department, null=True)
    vector_id   = CharField(max_length=100, null=True)  # FAISS vector ID
    is_indexed  = BooleanField(default=False)
    uploaded_by = ForeignKey(User)
    created_at  = DateTimeField(auto_now_add=True)
```

### 4-3. chat 앱

```python
# ChatSession
class ChatSession(Model):
    user        = ForeignKey(User)
    started_at  = DateTimeField(auto_now_add=True)
    ended_at    = DateTimeField(null=True)
    is_active   = BooleanField(default=True)

# ChatMessage
class ChatMessage(Model):
    ROLE_CHOICES = [('USER', 'User'), ('ASSISTANT', 'Assistant')]
    session         = ForeignKey(ChatSession)
    role            = CharField(choices=ROLE_CHOICES)
    content         = TextField()
    is_flagged      = BooleanField(default=False)  # 금기어 탐지 여부
    flagged_words   = JSONField(default=list)       # 감지된 금기어 목록
    rag_context     = JSONField(default=dict)       # 참조한 RAG 문서
    created_at      = DateTimeField(auto_now_add=True)
```

### 4-4. moderation 앱

```python
# ForbiddenWord (금기어)
class ForbiddenWord(Model):
    SEVERITY_CHOICES = [
        ('WARNING', '경고 후 전송'),   # 경고만, 메시지 허용
        ('BLOCK', '전송 차단'),        # 메시지 차단
    ]
    word        = CharField(max_length=100, unique=True)
    category    = CharField(max_length=50)   # 예: 경쟁사, 비속어, 기밀
    severity    = CharField(choices=SEVERITY_CHOICES)
    is_active   = BooleanField(default=True)
    created_by  = ForeignKey(User)
    created_at  = DateTimeField(auto_now_add=True)

# ModerationLog (금기어 감지 기록)
class ModerationLog(Model):
    user            = ForeignKey(User)
    message         = ForeignKey(ChatMessage, null=True)
    detected_words  = JSONField()
    original_text   = TextField()
    action_taken    = CharField()   # 'WARNING' or 'BLOCKED'
    created_at      = DateTimeField(auto_now_add=True)
```

### 4-5. audit 앱

```python
# AuditLog (전체 행동 감사)
class AuditLog(Model):
    user        = ForeignKey(User, null=True)
    action      = CharField(max_length=100)  # 예: 'chat.send', 'user.create'
    resource    = CharField(max_length=100)  # 예: 'ChatMessage', 'User'
    resource_id = CharField(max_length=100, null=True)
    detail      = JSONField(default=dict)
    ip_address  = GenericIPAddressField(null=True)
    created_at  = DateTimeField(auto_now_add=True)
```

---

## 5. API 엔드포인트 설계

```
/api/v1/
│
├── auth/
│   ├── POST   login/              # { email, password } → { access, refresh }
│   ├── POST   logout/
│   ├── POST   token/refresh/      # { refresh } → { access }
│   └── GET    me/                 # 현재 로그인 사용자 정보
│
├── users/                         # ADMIN only (관리)
│   ├── GET    /                   # 전체 사용자 목록 (필터: role, department)
│   ├── POST   /                   # 사용자 생성
│   ├── GET    /{id}/
│   ├── PATCH  /{id}/
│   └── PATCH  /{id}/role/         # 역할 변경
│
├── departments/
│   ├── GET    /                   # 전체 부서 목록
│   ├── POST   /                   # ADMIN only
│   ├── GET    /{id}/
│   ├── PATCH  /{id}/              # ADMIN only
│   └── GET    /{id}/members/      # 부서 소속 멤버
│
├── products/                      # 제품·서비스 정보
│   ├── GET    /                   # 전체 (검색: name, category, department)
│   ├── POST   /                   # ADMIN/MANAGER
│   ├── GET    /{id}/
│   └── PATCH  /{id}/              # ADMIN/MANAGER
│
├── chat/
│   ├── GET    sessions/           # 내 채팅 세션 목록
│   ├── POST   sessions/           # 새 세션 시작
│   ├── GET    sessions/{id}/messages/
│   └── POST   sessions/{id}/messages/   # 메시지 전송 (RAG + 필터)
│
├── search/
│   └── POST   /                   # 통합 검색 (RAG 벡터 + 제품/부서)
│
├── moderation/                    # ADMIN only
│   ├── GET    forbidden-words/
│   ├── POST   forbidden-words/
│   ├── PATCH  forbidden-words/{id}/
│   ├── DELETE forbidden-words/{id}/
│   └── GET    logs/               # 금기어 감지 로그
│
├── rag/                           # ADMIN only
│   ├── GET    documents/
│   ├── POST   documents/upload/   # 파일 업로드 + 인덱싱 트리거
│   └── DELETE documents/{id}/
│
└── admin/
    ├── GET    audit-logs/         # 전체 감사 로그
    └── GET    stats/              # 대시보드 통계
```

---

## 6. 인증 플로우

```
[Next.js Frontend]                [Django Backend]
      │                                  │
      │  1. POST /api/v1/auth/login/      │
      │  { email, password }              │
      │ ─────────────────────────────────▶│
      │                                  │ 검증 후
      │  { access (15min),               │
      │    refresh (7days),              │
      │    user: { role, dept } }        │
      │ ◀─────────────────────────────── │
      │                                  │
      │  2. NextAuth JWT에 저장           │
      │     (httpOnly cookie)            │
      │                                  │
      │  3. 이후 모든 요청               │
      │  Authorization: Bearer <access>  │
      │ ─────────────────────────────────▶│
      │                                  │
      │  4. access 만료 시 자동 refresh  │
      │  POST /api/v1/auth/token/refresh/ │
```

---

## 7. 금기어 파이프라인 플로우

```
사용자 입력
    │
    ▼
[ForbiddenWordFilter]  ← moderation 앱
    │
    ├─ 감지 없음 ──────────────────────────────────────────▶ [retrieve]
    │                                                            │
    ├─ WARNING 감지 → ModerationLog 저장                         ▼
    │               → 경고 포함해서 계속 진행 ──────────────▶ [reasoning]
    │                                                            │
    └─ BLOCK 감지  → ModerationLog 저장                          ▼
                   → 즉시 차단 응답 반환            [generation]
                                                         │
                                               [OutputFilter]  ← AI 응답도 필터링
                                                         │
                                                      최종 응답
```

---

## 8. 역할별 접근 권한

| 기능 | USER | MANAGER | ADMIN |
|------|:----:|:-------:|:-----:|
| AI 채팅 | ✅ | ✅ | ✅ |
| 제품·부서 검색 | ✅ | ✅ | ✅ |
| 본인 채팅 히스토리 | ✅ | ✅ | ✅ |
| 팀원 관리 (본인 부서) | ❌ | ✅ | ✅ |
| 팀 채팅 리포트 | ❌ | ✅ | ✅ |
| 전체 사용자 관리 | ❌ | ❌ | ✅ |
| 부서 생성·수정 | ❌ | ❌ | ✅ |
| 제품 정보 등록 | ❌ | ✅ | ✅ |
| 금기어 관리 | ❌ | ❌ | ✅ |
| RAG 문서 업로드 | ❌ | ❌ | ✅ |
| 감사 로그 열람 | ❌ | ❌ | ✅ |
| 대시보드 통계 | ❌ | 본인 부서 | 전체 |

---

## 9. Docker Compose 서비스 구성

```yaml
services:
  postgres:     # PostgreSQL 16
  redis:        # Redis 7 (세션 + Celery broker)
  backend:      # Django API (gunicorn)
  celery:       # Celery worker
  celery-beat:  # 주기적 태스크 (세션 정리, 재인덱싱)
  frontend:     # Next.js (standalone output)
  nginx:        # 리버스 프록시 (프로덕션)
```

---

## 10. 개발 우선순위 (Phase)

### Phase 1 — 기반 인프라 (1~2주)
- [ ] Monorepo 폴더 구조 생성
- [ ] Docker Compose 세팅 (postgres, redis, backend, frontend)
- [ ] Django accounts 앱: User(역할) + Department 모델
- [ ] JWT 인증 API (login, refresh, me)
- [ ] NextAuth.js 연동 + Next.js 미들웨어 역할 보호

### Phase 2 — 핵심 기능 (2~3주)
- [ ] 기존 RAG 파이프라인 이전 (chat 앱으로)
- [ ] ForbiddenWord 모델 + filter 모듈 파이프라인 연결
- [ ] ChatSession / ChatMessage API
- [ ] 기본 채팅 UI (Next.js) + SSE 스트리밍

### Phase 3 — 지식베이스 (1~2주)
- [ ] knowledge 앱: Product, Service, RAGDocument
- [ ] 파일 업로드 + 벡터 인덱싱 API
- [ ] 통합 검색 API (벡터 + 키워드)
- [ ] 검색 UI

### Phase 4 — 관리자 기능 (2주)
- [ ] Admin 대시보드 (사용자·부서·제품 CRUD)
- [ ] 금기어 관리 UI
- [ ] 감사 로그 UI
- [ ] 통계 대시보드

---

## 11. 환경변수 목록 (.env.example)

```bash
# Django
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=internal_chat
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/internal_chat

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# LLM
GOOGLE_API_KEY=your-google-api-key
QWEN_API_KEY=your-qwen-api-key

# Next.js
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=change-me-in-production
NEXT_PUBLIC_API_URL=http://localhost:8000

# Session
SESSION_TIMEOUT=300
```
