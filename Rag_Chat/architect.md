graph TB
    subgraph "사용자 환경"
        User(("사용자"))
        UI["Streamlit 프론트엔드\n(frontend 서비스, :8501)"]
    end

    subgraph "백엔드 (Django)"
        API["REST API / RAG 파이프라인\n(backend 서비스, :8000)"]
        Celery["Celery 워커\n(celery 서비스)"]
    end

    subgraph "저장소"
        Redis[("Redis\n(redis:6379)")]
        Chroma[("ChromaDB\n(vector_store)")]

        subgraph "SQLite"
            SQLiteDB[("SQLite DB\n(sqlite_data 볼륨)")]
        end
    end

    subgraph "외부 서비스"
        Gemini[("Google Gemini API")]
    end

    User --> UI
    UI --> |HTTP 요청| API
    API --> |세션/메시지 기록| Redis
    API --> |질문 컨텍스트 검색| Chroma
    API --> |메타데이터/로그| SQLiteDB
    API --> |임베딩·응답 생성| Gemini
    Celery --> |비동기 작업| Redis
    Celery --> |백엔드 코드 공유| API
