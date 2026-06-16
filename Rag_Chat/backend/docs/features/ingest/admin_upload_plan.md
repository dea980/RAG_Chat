# Admin Upload Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sidebar-only "Update Phone Data" button with an admin upload flow that accepts multiple knowledge files and updates the local RAG store.

**Architecture:** Add a dedicated multipart backend endpoint for file ingest, keeping the legacy `/chat-rag/` Excel button path as fallback. The Streamlit sidebar will upload multiple files, call the new endpoint, and show per-file results. The backend will save each upload to a temporary file, route by extension through the existing ingest registry/loaders where possible, split documents, persist them through the Chroma sink, and return a JSON summary.

**Tech Stack:** Django REST Framework, Streamlit, `requests`, existing `chat.ingest` loader/splitter/sink modules, Chroma vector store, pytest.

---

## File Map

- Modify: `Rag_Chat/backend/chat/ingest_views.py`
  - Add `IngestUploadAPIView` for multipart `files`.
  - Reuse existing temp-file pattern from `IngestPreviewAPIView`.
  - Return `processed` and `failed` arrays.
- Modify: `Rag_Chat/backend/chat/urls.py`
  - Register `ingest/upload/`.
- Modify: `Rag_Chat/frontend/api.py`
  - Add `upload_knowledge_files(uploaded_files)` using multipart requests.
- Modify: `Rag_Chat/frontend/app.py`
  - Replace the bare `Update Phone Data` button with `st.file_uploader(..., accept_multiple_files=True)` and `Upload & Update Knowledge`.
  - Keep a legacy no-file button path if needed.
- Test: `Rag_Chat/backend/chat/tests/ingest/test_upload_api.py`
  - Verify multi-file upload response shape and unsupported file handling.

## Supported Inputs

Initial supported extensions:

- `.xlsx`, `.xls`
- `.csv`
- `.txt`

Next extension targets after initial flow is stable:

- `.pdf`
- `.docx`
- `.html`
- `.hwp`

PDF/DOCX require adding loaders and dependencies, so they should be handled as a follow-up task unless the current environment already has the required parser packages installed.

## Task 1: Backend Upload API

**Files:**
- Modify: `Rag_Chat/backend/chat/ingest_views.py`
- Modify: `Rag_Chat/backend/chat/urls.py`
- Test: `Rag_Chat/backend/chat/tests/ingest/test_upload_api.py`

- [ ] **Step 1: Write failing upload API test**

Create `Rag_Chat/backend/chat/tests/ingest/test_upload_api.py`:

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase


class IngestUploadAPITests(APITestCase):
    def test_upload_txt_file_returns_processed_result(self):
        upload = SimpleUploadedFile(
            "sample.txt",
            b"Galaxy S25 Ultra supports a 200MP camera.",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("ingest-upload"),
            {"files": [upload]},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["processed"][0]["filename"], "sample.txt")
        self.assertEqual(response.data["processed"][0]["status"], "ok")
        self.assertGreaterEqual(response.data["processed"][0]["chunks"], 1)
        self.assertEqual(response.data["failed"], [])

    def test_upload_unsupported_file_reports_failure(self):
        upload = SimpleUploadedFile(
            "sample.bin",
            b"not supported",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            reverse("ingest-upload"),
            {"files": [upload]},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["processed"], [])
        self.assertEqual(response.data["failed"][0]["filename"], "sample.bin")
        self.assertIn("Unsupported", response.data["failed"][0]["error"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
docker compose exec -T backend pytest chat/tests/ingest/test_upload_api.py -q
```

Expected: failure because `ingest-upload` URL/view does not exist.

- [ ] **Step 3: Implement minimal upload endpoint**

In `Rag_Chat/backend/chat/ingest_views.py`, add:

```python
class IngestUploadAPIView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [AllowAny]

    def post(self, request):
        uploads = request.FILES.getlist("files")
        if not uploads:
            return Response(
                {"error": "files is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        processed = []
        failed = []

        for upload in uploads:
            suffix = os.path.splitext(upload.name)[1].lower()
            if suffix not in {".txt", ".csv", ".xlsx", ".xls"}:
                failed.append({
                    "filename": upload.name,
                    "error": f"Unsupported file extension: {suffix or '(none)'}",
                })
                continue

            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in upload.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

                chunks = ingest_uploaded_file(temp_path)
                processed.append({
                    "filename": upload.name,
                    "status": "ok",
                    "chunks": chunks,
                })
            except Exception as exc:
                failed.append({"filename": upload.name, "error": str(exc)})
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

        return Response(
            {"processed": processed, "failed": failed},
            status=status.HTTP_200_OK,
        )
```

Add a small helper in the same file first, then extract later only if needed:

```python
def ingest_uploaded_file(path: str) -> int:
    loader = loader_for(path)
    docs = list(loader.load(path))
    splitter = RecursiveSplitter()
    chunks = []
    for doc in docs:
        chunks.extend(splitter.split(doc))
    sink = ChromaSink()
    sink.write(chunks)
    return len(chunks)
```

Use actual class/function names from the existing ingest modules:

- `loader_for` from `chat.ingest.registry`
- `RecursiveSplitter` from `chat.ingest.splitters.recursive`
- `ChromaSink` from `chat.ingest.sinks.chroma`

- [ ] **Step 4: Register URL**

In `Rag_Chat/backend/chat/urls.py`, import and register:

```python
from .ingest_views import IngestPreviewAPIView, IngestUploadAPIView

path("ingest/upload/", IngestUploadAPIView.as_view(), name="ingest-upload"),
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
docker compose exec -T backend pytest chat/tests/ingest/test_upload_api.py -q
```

Expected: both tests pass. If embedding provider credentials make Chroma writes fail in test, patch `ChromaSink.write` in the test and assert it was called.

## Task 2: Frontend API Wrapper

**Files:**
- Modify: `Rag_Chat/frontend/api.py`

- [ ] **Step 1: Add upload API wrapper**

Add:

```python
def upload_knowledge_files(uploaded_files):
    """Upload one or more knowledge files to the backend ingest endpoint."""
    if not uploaded_files:
        return None

    files = [
        (
            "files",
            (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream"),
        )
        for uploaded in uploaded_files
    ]

    try:
        response = requests.post(f"{API_BASE_URL}/ingest/upload/", files=files)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to upload knowledge files: {e}")
        logger.error(f"Error uploading knowledge files: {e}")
        return None
```

- [ ] **Step 2: Manual smoke test through Streamlit after Task 3**

Expected: selecting a file and pressing the upload button calls `/ingest/upload/`.

## Task 3: Sidebar Upload UI

**Files:**
- Modify: `Rag_Chat/frontend/app.py`

- [ ] **Step 1: Import frontend wrapper**

At the top-level API imports, include:

```python
from api import fetch_user_id, get_provider_selection, set_provider_combo, upload_knowledge_files
```

- [ ] **Step 2: Replace Admin Controls button block**

Replace the old `Update Phone Data` button block with:

```python
st.sidebar.markdown("### Admin Controls")
uploaded_knowledge_files = st.sidebar.file_uploader(
    "Knowledge files",
    type=["xlsx", "xls", "csv", "txt", "pdf", "docx", "html", "hwp"],
    accept_multiple_files=True,
    help="Upload files to update the RAG knowledge store.",
)

if st.sidebar.button("Upload & Update Knowledge", disabled=not uploaded_knowledge_files):
    with st.sidebar.status("Uploading knowledge files..."):
        result = upload_knowledge_files(uploaded_knowledge_files)
        if result:
            processed = result.get("processed", [])
            failed = result.get("failed", [])
            if processed:
                st.sidebar.success(f"Processed {len(processed)} file(s).")
                st.sidebar.json(processed)
            if failed:
                st.sidebar.error(f"Failed {len(failed)} file(s).")
                st.sidebar.json(failed)
        else:
            st.sidebar.error("Failed to upload knowledge files. Please try again.")
```

- [ ] **Step 3: Keep legacy update as fallback if desired**

If keeping the old fixed Excel path is still useful, add:

```python
if st.sidebar.button("Use Bundled Phone Data"):
    with st.sidebar.status("Updating bundled phone data..."):
        if load_phone_data():
            st.sidebar.success("Bundled phone data updated successfully.")
        else:
            st.sidebar.error("Failed to update bundled phone data.")
```

## Task 4: Docker Verification

**Files:**
- No code files unless tests reveal a defect.

- [ ] **Step 1: Rebuild and start**

Run:

```bash
docker compose up --build -d
```

Expected: backend, frontend, celery, celery-beat, postgres, redis are up.

- [ ] **Step 2: Verify backend and frontend**

Run:

```bash
curl --max-time 5 -I http://localhost:8501
curl --max-time 5 -I http://localhost:8002
```

Expected:

- frontend returns `HTTP/1.1 200 OK`
- backend returns `HTTP/1.1 302 Found` or an API response

- [ ] **Step 3: Run backend upload test**

Run:

```bash
docker compose exec -T backend pytest chat/tests/ingest/test_upload_api.py -q
```

Expected: upload API tests pass.

## Scope Notes

- The first implementation should make `.txt`, `.csv`, `.xlsx`, and `.xls` work.
- The UI can list `.pdf`, `.docx`, `.html`, and `.hwp`, but unsupported backend extensions should return a per-file failure until their loaders are implemented.
- Do not change provider selection JSON UI; it is separate from knowledge upload.
- Do not remove the existing `/chat-rag/` endpoint in this task.

## Self-Review

- No placeholders remain.
- Backend, frontend, and verification tasks are covered.
- The plan keeps provider controls separate from upload controls.
- The initial backend support is intentionally narrower than the UI's future file list to avoid pretending PDF/DOCX/HWP parsing works before loaders exist.
