"""
P0/P1 Functional Stabilization Regression Tests.

Covers:
  - Schema validation contracts (P0.5)
  - Private constraints never leave user_truth (P0.3)
  - Bullet preservation in normalizer (P0.3)
  - Normalizer forbidden section filtering
  - render_resume callable contract (P0.2)
  - Company intelligence grounding provenance (P0.8)
  - Validator catches em-dashes, arrows, raw markdown (P0.7)
  - Section rewrites include allowed_to_edit per section
  - Malformed JSON fails loudly before reaching downstream nodes

Run: python -m pytest tests/test_stabilization.py -v
"""

import sys
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from careerloop.council.schemas import validate_payload, schema_instruction, NODE_SCHEMAS
from careerloop.council.graph import _payload_to_rewritten_text
from careerloop.council.company_research import CompanyResearchAdapter, quality_score
from careerloop.council.compiler import ResumeCompiler
from careerloop.council.humanizer import Humanizer
from careerloop.rendering.normalizer import normalize
from careerloop.rendering.validator import ResumeValidator


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SIDDHARTH_MD = (ROOT / "cv.md").read_text(encoding="utf-8") if (ROOT / "cv.md").exists() else ""

COLLAPSED_BULLET_RESUME = """\
## Siddharth — CV

## Profile
AI engineer with 4 years experience.

## Work Experience

## AI Engineer — Omnex Systems, Chennai (Jul 2025 – Present)
- Built a production AI system. - Designed an orchestration layer. - Reduced latency from 12s to 8s.

## Co-Founder — Emote (Apr 2024 – Present)
- Built and shipped companion AI. - Grew to 450+ users. - Reduced cost by 95%.

## Key Achievements
- Won recognition for data migration.
"""

FORBIDDEN_SECTIONS_RESUME = """\
## Siddharth — CV

## Profile
Test profile.

## Target Roles
- AI Engineer

## Deal-breakers
- No pure frontend

## Work Experience

## Test Role — Test Company (2022–Present)
- Did things.

## Skills
| Category | Technologies |
|----------|-------------|
| **Programming** | Python |
"""

BROKEN_HTML_WITH_EM_DASH = """\
<html><body>
<h2>Experience</h2>
<ul>
<li>Built AI systems — Designed pipelines → Drove results</li>
</ul>
</body></html>
"""

BROKEN_HTML_WITH_COLLAPSED_BULLETS = """\
<html><body>
<h2>Work Experience</h2>
<ul>
<li>Built AI system. - Designed orchestration layer. - Drove performance improvements.</li>
</ul>
</body></html>
"""

BROKEN_HTML_WITH_RAW_MARKDOWN = """\
<html><body>
<h2>Profile</h2>
<p>**AI Engineer** with experience in LLM systems.</p>
</body></html>
"""

BROKEN_HTML_WITH_PRIVATE_SECTIONS = """\
<html><body>
<h2>Target Role</h2>
<p>AI Engineer</p>
<h2>Deal-breaker</h2>
<p>No legacy Java</p>
</body></html>
"""


# ─── Schema validation tests ──────────────────────────────────────────────────

class TestSchemaValidation:
    def test_valid_user_truth_passes(self):
        payload = {
            "total_years_experience": 4.5,
            "confirmed_skills": [{"skill": "Python", "years": 4, "evidence": "Built systems"}],
            "weak_skills": ["Kubernetes"],
            "evidence_bank": {"Python": ["Built AI system"]},
            "strongest_proof_points": ["Shipped production AI"],
            "claims_allowed": ["4+ years Python"],
            "claims_not_allowed": ["10 years AI"],
        }
        r = validate_payload("user_truth", payload)
        assert r.ok, r.errors

    def test_private_constraints_stripped_from_user_truth(self):
        payload = {
            "total_years_experience": 4.5,
            "confirmed_skills": [],
            "weak_skills": [],
            "evidence_bank": {},
            "strongest_proof_points": [],
            "claims_allowed": [],
            "claims_not_allowed": [],
            "private_constraints": ["min salary 25L", "Chennai preferred"],
        }
        r = validate_payload("user_truth", payload)
        assert "private_constraints" not in r.payload, (
            "private_constraints must be stripped from user_truth before any downstream LLM sees it"
        )

    def test_invalid_application_stance_caught(self):
        payload = {
            "one_line_positioning": "AI engineer",
            "narrative_angle": "builder",
            "lead_strengths": [],
            "proof_points_to_emphasize": [],
            "things_to_downplay": [],
            "tone_guidance": "direct",
            "recruiter_first_impression_target": "strong",
            "application_stance": "INVALID_STANCE",
            "reasoning": "test",
        }
        r = validate_payload("positioning_strategy", payload)
        assert not r.ok
        assert any("application_stance" in e for e in r.errors)

    def test_missing_required_key_caught(self):
        r = validate_payload("role_decode", {"normalized_title": "AI Engineer"})
        assert not r.ok
        assert len(r.errors) > 2

    def test_schema_instruction_contains_all_required_keys(self):
        instr = schema_instruction("user_truth")
        for key in NODE_SCHEMAS["user_truth"]["required"]:
            assert key in instr, f"schema_instruction missing key: {key}"

    def test_confidence_out_of_range_caught(self):
        payload = {
            "summary": "test", "business_model": "saas", "india_presence": "yes",
            "maturity": "startup", "hiring_urgency": "HIGH",
            "culture_signals": [], "red_flags": [],
            "positioning_implications": "", "interview_implications": "",
            "confidence": 1.5,
            "missing_data": [], "facts": [], "inferences": [],
            "sources": [], "gaps": [], "role_implications": [],
            "grounding_status": "UNGROUNDED", "fetched_at": "2026-05-19T00:00:00Z",
        }
        r = validate_payload("company_intelligence", payload)
        assert not r.ok
        assert any("confidence" in e for e in r.errors)


class TestS7StructuredRewriteContract:
    def test_tailored_bullets_compile_to_markdown_bullets(self):
        payload = {
            "tailored_bullets": ["Shipped the system.", "- Reduced latency."],
        }
        original = "- Built the system.\n- Improved speed."
        text = _payload_to_rewritten_text(payload, original, "experience")
        assert text == "- Shipped the system.\n- Reduced latency."

    def test_profile_tailored_bullet_compiles_to_paragraph(self):
        payload = {"tailored_bullets": ["AI product engineer with production LLM systems experience."]}
        text = _payload_to_rewritten_text(payload, "Old profile paragraph.", "profile")
        assert text == "AI product engineer with production LLM systems experience."

    def test_legacy_rewritten_text_wins_for_non_scaffold_sections(self):
        """For non-scaffold sections (summary, skills), rewritten_text takes priority."""
        payload = {
            "rewritten_text": "Full rewritten summary paragraph.",
            "tailored_bullets": ["Should not win for summary."],
        }
        assert _payload_to_rewritten_text(payload, "Old summary text.", "summary") == "Full rewritten summary paragraph."

    def test_scaffold_section_prefers_tailored_bullets_when_both_present(self):
        """For experience sections, tailored_bullets wins over rewritten_text so that
        scaffold reconstruction preserves company headers, job titles, and dates."""
        original = "Acme Corp\nEngineer 2022–Present\n- Old bullet one.\n- Old bullet two."
        payload = {
            "rewritten_text": "Rewrite without company headers.\n- New bullet.",
            "tailored_bullets": ["New bullet via scaffold."],
        }
        text = _payload_to_rewritten_text(payload, original, "experience")
        # Scaffold reconstruction should be used — company header preserved
        assert "Acme Corp" in text
        assert "New bullet via scaffold" in text

    def test_legacy_rewritten_text_extracted_when_no_tailored_bullets(self):
        """For experience sections with only rewritten_text, extract bullets from it
        and run scaffold reconstruction so company headers are preserved."""
        original = "Acme Corp\nEngineer 2022–Present\n- Old bullet one.\n- Old bullet two."
        payload = {
            "rewritten_text": "Rewrite prose.\n- Extracted new bullet.",
        }
        text = _payload_to_rewritten_text(payload, original, "experience")
        # Company header should be preserved via scaffold reconstruction
        assert "Acme Corp" in text
        assert "Extracted new bullet" in text

    def test_skills_section_uses_flat_list_path(self):
        """Skills sections skip scaffold reconstruction and output LLM bullets directly."""
        payload = {
            "tailored_bullets": [
                "Core Competencies: OTB Management, Assortment Planning, Vendor Negotiation",
                "Tools: Advanced Excel, SAP (Basic), Google Sheets",
            ]
        }
        # Original has more bullets (15) and subsection headers — scaffold would be garbled
        original = (
            "Core Competencies: Assortment Planning\n\n"
            "- Fashion Buying\n- PO/PI Coordination\n- Vendor Management\n"
            "- Inventory\nControl\n"
            "Tools: Advanced MS Excel\n- MS Word\n- Google Sheets\n"
        )
        text = _payload_to_rewritten_text(payload, original, "skills")
        # Should be flat 2-bullet list — no original content leaking through
        assert text == (
            "- Core Competencies: OTB Management, Assortment Planning, Vendor Negotiation\n"
            "- Tools: Advanced Excel, SAP (Basic), Google Sheets"
        )
        # Crucially — no original artifacts in output
        assert "Fashion Buying" not in text
        assert "Inventory\nControl" not in text

    def test_experience_continuation_lines_are_skipped(self):
        """Multi-line wrapped bullets: continuation lines must not appear after rewrite."""
        # Simulates PDF-extracted experience where bullets wrap across multiple lines
        original = (
            "Acme Corp\nSoftware Engineer Jan 2022 – Present\n\n"
            "- Built recommendation engine using\ncollaborative filtering across 1M users.\n"
            "- Reduced latency from 12s to 800ms by\nrefactoring the cache layer.\n"
        )
        payload = {
            "tailored_bullets": [
                "Shipped personalization engine that drove 22% lift in engagement across 1M users.",
                "Cut API latency 93% by redesigning cache invalidation strategy.",
            ]
        }
        text = _payload_to_rewritten_text(payload, original, "experience")
        # Structural lines preserved
        assert "Acme Corp" in text
        assert "Software Engineer Jan 2022" in text
        # Rewritten bullets present
        assert "- Shipped personalization engine" in text
        assert "- Cut API latency 93%" in text
        # Continuation lines from original MUST NOT appear
        assert "collaborative filtering" not in text
        assert "refactoring the cache layer" not in text

    def test_experience_excess_original_bullets_are_dropped(self):
        """When LLM returns fewer bullets than original, excess originals are not kept."""
        original = (
            "- Bullet one original.\n"
            "- Bullet two original.\n"
            "- Bullet three original.\n"
            "- Bullet four original.\n"
        )
        payload = {"tailored_bullets": ["Rewritten one.", "Rewritten two."]}
        text = _payload_to_rewritten_text(payload, original, "experience")
        assert "- Rewritten one." in text
        assert "- Rewritten two." in text
        # The two un-replaced originals must not appear
        assert "Bullet three original" not in text
        assert "Bullet four original" not in text


# ─── Normalizer bullet preservation tests ─────────────────────────────────────

class TestNormalizerBulletPreservation:
    def test_plaintext_softbreaks_are_preserved_in_canonical_parse(self):
        text = """\
NAME
email@example.com
SUMMARY
Line one
line two
PROFESSIONAL EXPERIENCE
Company City, India
Role Jan 2024 - Present
- Did one thing.
"""
        resume = ResumeCompiler.parse_markdown(text)
        summary = next(s for s in resume.sections if s.section_id == "summary")
        assert "Line one\nline two" in summary.raw_text

    def test_collapsed_bullets_split(self):
        resume = normalize(COLLAPSED_BULLET_RESUME)
        assert len(resume.experience) == 2
        omnex = resume.experience[0]
        assert len(omnex.bullets) >= 3, (
            f"Omnex bullets should be ≥3, got {len(omnex.bullets)}: {omnex.bullets}"
        )
        emote = resume.experience[1]
        assert len(emote.bullets) >= 3, (
            f"Emote bullets should be ≥3, got {len(emote.bullets)}: {emote.bullets}"
        )
        for exp in resume.experience:
            for b in exp.bullets:
                import re
                assert not re.search(r"\.\s+[-–—]\s+[A-Z]", b), (
                    f"Collapsed bullet survived: {b[:80]}"
                )

    def test_forbidden_sections_excluded(self):
        resume = normalize(FORBIDDEN_SECTIONS_RESUME)
        all_text = " ".join(
            [resume.profile] +
            [e.role + " " + " ".join(e.bullets) for e in resume.experience] +
            resume.achievements +
            [s.label for s in resume.skills]
        ).lower()
        assert "target role" not in all_text, "Target Roles leaked into normalized output"
        assert "deal-breaker" not in all_text, "Deal-breakers leaked into normalized output"

    def test_achievement_thematic_break_is_not_parsed_as_bullet(self):
        resume = normalize("""\
## Test Candidate

## Achievements
- Shipped one real thing.

---
""")
        assert resume.achievements == ["Shipped one real thing."]

    def test_experience_thematic_break_is_not_appended_to_last_bullet(self):
        resume = normalize("""\
## Test Candidate

## Work Experience

## Data Analyst — TestCo

- Built dashboards.

---

## Skills
Python
""")
        assert resume.experience[0].bullets == ["Built dashboards."]

    def test_education_detail_bullets_stay_inside_degree(self):
        resume = normalize("""\
## Test Candidate

## Education

**M.Sc. Statistics and Machine Learning** — Linköping University, Sweden · 2020-2022

- Thesis: Built an ML pipeline.
- Applied PCA for modeling.

**B.Tech Computer Science & Engineering** — SRM University, India · 2016-2020
""")
        assert len(resume.education) == 2
        assert resume.education[0].degree == "M.Sc. Statistics and Machine Learning"
        assert resume.education[0].dates == "2020-2022"
        assert "Thesis: Built an ML pipeline." in resume.education[0].details
        assert "Applied PCA for modeling." in resume.education[0].details

    @pytest.mark.skipif(not SIDDHARTH_MD, reason="cv.md not present")
    def test_siddharth_cv_md_bullet_counts(self):
        resume = normalize(SIDDHARTH_MD)
        assert len(resume.experience) >= 4, f"Expected ≥4 experience entries, got {len(resume.experience)}"
        for exp in resume.experience:
            assert len(exp.bullets) >= 1, f"Zero bullets for {exp.company}"
        emote = next((e for e in resume.experience if "emote" in e.company.lower()), None)
        if emote:
            assert len(emote.bullets) >= 3, f"Emote should have ≥3 bullets, got {len(emote.bullets)}"


class TestNormalizerLooseFormats:
    def test_preamble_header_is_not_dropped(self):
        md = """\
Jane Candidate
jane@example.com | +91 9999999999 | linkedin.com/in/jane

## Summary
Retail operator.

## Work Experience

### Manager - TestCo, Bangalore (Jan 2024 - Present)
- Built category process.
"""
        resume = normalize(md)
        assert resume.header.name == "Jane Candidate"
        assert resume.header.email == "jane@example.com"

    def test_loose_experience_company_role_date_format(self):
        md = """\
Jane Candidate
jane@example.com

## Summary
Retail operator.

## Professional Experience
TestCo Bangalore, India
Category Manager Jan 2024 - Present
Owned assortment planning.
- Built category process.
- Improved margins by 12%.

SecondCo Remote - Chennai, India
Founder Nov 2022 - Dec 2023
Built a resale brand.
- Sold 80+ orders.
- Maintained 0 returns.
"""
        resume = normalize(md)
        assert len(resume.experience) == 2
        assert resume.experience[0].company == "TestCo"
        assert "Category Manager" in resume.experience[0].role
        assert len(resume.experience[0].bullets) == 2

    def test_grouped_skills_bold_heading_plus_bullets(self):
        md = """\
Jane Candidate
jane@example.com

## Summary
Retail operator.

## Work Experience

### Manager - TestCo, Bangalore (Jan 2024 - Present)
- Built category process.

## Skills
**Tools**
- Excel
- SAP

**Core Competencies**
- Assortment planning
- Vendor negotiation
"""
        resume = normalize(md)
        labels = [row.label for row in resume.skills]
        assert labels == ["Tools", "Core Competencies"]
        assert resume.skills[0].items == ["Excel", "SAP"]


class TestHumanizerStructureSafety:
    def test_resume_humanizer_never_uses_llm_to_rewrite_full_markdown(self):
        class ExplodingLLM:
            def complete_json(self, system, user, max_tokens=None):
                raise AssertionError("resume markdown must not be LLM-humanized as one blob")

        md = """\
## Summary
I am passionate about retail.

## Experience

### Manager - TestCo, Bangalore (Jan 2024 - Present)
- Built category process.
- Improved margins by 12%.
"""
        result = Humanizer(ExplodingLLM()).humanize(md, mode="resume")
        assert result.humanized_text.count("\n- ") == 2
        assert "## Experience" in result.humanized_text


# ─── Validator rule tests ──────────────────────────────────────────────────────

class TestResumeValidator:
    def test_em_dash_fails(self):
        v = ResumeValidator(BROKEN_HTML_WITH_EM_DASH)
        passed, errors, warnings = v.validate()
        rule = v.to_dict()["rules"]
        assert not rule["EM_DASH"]["passed"], "EM_DASH rule should fail for em-dash content"

    def test_arrow_fails(self):
        v = ResumeValidator(BROKEN_HTML_WITH_EM_DASH)
        v.validate()
        rule = v.to_dict()["rules"]
        assert not rule["ARROWS"]["passed"], "ARROWS rule should fail for arrow content"

    def test_collapsed_bullets_detected(self):
        v = ResumeValidator(BROKEN_HTML_WITH_COLLAPSED_BULLETS)
        v.validate()
        rule = v.to_dict()["rules"]
        assert not rule["COLLAPSED_BULLETS"]["passed"], "Collapsed bullets should be detected"

    def test_raw_markdown_bold_detected(self):
        v = ResumeValidator(BROKEN_HTML_WITH_RAW_MARKDOWN)
        v.validate()
        rule = v.to_dict()["rules"]
        assert not rule["RAW_MARKDOWN_TOKENS"]["passed"], "**bold** in HTML should fail RAW_MARKDOWN_TOKENS"

    def test_forbidden_sections_detected(self):
        v = ResumeValidator(BROKEN_HTML_WITH_PRIVATE_SECTIONS)
        v.validate()
        rule = v.to_dict()["rules"]
        assert not rule["FORBIDDEN_SECTIONS"]["passed"], "Target Role/Deal-breaker should fail FORBIDDEN_SECTIONS"

    def test_clean_html_passes_all_error_rules(self):
        clean_html = """\
<html><body>
<h2>Profile</h2>
<p>AI engineer with 4 years of experience building production systems.</p>
<h2>Work Experience</h2>
<ul>
<li>Built a production AI system for manufacturing quality workflows at Omnex.</li>
<li>Designed an orchestration layer using tool-calling and microservices.</li>
<li>Reduced response latency from 12s to 8s through pipeline restructuring.</li>
</ul>
<h2>Education</h2>
<p>M.Sc. Statistics and Machine Learning, Linkoping University (2020-2022)</p>
</body></html>"""
        v = ResumeValidator(clean_html)
        v.validate()
        d = v.to_dict()
        error_rules = {k: v for k, v in d["rules"].items() if v["severity"] == "ERROR"}
        failed_errors = [k for k, v in error_rules.items() if not v["passed"] and k != "TAILORING_DELTA"]
        assert not failed_errors, f"Clean HTML should pass all ERROR rules, failed: {failed_errors}"


# ─── Company research grounding tests ─────────────────────────────────────────

class TestCompanyResearch:
    def test_ungrounded_when_no_sources(self):
        adapter = CompanyResearchAdapter()
        bundle = adapter.gather("UnknownStartupXYZ")
        assert bundle.grounding_status in ("UNGROUNDED", "PARTIAL")
        assert bundle.fetched_at
        qs = quality_score(bundle)
        assert qs["status"] in ("UNGROUNDED", "PARTIAL")

    def test_partial_when_website_provided(self):
        adapter = CompanyResearchAdapter()
        bundle = adapter.gather("TestCo", website="https://testco.example.com", jd_text="We build AI systems.")
        assert bundle.grounding_status in ("PARTIAL", "UNGROUNDED")
        qs = quality_score(bundle)
        assert "source_count" in qs
        assert "gaps" in qs

    def test_gaps_populated_without_search(self):
        adapter = CompanyResearchAdapter()
        bundle = adapter.gather("MysteryCompany")
        assert len(bundle.gaps) > 0, "Should document gaps when no search is available"

    def test_bundle_to_dict_has_required_keys(self):
        adapter = CompanyResearchAdapter()
        bundle = adapter.gather("AnyCompany", jd_text="Looking for an AI engineer.")
        d = bundle.to_dict()
        for key in ("company", "fetched_at", "sources", "grounding_status", "gaps"):
            assert key in d, f"bundle dict missing key: {key}"


# ─── render_resume P0.2 contract test ─────────────────────────────────────────

class TestRenderResumeContract:
    def test_render_resume_uses_council_output_not_cv_md(self):
        """Changing 10_final_resume.md changes the rendered HTML."""
        from careerloop.rendering.render_all_templates import render_resume

        council_md = """\
## Test Person — CV

## Contact
- **Email:** test@example.com
- **Phone:** +91 9999999999
- **Location:** Chennai, India

## Profile
AI engineer with 3 years of experience.

## Work Experience

## AI Engineer — Acme Corp, Chennai (Jan 2023 – Present)
- Built a production pipeline for data ingestion.
- Designed a monitoring system for real-time alerting.
- Reduced latency from 10s to 2s.

## Skills
| Category | Technologies |
|----------|-------------|
| **Programming** | Python, SQL |

## Education
- **B.Tech CS** — SRM University, India (2016–2020)
"""
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "10_final_resume.md"
            md_path.write_text(council_md, encoding="utf-8")
            out_dir = Path(tmp) / "rendered"

            meta = render_resume(md_path, candidate="testperson", run_id="test", out_dir=str(out_dir), generate_pdf=False)

            assert "templates" in meta
            assert "normalized_resume_json_path" in meta

            norm_path = Path(meta["normalized_resume_json_path"])
            assert norm_path.exists(), "Normalized resume JSON must be written"
            norm = json.loads(norm_path.read_text(encoding="utf-8"))
            assert norm["header"]["email"] == "test@example.com"
            assert len(norm["experience"]) == 1
            assert len(norm["experience"][0]["bullets"]) == 3

    def test_render_resume_raises_if_md_not_found(self):
        from careerloop.rendering.render_all_templates import render_resume
        with pytest.raises(FileNotFoundError):
            render_resume("/nonexistent/path/resume.md", candidate="x")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
