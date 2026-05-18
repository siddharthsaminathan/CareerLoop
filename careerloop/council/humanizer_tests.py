"""Tests for Humanizer — deterministic phases only.

These tests verify Phases 1-2 (deterministic slop detection and recruiter realism)
and the deterministic fallback path for Phases 3-4. No LLM client required.
"""
import pytest
from careerloop.council.humanizer import Humanizer, HumanizerFlag, HumanizerResult


class TestPhase1SlopDetection:
    """Phase 1: AI slop detection — deterministic."""

    def setup_method(self):
        self.h = Humanizer()  # No LLM client — deterministic only

    def test_detect_banned_word_simple(self):
        flags = self.h._detect_slop("I am passionate about leveraging AI.")
        words = [f.text.lower() for f in flags]
        assert "passionate" in words
        assert "leverage" in words or "leveraging" in words

    def test_detect_banned_word_variants(self):
        """Lemma matching: 'leveraged' and 'leveraging' should match 'leverage'."""
        flags = self.h._detect_slop("We leveraged the existing infrastructure.")
        assert len(flags) >= 1

    def test_detect_banned_word_synergy(self):
        flags = self.h._detect_slop("The synergy between teams was great.")
        assert len(flags) >= 1
        assert flags[0].category == "banned_word"

    def test_detect_banned_phrase(self):
        flags = self.h._detect_slop("I am writing to express my interest in the role.")
        assert len(flags) >= 1
        filler_flags = [f for f in flags if f.category == "filler"]
        assert len(filler_flags) >= 1
        assert any("I am writing to express" in f.text for f in filler_flags)

    def test_detect_consecutive_i_starts(self):
        text = "I built the system. I led the team. I improved metrics. I also mentored juniors."
        flags = self.h._detect_slop(text)
        cadence_flags = [f for f in flags if f.category == "cadence"]
        assert len(cadence_flags) >= 1

    def test_detect_exclamation_marks(self):
        text = "I built an amazing platform! It was great!"
        flags = self.h._detect_slop(text)
        exclamation_flags = [f for f in flags if f.text == "!"]
        assert len(exclamation_flags) == 2

    def test_clean_text_no_flags(self):
        text = "Built a real-time analytics pipeline processing 500K events/second."
        flags = self.h._detect_slop(text)
        assert len(flags) == 0

    def test_no_flags_for_normal_sentence(self):
        text = "Deployed a distributed tracing system across 12 microservices using OpenTelemetry."
        flags = self.h._detect_slop(text)
        assert len(flags) == 0


class TestPhase2RecruiterRealism:
    """Phase 2: Recruiter realism check — deterministic."""

    def setup_method(self):
        self.h = Humanizer()

    def test_metric_without_baseline(self):
        text = "Increased revenue by 150% using the new system."
        concerns = self.h._check_realism(text, [])
        assert len(concerns) >= 1
        assert any("baseline" in c["reason"].lower() for c in concerns)

    def test_metric_with_baseline_is_ok(self):
        text = "Increased revenue by 150% (from $2M to $5M) over 6 months."
        concerns = self.h._check_realism(text, [])
        assert len(concerns) == 0

    def test_metric_with_over_timeframe(self):
        text = "Reduced latency by 40% across all endpoints over 3 months."
        concerns = self.h._check_realism(text, [])
        assert len(concerns) == 0

    def test_metric_with_during_context(self):
        text = "Improved accuracy by 15% during the Q3 optimization push."
        concerns = self.h._check_realism(text, [])
        assert len(concerns) == 0

    def test_overuse_of_led(self):
        text = (
            "Led the frontend team. Led the migration project. "
            "Led the design system initiative. Led the hiring process."
        )
        concerns = self.h._check_realism(text, [])
        led_concern = [c for c in concerns if "led" in c["claim"].lower()]
        assert len(led_concern) >= 1

    def test_normal_led_count_is_ok(self):
        text = "Led the engineering team. Built the analytics pipeline. Designed the API."
        concerns = self.h._check_realism(text, [])
        led_concern = [c for c in concerns if "led" in c["claim"].lower()]
        assert len(led_concern) == 0

    def test_too_many_expertise_claims(self):
        text = (
            "Expertise in distributed systems. Expertise in machine learning. "
            "Expertise in frontend development. Expertise in DevOps."
        )
        concerns = self.h._check_realism(text, [])
        expertise_concern = [c for c in concerns if "expertise" in c["claim"].lower()]
        assert len(expertise_concern) >= 1


class TestPhase3DeterministicClean:
    """Phase 3: Deterministic fallback for surgical humanize."""

    def setup_method(self):
        self.h = Humanizer()

    def test_removes_banned_words_from_text(self):
        text = "I am passionate about leveraging AI."
        result = self.h.humanize(text, mode="resume")
        assert "passionate" not in result.humanized_text.lower()
        # "leveraging" could be replaced or removed
        assert "leveraging" not in result.humanized_text.lower()

    def test_removes_banned_phrases(self):
        text = "I am writing to express my interest in the role. I built the system."
        result = self.h.humanize(text, mode="cover_note")
        assert "I am writing to express" not in result.humanized_text

    def test_preserves_markdown_links(self):
        text = "Built [Analytics Platform](https://github.com/user/repo) for real-time data processing."
        flags = self.h._detect_slop(text)
        result = self.h.humanize(text, mode="resume")
        assert "https://github.com/user/repo" in result.humanized_text
        assert "[Analytics Platform]" in result.humanized_text or "Analytics Platform" in result.humanized_text

    def test_preserves_metrics(self):
        text = "Increased throughput by 200% (from 10K to 30K req/s) over 6 months."
        result = self.h.humanize(text, mode="resume")
        assert "200%" in result.humanized_text
        assert "10K" in result.humanized_text

    def test_empty_text_returns_empty(self):
        result = self.h.humanize("", mode="resume")
        assert result.humanized_text == ""

        result = self.h.humanize("   ", mode="resume")
        assert result.humanized_text.strip() == ""

    def test_no_flags_returns_unchanged(self):
        text = "Built a real-time data pipeline processing 500K events per second."
        result = self.h.humanize(text, mode="resume")
        assert result.humanized_text == text


class TestHumanizerResult:
    """Test the HumanizerResult dataclass and full pipeline output."""

    def setup_method(self):
        self.h = Humanizer()

    def test_result_structure(self):
        text = "I am passionate about technology."
        result = self.h.humanize(text, mode="resume")
        assert isinstance(result, HumanizerResult)
        assert result.original_text == text
        assert result.humanized_text != ""
        assert isinstance(result.flags, list)
        assert isinstance(result.recruiter_concerns, list)
        assert result.changes_made >= 0

    def test_company_type_context(self):
        """Test that company_type context is accepted and doesn't crash."""
        text = "Built a scalable data pipeline."
        result = self.h.humanize(text, mode="resume",
                                 context={"company_type": "startup"})
        assert result.humanized_text != ""


class TestStructuralRules:
    """Additional structural rule checks."""

    def setup_method(self):
        self.h = Humanizer()

    def test_long_sentence_splitting(self):
        """Deterministic tone adapt should split overly long sentences."""
        text = (
            "This is a very long sentence with many words that goes on and on "
            "and on and on and on and on and on and on and on and on and on "
            "and on and on and on and on and on and on and on and on."
        )
        # Should not crash even with very long sentences
        result = self.h.humanize(text, mode="resume",
                                 context={"company_type": "startup"})
        assert len(result.humanized_text) > 0

    def test_multiple_consecutive_i_starts_detected(self):
        text = "I did X. I did Y. I did Z."  # 3 consecutive I starts
        flags = self.h._detect_slop(text)
        cadence = [f for f in flags if f.category == "cadence"]
        assert len(cadence) >= 1


class TestEdgeCases:
    """Edge case handling."""

    def setup_method(self):
        self.h = Humanizer()

    def test_none_context(self):
        text = "Built a system."
        result = self.h.humanize(text, mode="resume", context=None)
        assert result.humanized_text == text

    def test_text_with_only_banned_words(self):
        text = "passionate innovative dynamic"
        result = self.h.humanize(text, mode="resume")
        # Should produce something (maybe empty after cleaning)
        assert isinstance(result.humanized_text, str)

    def test_text_with_unicode(self):
        text = "Built a system with 99.9% uptime. Used C++ and Rust."
        result = self.h.humanize(text, mode="resume")
        assert "99.9%" in result.humanized_text
        assert "C++" in result.humanized_text

    def test_mixed_content_with_banned_and_clean(self):
        text = (
            "I am passionate about software engineering.\n\n"
            "Built a real-time pipeline processing 500K events/second. "
            "Reduced latency by 40% (from 200ms to 120ms) over 3 months."
        )
        result = self.h.humanize(text, mode="resume")
        assert "passionate" not in result.humanized_text.lower()
        assert "500K events/second" in result.humanized_text
        assert "200ms" in result.humanized_text
