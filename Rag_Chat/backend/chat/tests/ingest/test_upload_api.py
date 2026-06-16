import os
from unittest.mock import patch

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from chat.ingest.base import WriteResult


class IngestUploadAPITests(APITestCase):
    @patch("chat.ingest.sinks.chroma.ChromaSink.write")
    def test_upload_txt_file_returns_processed_result(self, mock_write):
        mock_write.return_value = WriteResult(count=1, ids=["chunk-1"])
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
        mock_write.assert_called_once()

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
