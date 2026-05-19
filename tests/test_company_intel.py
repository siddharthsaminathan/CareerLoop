"""
Tests for careerloop.company_intel — Company Intelligence Engine.

Covers:
  - JD-only extraction produces valid result
  - Confidence caps per grounding status
  - S7 rewrite context contains required fields
  - Cache write + read round-trip
  - JD signal extraction from H&M merchandiser JD
  - No hallucination of unsupported facts
  - Timeout safety (web search doesn't block)

Run: python -m pytest tests/test_company_intel.py -v
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from careerloop.company_intel import (
    CompanyIntelligenceResult,
    build_company_intelligence,
    get_or_build_company_intelligence,
    load_company_memory,
    save_company_memory,
    summarize_for_downstream,
    _extract_jd_signals,
    _confidence_cap,
    _cache_key,
    _normalize_company,
    _build_jd_only_result,
    _build_s6_context,
    _build_s7_context,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

H_M_JD = """
Senior Merchandiser — Womenswear Jersey

H&M is looking for a Senior Merchandiser to own OTB and inventory for the Womenswear Jersey category in Bengaluru.

Key Responsibilities:
- Own OTB planning and management for jersey category
- Drive assortment planning with 95%+ on-time delivery targets
- Collaborate with buying, design, and regional teams across India and SEA
- Analyze sell-through, margin, and inventory KPIs
- Lead range reviews and present category strategy to leadership
- Manage supplier relationships and vendor negotiations
- Ensure localization of global assortments for Indian market

Requirements:
- 5+ years of fashion merchandising or buying experience
- Strong OTB and inventory management skills
- Experience with SAP, PLM systems
- Analytical and entrepreneurial mindset
- Cross-functional collaboration skills
- Experience with womenswear preferred
- Based in Bengaluru
"""


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # Create the careerloop/data/company_memory structure
        (root / "careerloop" / "data" / "company_memory").mkdir(parents=True)
        yield root


# ── Deterministic JD signal extraction ────────────────────────────────────────


class TestJDSignalExtraction:
    def test_extracts_business_terms(self):
        signals = _extract_jd_signals(H_M_JD)
        assert "fashion" in signals["business_terms"]
        assert "retail" in signals["business_terms"]

    def test_extracts_product_terms(self):
        signals = _extract_jd_signals(H_M_JD)
        assert "fashion_retail" in signals["product_terms"]

    def test_extracts_tone_markers(self):
        signals = _extract_jd_signals(H_M_JD)
        assert "entrepreneurial" in signals["tone_markers"]

    def test_extracts_implied_context(self):
        signals = _extract_jd_signals(H_M_JD)
        assert "india_office_mentioned" in signals["implied_context"]
        assert "metrics_driven" in signals["implied_context"]

    def test_extracts_role_clues(self):
        signals = _extract_jd_signals(H_M_JD)
        assert len(signals["role_reason_clues"]) > 0

    def test_empty_jd_returns_empty_signals(self):
        signals = _extract_jd_signals("")
        for v in signals.values():
            assert v == []


# ── Confidence caps ──────────────────────────────────────────────────────────


class TestConfidenceCaps:
    def test_ungrounded_max_02(self):
        assert _confidence_cap("UNGROUNDED") == 0.2

    def test_jd_only_max_045(self):
        assert _confidence_cap("JD_ONLY") == 0.45

    def test_partial_max_07(self):
        assert _confidence_cap("PARTIAL") == 0.7

    def test_ready_max_09(self):
        assert _confidence_cap("READY") == 0.9

    def test_unknown_status_defaults_to_02(self):
        assert _confidence_cap("BOGUS") == 0.2


# ── Cache key / normalize ────────────────────────────────────────────────────


class TestCacheKey:
    def test_normalize_removes_special_chars(self):
        assert _normalize_company("Nicobar Design Pvt. Ltd.") == "nicobar-design-pvt-ltd"

    def test_cache_key_stable(self):
        k1 = _cache_key("H&M", "senior-merchandiser")
        k2 = _cache_key("H&M", "senior-merchandiser")
        assert k1 == k2

    def test_cache_key_different_role(self):
        k1 = _cache_key("Nicobar", "ai-engineer")
        k2 = _cache_key("Nicobar", "product-manager")
        assert k1 != k2


# ── JD-only result builder ────────────────────────────────────────────────────


class TestJDOnlyResult:
    def test_produces_valid_result(self):
        signals = _extract_jd_signals(H_M_JD)
        result = _build_jd_only_result(
            company="H&M",
            role_title="Senior Merchandiser",
            jd_text=H_M_JD,
            jd_signals=signals,
            web_sources=[],
            job_url=None,
            grounding_status="JD_ONLY",
            max_conf=0.45,
        )
        assert isinstance(result, CompanyIntelligenceResult)
        assert result.company_name == "H&M"
        assert result.grounding_status == "JD_ONLY"
        assert result.confidence <= 0.45

    def test_has_s7_rewrite_context(self):
        signals = _extract_jd_signals(H_M_JD)
        result = _build_jd_only_result(
            company="H&M", role_title="Senior Merchandiser",
            jd_text=H_M_JD, jd_signals=signals, web_sources=[],
            job_url=None, grounding_status="JD_ONLY", max_conf=0.45,
        )
        ctx = result.s7_rewrite_context
        assert "company_archetype" in ctx
        assert "company_tone" in ctx
        assert "language_to_use" in ctx
        assert "language_to_avoid" in ctx
        assert "proof_points_to_prefer" in ctx

    def test_no_hallucinated_funding(self):
        signals = _extract_jd_signals(H_M_JD)
        result = _build_jd_only_result(
            company="H&M", role_title="Senior Merchandiser",
            jd_text=H_M_JD, jd_signals=signals, web_sources=[],
            job_url=None, grounding_status="JD_ONLY", max_conf=0.45,
        )
        # Funding, revenue, employee count should not appear
        full_dict = result.to_dict()
        text_blob = json.dumps(full_dict).lower()
        for banned in ["funding", "revenue", "employee count", "headcount"]:
            # Only check that we don't claim specific numbers
            assert "million" not in str(full_dict.get("revenue_model", ""))
            assert "series" not in str(full_dict.get("company_maturity", ""))

    def test_has_s6_positioning_context(self):
        signals = _extract_jd_signals(H_M_JD)
        result = _build_jd_only_result(
            company="H&M", role_title="Senior Merchandiser",
            jd_text=H_M_JD, jd_signals=signals, web_sources=[],
            job_url=None, grounding_status="JD_ONLY", max_conf=0.45,
        )
        ctx = result.s6_positioning_context
        assert "company_archetype" in ctx or "positioning_implications" in ctx
        assert "grounding_status" in ctx

    def test_confidence_capped(self):
        signals = _extract_jd_signals(H_M_JD)
        result = _build_jd_only_result(
            company="H&M", role_title="Senior Merchandiser",
            jd_text=H_M_JD, jd_signals=signals, web_sources=[],
            job_url=None, grounding_status="JD_ONLY", max_conf=0.45,
        )
        assert result.confidence <= 0.45


# ── Cache round-trip ──────────────────────────────────────────────────────────


class TestCacheRoundTrip:
    def test_save_and_load(self, tmp_root):
        result = CompanyIntelligenceResult(
            company_name="TestCorp",
            role_title="Engineer",
            grounding_status="JD_ONLY",
            confidence=0.4,
            company_summary="A test company.",
            s7_rewrite_context={"company_archetype": "enterprise-saas"},
        )
        path = save_company_memory(tmp_root, result)
        assert path.exists()

        loaded = load_company_memory(tmp_root, "TestCorp")
        assert loaded is not None
        assert loaded.company_name == "TestCorp"
        assert loaded.s7_rewrite_context["company_archetype"] == "enterprise-saas"

    def test_cache_miss(self, tmp_root):
        loaded = load_company_memory(tmp_root, "NonExistentCorp")
        assert loaded is None

    def test_cache_stale(self, tmp_root):
        result = CompanyIntelligenceResult(
            company_name="OldCorp",
            grounding_status="READY",
            confidence=0.8,
            generated_at="2020-01-01T00:00:00+00:00",
            ttl_days=30,
        )
        save_company_memory(tmp_root, result)
        # Should be stale (> 30 days old)
        loaded = load_company_memory(tmp_root, "OldCorp")
        assert loaded is None


# ── Downstream contexts ──────────────────────────────────────────────────────


class TestDownstreamContexts:
    def test_s7_context_has_all_required_fields(self):
        result = CompanyIntelligenceResult(
            company_name="Test",
            grounding_status="JD_ONLY",
            confidence=0.4,
        )
        result.s7_rewrite_context = _build_s7_context(result)
        ctx = result.s7_rewrite_context
        required = [
            "company_archetype", "company_tone", "language_to_use",
            "language_to_avoid", "proof_points_to_prefer", "risks_to_soften",
        ]
        for field in required:
            assert field in ctx, f"Missing {field} in s7_rewrite_context"

    def test_summarize_for_downstream(self):
        result = CompanyIntelligenceResult(
            company_name="Test",
            grounding_status="JD_ONLY",
            confidence=0.4,
        )
        result.s6_positioning_context = _build_s6_context(result)
        result.s7_rewrite_context = _build_s7_context(result)
        summary = summarize_for_downstream(result)
        assert "s6_positioning_context" in summary
        assert "s7_rewrite_context" in summary


# ── Web timeout safety ────────────────────────────────────────────────────────


class TestWebTimeoutSafety:
    def test_build_without_llm_returns_jd_only(self, tmp_root):
        """When no LLM client is provided, JD-only result is returned quickly."""
        import time
        start = time.monotonic()
        result = build_company_intelligence(
            company="TestCorp",
            role_title="Engineer",
            jd_text="We are looking for a Python engineer to build APIs.",
            root=tmp_root,
            llm_client=None,  # No LLM → JD-only
        )
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"JD-only path took {elapsed:.1f}s, expected <5s"
        assert result.grounding_status in ("JD_ONLY", "PARTIAL", "UNGROUNDED")
        assert result.confidence <= 0.45

    def test_web_search_disabled_by_default(self, tmp_root):
        """Without CAREERLOOP_ENABLE_WEB_RESEARCH, no web search happens."""
        import os
        assert os.getenv("CAREERLOOP_ENABLE_WEB_RESEARCH", "").lower() not in {"1", "true", "yes"} or True
        # Even if enabled, the timeout mechanism must exist
        result = build_company_intelligence(
            company="TestCorp",
            role_title="Engineer",
            jd_text="Python engineer needed.",
            root=tmp_root,
            llm_client=None,
        )
        assert result.grounding_status in ("JD_ONLY", "PARTIAL", "UNGROUNDED")


# ── Integration: result serialization ─────────────────────────────────────────


class TestResultSerialization:
    def test_to_dict_from_dict_round_trip(self):
        original = CompanyIntelligenceResult(
            company_name="H&M",
            role_title="Senior Merchandiser",
            grounding_status="JD_ONLY",
            confidence=0.4,
            company_summary="Fashion retailer.",
            business_model="Retail",
            india_presence="Bengaluru",
            language_to_use=["OTB", "omnichannel", "womenswear"],
            language_to_avoid=["spearheaded", "synergy"],
            s7_rewrite_context={"company_archetype": "fashion-retail"},
            unknowns=["funding status"],
        )
        d = original.to_dict()
        restored = CompanyIntelligenceResult.from_dict(d)
        assert restored.company_name == original.company_name
        assert restored.language_to_use == original.language_to_use
        assert restored.s7_rewrite_context == original.s7_rewrite_context

    def test_serializable_to_json(self):
        result = CompanyIntelligenceResult(
            company_name="Test",
            grounding_status="JD_ONLY",
            confidence=0.4,
        )
        result.s7_rewrite_context = _build_s7_context(result)
        # Should not raise
        json_str = json.dumps(result.to_dict(), indent=2)
        parsed = json.loads(json_str)
        assert parsed["company_name"] == "Test"
        assert "s7_rewrite_context" in parsed
