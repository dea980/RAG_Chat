import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from chat.ingest.splitters.clause import ClauseSplitter
from chat.ingest.splitters.heading import HeadingSplitter


@patch("chat.management.commands.build_vectors.ChromaSink")
@patch("chat.management.commands.build_vectors.ingest_path", return_value=0)
def test_splitter_flag_forces_clause(mock_ingest, _mock_sink):
    call_command("build_vectors", "--splitter", "clause")
    assert mock_ingest.called
    assert isinstance(mock_ingest.call_args.kwargs["splitter"], ClauseSplitter)


@patch("chat.management.commands.build_vectors.ChromaSink")
@patch("chat.management.commands.build_vectors.ingest_path", return_value=0)
def test_splitter_flag_forces_heading(mock_ingest, _mock_sink):
    call_command("build_vectors", "--splitter", "heading")
    assert isinstance(mock_ingest.call_args.kwargs["splitter"], HeadingSplitter)


@patch("chat.management.commands.build_vectors.ChromaSink")
@patch("chat.management.commands.build_vectors.ingest_path", return_value=0)
def test_no_splitter_flag_keeps_auto_dispatch(mock_ingest, _mock_sink):
    # 플래그 없으면 splitter=None 으로 넘겨 pipeline 이 source_type 기반 자동 선택.
    call_command("build_vectors")
    assert mock_ingest.call_args.kwargs.get("splitter") is None


def test_invalid_splitter_name_rejected():
    with pytest.raises(CommandError):
        call_command("build_vectors", "--splitter", "nonsense")
