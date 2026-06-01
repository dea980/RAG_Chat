"""Persona × audience_tier ACL — unit + integration tests.

설계: backend/docs/learning/2026-05-29-persona-security-design.md
구현: chat/persona.py · chat/utils.py::_pgvector_search · pipeline.py
"""
import pytest
from django.test import TestCase

from chat.persona import (
    Persona,
    tiers_for_persona,
    chroma_filter_for_persona,
    detect_query_intent_tiers,
    is_escalation,
    prompt_style_for_persona,
)
from chat.ingest.sinks.chroma import infer_tier
from chat.models import EscalationAttempt, User


class TestTierMapping(TestCase):
    """경로 → tier 매핑 (infer_tier)."""

    def test_public_path(self):
        assert infer_tier("data/corpus/public/specs.csv") == "public"

    def test_retail_path(self):
        assert infer_tier("data/corpus/retail/kr_pricing.csv") == "retail"

    def test_b2b_path(self):
        assert infer_tier("data/corpus/b2b/knox.csv") == "b2b"

    def test_competitive_path(self):
        assert infer_tier("data/corpus/competitive/iphone.csv") == "competitive"

    def test_carrier_path(self):
        assert infer_tier("data/corpus/carrier/pricing.csv") == "carrier"

    def test_internal_path_returns_none(self):
        """internal_only 는 인덱싱 차단 — None 반환."""
        assert infer_tier("data/corpus/internal/margin.csv") is None

    def test_samples_fallback_to_public(self):
        """기존 samples/ 는 public 호환."""
        assert infer_tier("data/samples/galaxy_lineup.csv") == "public"

    def test_unknown_path_fallback(self):
        """매핑 없는 경로는 public fallback."""
        assert infer_tier("random/path/file.csv") == "public"


class TestPersonaTiers(TestCase):
    """persona → tiers 매트릭스."""

    def test_p1_retail_tiers(self):
        tiers = tiers_for_persona(Persona.P1_RETAIL)
        assert "public" in tiers
        assert "retail" in tiers
        assert "carrier" in tiers
        assert "b2b" not in tiers
        assert "competitive" not in tiers
        assert "internal_only" not in tiers

    def test_p2_b2b_tiers(self):
        tiers = tiers_for_persona(Persona.P2_B2B)
        assert "b2b" in tiers
        assert "competitive" not in tiers
        assert "carrier" not in tiers

    def test_p3_hq_tiers(self):
        """본사 = 가장 넓은 권한 (internal_only 제외 전부)."""
        tiers = tiers_for_persona(Persona.P3_HQ)
        assert set(tiers) == {"public", "retail", "b2b", "competitive", "carrier"}

    def test_p4_outbound_tiers(self):
        tiers = tiers_for_persona(Persona.P4_OUTBOUND)
        assert "carrier" in tiers
        assert "b2b" not in tiers
        assert "competitive" not in tiers

    def test_none_persona_fallback(self):
        """미할당 → 가장 보수적."""
        assert tiers_for_persona(None) == ("public", "retail")

    def test_no_persona_has_internal(self):
        """어떤 persona 도 internal_only 접근 못 함."""
        for p in [None, Persona.P1_RETAIL, Persona.P2_B2B, Persona.P3_HQ, Persona.P4_OUTBOUND]:
            assert "internal_only" not in tiers_for_persona(p)


class TestChromaFilter(TestCase):
    """chroma_filter_for_persona — search filter 형식."""

    def test_filter_shape(self):
        f = chroma_filter_for_persona(Persona.P1_RETAIL)
        assert "audience_tier" in f
        assert "$in" in f["audience_tier"]
        assert isinstance(f["audience_tier"]["$in"], list)

    def test_filter_excludes_internal(self):
        for p in [None, Persona.P1_RETAIL, Persona.P2_B2B, Persona.P3_HQ, Persona.P4_OUTBOUND]:
            f = chroma_filter_for_persona(p)
            assert "internal_only" not in f["audience_tier"]["$in"]


class TestEscalationDetection(TestCase):
    """is_escalation — 키워드 기반 권한 위반 탐지."""

    def test_p1_knox_query_escalates(self):
        """P1 매장이 b2b 키워드 → escalation."""
        esc, detected, allowed = is_escalation("Knox Vault EAL4", "P1_RETAIL")
        assert esc is True
        assert "b2b" in detected

    def test_p1_margin_query_escalates(self):
        """P1 매장이 internal_only 키워드 → escalation."""
        esc, detected, _ = is_escalation("이번달 마진율", "P1_RETAIL")
        assert esc is True
        assert "internal_only" in detected

    def test_p1_iphone_query_escalates(self):
        """P1 매장이 competitive 키워드 → escalation."""
        esc, detected, _ = is_escalation("iPhone 16 카메라", "P1_RETAIL")
        assert esc is True
        assert "competitive" in detected

    def test_p1_normal_query_no_escalation(self):
        esc, detected, _ = is_escalation("S25 Ultra 카메라 스펙", "P1_RETAIL")
        assert esc is False
        assert detected == []

    def test_p3_iphone_no_escalation(self):
        """본사는 competitive 접근 가능 — escalation 아님."""
        esc, detected, allowed = is_escalation("iPhone 16 카메라", "P3_HQ")
        assert esc is False
        assert "competitive" in detected
        assert "competitive" in allowed


class TestPromptStyle(TestCase):
    """prompt_style_for_persona — 페르소나별 답변 가이드 문자열."""

    def test_each_persona_has_distinct_style(self):
        p1 = prompt_style_for_persona(Persona.P1_RETAIL)
        p2 = prompt_style_for_persona(Persona.P2_B2B)
        p3 = prompt_style_for_persona(Persona.P3_HQ)
        p4 = prompt_style_for_persona(Persona.P4_OUTBOUND)
        # 4개 모두 달라야 함
        assert len({p1, p2, p3, p4}) == 4

    def test_p1_emphasizes_short_response(self):
        p1 = prompt_style_for_persona(Persona.P1_RETAIL)
        assert "1~2 문장" in p1 or "짧" in p1

    def test_p2_b2b_mentions_b2b_terms(self):
        p2 = prompt_style_for_persona(Persona.P2_B2B)
        assert "Knox" in p2 or "B2B" in p2.upper()

    def test_p4_outbound_voice_friendly(self):
        p4 = prompt_style_for_persona(Persona.P4_OUTBOUND)
        assert "음성" in p4 or "1 문장" in p4

    def test_none_returns_default(self):
        d = prompt_style_for_persona(None)
        assert "미할당" in d or "보수적" in d


class TestEscalationLogging(TestCase):
    """RetrieveModule 가 EscalationAttempt 를 자동 로깅하는지."""

    def test_log_creates_row(self):
        """직접 모델 만들어서 schema 검증."""
        user = User.objects.create(email="ea_test@test.kr", persona="P1_RETAIL")
        ea = EscalationAttempt.objects.create(
            user=user,
            from_persona="P1_RETAIL",
            requested_query="Knox 호환",
            allowed_tiers=["public", "retail", "carrier"],
            detected_tiers=["b2b"],
            decision=EscalationAttempt.Decision.REDIRECTED,
        )
        assert ea.pk is not None
        assert "Knox" in ea.requested_query
        assert "b2b" in ea.detected_tiers
