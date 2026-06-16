import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from chat.ingest import loaders  # noqa: F401
from chat.ingest.registry import registered_extensions


def test_text_document_extensions_are_registered():
    extensions = registered_extensions()

    assert ".txt" in extensions
    assert ".md" in extensions
    assert ".pdf" in extensions
    assert ".docx" in extensions
    assert ".html" in extensions
    assert ".htm" in extensions
