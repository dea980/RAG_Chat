# Chunk Lab — 청크 미리보기 페이지 (작업 기록)

> `chunk_testing_page.md` 의 설계 중 **Streamlit 페이지 + 미리보기 API** 부분을
> 구현. 임베딩/저장 없이 splitter 결과만 비교할 수 있다.

---

## 1. 추가된 파일

```
backend/chat/ingest_views.py                       # 미리보기 API view
backend/chat/ingest/loaders/text/__init__.py       # 분류 1 진입
backend/chat/ingest/loaders/text/txt.py            # TXT/MD loader (encoding fallback)
frontend/pages/chunk_lab.py                        # Streamlit multipage 페이지
```

## 2. 수정된 파일

```
backend/chat/ingest/loaders/__init__.py            # text 패키지 side-effect import
backend/chat/urls.py                               # /ingest/preview/ 경로 추가
```

## 3. 새 엔드포인트

`POST /api/v1/triple/ingest/preview/`

**Body** (form-data 또는 JSON):

| 키 | 필수 | 설명 |
|---|---|---|
| `text` | text 또는 file | 인라인 텍스트 |
| `file` | text 또는 file | multipart 업로드 (csv/xlsx/txt/md) |
| `chunk_size` | 선택 | default 500 |
| `chunk_overlap` | 선택 | default 100 |
| `splitter` | 선택 | `recursive` (default) / `row` |

**Response 200**:
```json
{
  "source": "test.txt",
  "splitter": "recursive",
  "chunk_size": 500,
  "chunk_overlap": 100,
  "num_chunks": 9,
  "total_chars": 4500,
  "min_length": 440,
  "max_length": 500,
  "avg_length": 500,
  "chunks": [
    {"content": "...", "length": 500, "section": null, "chunk_index": 0},
    ...
  ]
}
```

**중요 — 저장·임베딩 없음:**
- 업로드된 파일은 `tempfile.NamedTemporaryFile` 로 임시 저장 → loader 통과
  → 즉시 unlink. 디스크에 영구 저장되지 않음.
- Chroma 에 적재되지 않음 → API key 불필요 → 사내 기밀 문서도 안전하게
  실험 가능.

## 4. Streamlit 페이지 사용법

### Docker compose (권장)
```bash
cd Rag_Chat && docker compose up -d
# → http://localhost:8501 의 사이드바에서 "chunk_lab" 페이지 선택
```

Frontend 컨테이너는 `BACKEND_URL=http://backend:8000` (docker network) 자동 주입.
호스트 expose 는 backend 8002 / frontend 8501.

deps 추가 시 (예: streamlit-extras) frontend 만 재빌드:
```bash
docker compose up -d --build frontend
```

### 호스트 실행 (개발용, Docker 안 쓰는 경우)
```bash
cd Rag_Chat/backend && venv/bin/python manage.py runserver 8001
# 다른 터미널
cd Rag_Chat/frontend
BACKEND_URL=http://localhost:8001 streamlit run app.py
```

`chunk_lab.py` 는 `os.getenv("BACKEND_URL", "http://localhost:8001") + "/api/v1/triple"`
— 다른 페이지와 env 키 통일 (이전엔 `API_BASE_URL` 만 봐서 불일치).

UI 흐름:
1. 좌측 사이드바에서 텍스트 붙여넣기 또는 파일 업로드
2. splitter 선택 (recursive / row)
3. 비교할 컬럼 수 (1~4) + 각 컬럼의 chunk_size / chunk_overlap 설정
4. **청킹 실행** → 각 컬럼에 청크 수·길이 통계·길이 분포 차트·청크 개별 미리보기

검증 결과:
```
size=100 → 25 chunks, avg=99 min=80 max=100
size=300 →  8 chunks, avg=267 min=40 max=300
size=800 →  3 chunks, avg=680 min=440 max=800
```

청크 사이즈가 줄수록 청크 수↑, max 가 안정적인 반면 min 이 떨어진다
(마지막 청크 잔여). 7강 강사가 200/500/1000 으로 손으로 바꿔가며 보던
것을 한 화면에서.

## 5. TXT loader

다중 인코딩 fallback (UTF-8 → CP949 → EUC-KR → errors=replace). 한국어
윈도우 파일도 통과. 확장자 `.txt`, `.md` 등록.

```python
@register
class TxtLoader:
    extensions = (".txt", ".md")
    source_type = "txt"
```

CSV/XLSX 와 달리 파일 전체를 단일 RawDoc 으로 반환하고, 청킹은 splitter
가 담당. 그래야 chunk_size 비교가 의미 있어진다.

## 6. 안 한 것 (의도적)

- **임베딩 비교** — 이 페이지는 splitter 결과만. 임베딩 모델 A/B 는
  별도 트랙 (`chunk_testing_page.md` 참조).
- **검색 정확도 측정** — 임베딩 + 검색이 필요해 다음 단계.
- **PDF 미리보기** — Phase 3 PDF loader 들어오면 자동 지원.
- **세션/권한 체크** — 저장이 없으므로 anonymous 허용. Phase 8 에서 권한
  추가 시 같이 결정.
- **CSRF token** — DRF APIView 가 처리. CSRF middleware 통과.

## 7. 학습 메모

- **저장 안 하는 미리보기 분리의 가치**: 같은 ingest layer 재사용이지만
  sink 를 쓰지 않으면 API key/권한/dedup 부담이 0. 빠른 실험 도구.
- **multipart vs JSON 동시 받기**: `parser_classes = [MultiPartParser, JSONParser]`
  로 file upload + plain text 모두 한 엔드포인트에서 처리.
- **Streamlit multipage**: `pages/<name>.py` 두면 자동으로 사이드바
  네비게이션. main `app.py` 변경 불필요.
- **`SERVER_NAME='localhost'`**: DEBUG=False + ALLOWED_HOSTS 환경에서
  Django test client 가 testserver 호스트로 가면 400. 실 서버는 영향 없음.

## 8. UI 리팩토링 (2026-05-27 오후)

기본 Streamlit 컴포넌트 (`st.bar_chart`, `st.expander` 스택, `st.dataframe`) 가
정보 밀도는 높지만 시각적으로 둔탁해서 외부 라이브러리로 교체.

| 영역 | Before | After |
|---|---|---|
| 헤더 | `st.title` | `streamlit_extras.colored_header` |
| 비교 요약 | `st.dataframe` | `st_aggrid.AgGrid` — 정렬·필터 + min/avg/max 셀 히트맵 (JsCode) |
| 길이 분포 | `st.bar_chart` per column | Plotly overlay 히스토그램 (config 색상별 비교) |
| 컬럼별 메트릭 | `st.metric` | `streamlit_extras.style_metric_cards` (보더/그림자) |
| 청크 미리보기 | `st.expander × N` | `st.tabs` + AgGrid (정렬/필터/셀 클릭 확장) |

추가 deps (`frontend/requirements.txt`):
```
streamlit-extras>=0.4.0
streamlit-aggrid>=1.0.0
plotly>=5.18.0
```

Docker 컨테이너는 `docker compose up -d --build frontend` 로 재빌드 필요.

## 9. Connection refused 디버깅 메모

증상: chunk_lab UI 가 모든 컬럼에 `HTTPConnectionPool(host='localhost', port=8000): Failed to establish a new connection: [Errno 111]`.

진단 (3 layers):
1. `chunk_lab.py` 초판이 `API_BASE_URL` env (다른 페이지는 `BACKEND_URL`) 만 봐서 env 키 불일치. 미설정 시 `localhost:8000` 하드코딩.
2. Docker compose 내부에서 frontend 컨테이너 → `localhost:8000` → 컨테이너 자기 자신. backend 없음 → ECONNREFUSED.
3. 호스트 8000 포트는 별개 uvicorn (api.main:app). backend 는 컨테이너 안 (port 8000) + 호스트 8002 expose.

해결:
- `chunk_lab.py` env var 을 `BACKEND_URL` 로 통일.
- Docker compose 가 `BACKEND_URL=http://backend:8000` 자동 주입 → docker network 의 backend service 로 정상 호출.

학습 포인트:
- **컨테이너의 `localhost` 는 컨테이너 자기 자신.** 호스트 서비스 호출 안 됨. Mac/Docker Desktop 에선 `host.docker.internal` 또는 docker network service name.
- **env var 이름 일관성.** 페이지마다 다른 키 쓰면 *어떤 환경에선 동작·다른 환경에선 안 됨* 의 디버깅 지옥.
