graph TB
    subgraph "사용자 환경"
        User(("사용자<br/>USER / MANAGER / ADMIN"))
        UI["Streamlit 프론트엔드<br/>(frontend 서비스, :8501)"]
    end

    subgraph "백엔드 (Django)"
        Mw["AuditLogMiddleware<br/>모든 호출 기록"]
        API["REST API / RAG 파이프라인<br/>chat 앱 (:8000)"]
        Mod["Moderation Filter<br/>BLOCK / MASK / WARN"]
        KB["Knowledge API<br/>Department / Contact / Product"]
        Admin["Django Admin<br/>금지어 검수 페이지"]
        Health["/health/, /health/ready/"]
        Celery["Celery worker + beat"]
    end

    subgraph "저장소"
        Redis[("Redis 7<br/>(redis:6379)<br/>session + broker")]
        Chroma[("ChromaDB / FAISS<br/>(vector_store)")]
        Postgres[("PostgreSQL 16<br/>(postgres:5432)<br/>+ ModerationLog<br/>+ AuditLog")]
    end

    subgraph "외부 서비스"
        Gemini[("Google Gemini API")]
        Qwen[("Qwen API (experimental)")]
        Ollama[("Ollama / vLLM<br/>(Stage 2/3, 사내 호스팅)")]
    end

    User --> UI
    UI --> |HTTP 요청| Mw
    Mw --> API
    Mw --> KB
    Mw --> Health
    API --> |INBOUND| Mod
    Mod --> |sanitized| Gemini
    Mod --> |sanitized| Qwen
    Mod -. "향후" .-> Ollama
    API --> |OUTBOUND| Mod
    API --> |세션/메시지 기록| Redis
    API --> |질문 컨텍스트 검색| Chroma
    API --> |메타데이터/로그| Postgres
    KB --> Postgres
    Mod --> |ModerationLog| Postgres
    Mw --> |AuditLog| Postgres
    Celery --> |비동기 작업| Redis
    Celery --> |백엔드 코드 공유| API
    Admin --> Postgres
