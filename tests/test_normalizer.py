"""
Tests for the Resume Normalizer.

Run: python -m pytest tests/test_normalizer.py -v
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure careerloop is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from careerloop.rendering.normalizer import normalize
from careerloop.rendering.resume_model import (
    NormalizedResume,
    HeaderInfo,
    SkillRow,
    ExperienceEntry,
    EducationEntry,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _serialize(resume: NormalizedResume) -> dict:
    """Convert NormalizedResume to a JSON-serializable dict."""
    def _convert(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _convert(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [_convert(i) for i in obj]
        return obj
    return _convert(resume)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Council Output (flat ## structure)
# ═══════════════════════════════════════════════════════════════════════════════

def test_normalize_council_output():
    """Parse the actual Council output (10_final_resume.md)."""
    council_path = Path(__file__).resolve().parent.parent / "output" / "council" / "siddharth" / "nicobar-final" / "10_final_resume.md"
    if not council_path.exists():
        # Try to find it relative to project root
        council_path = Path("output/council/siddharth/nicobar-final/10_final_resume.md")
        if not council_path.exists():
            print("SKIP: Council output not found, using inline test data")
            return _test_with_inline_council_output()

    md_text = council_path.read_text()
    resume = normalize(md_text)

    # Header checks
    assert resume.header.name == "Siddharth Saminathan"
    assert "siddharthsaminathan99@gmail.com" in resume.header.email
    assert "Chennai" in resume.header.location
    assert resume.header.phone != ""
    assert "emotenow.app" in resume.header.portfolio_url

    # Profile exists and is non-trivial
    assert len(resume.profile) > 100
    assert "AI Product Engineer" in resume.profile or "AI" in resume.profile

    # Skills: parsed as table rows (not empty)
    assert len(resume.skills) > 0
    for skill_row in resume.skills:
        assert isinstance(skill_row, SkillRow)
        assert skill_row.label != ""
        assert skill_row.items  # each row must have items

    # Skills rows must include expected categories
    skill_labels = {s.label.lower() for s in resume.skills}
    expected_labels = {"programming", "ai systems"}
    found = skill_labels & expected_labels
    assert found, f"Expected skill labels containing {expected_labels}, got {skill_labels}"

    # Experience: 4 entries
    assert len(resume.experience) == 4
    for exp in resume.experience:
        assert isinstance(exp, ExperienceEntry)
        assert exp.role != ""
        assert exp.company != ""
        assert isinstance(exp.bullets, list)
        # Each experience entry must have bullets (not a single blob)
        assert len(exp.bullets) > 0
        for bullet in exp.bullets:
            # No single bullet should contain internal " - " bullet separators
            assert not _has_collapsed_bullet_pattern(bullet), \
                f"Collapsed bullet detected in {exp.company}: {bullet[:100]}..."

    # Experience entries should not have description that looks like bullets
    for exp in resume.experience:
        if exp.description:
            assert not exp.description.strip().startswith("-"), \
                f"Description contains bullet markers for {exp.company}"

    # Achievements: non-empty list
    assert len(resume.achievements) > 0
    for ach in resume.achievements:
        assert isinstance(ach, str)
        assert len(ach) > 10

    # Education: 2 entries
    assert len(resume.education) == 2
    for edu in resume.education:
        assert isinstance(edu, EducationEntry)
        assert edu.degree != ""
        assert edu.institution != ""

    # Languages: non-empty list
    assert len(resume.languages) >= 2

    # Thesis exists
    assert resume.thesis is not None
    assert len(resume.thesis) > 20

    print(f"  PASS: {resume.header.name} — {len(resume.experience)} roles, "
          f"{len(resume.skills)} skill rows, {len(resume.achievements)} achievements, "
          f"{len(resume.education)} edu entries, {len(resume.languages)} languages")


def _test_with_inline_council_output():
    """Fallback test with inline sample data."""
    md_text = """\
## Siddharth Saminathan — CV

## Profile

**AI Product Engineer** with 4+ years building and shipping production AI systems.

## Contact

- **Phone:** +91 7299707403
- **Email:** test@example.com
- **Location:** Chennai, India
- **Portfolio:** https://emotenow.app/

## Education

- **M.Sc. Statistics and Machine Learning** — Linköping University, Sweden (2020–2022)
- **B.Tech Computer Science and Engineering** — SRM University, India (2016–2020)

## Skills

| Category | Technologies |
|----------|-------------|
| **Programming** | Python, SQL |
| **AI Systems** | LLM APIs, RAG pipelines, embeddings |

## Languages

- English (Fluent)
- Tamil
- Hindi

## Work Experience

## AI Engineer — Omnex Systems, Chennai (Jul 2025 – Present)

Omnex is an Enterprise AI Quality Platform.

- Built a production multi-agent AI system for manufacturing quality workflows.
- Designed a tool-driven orchestration layer.

## Co-Founder / AI Engineer — Emote (emotenow.app) (Apr 2024 – Present)

- Built and iterated a production AI system that learns from user interactions over time. - Designed and scaled end-to-end backend architecture. - Drove core system performance improvements.

## Key Achievements

- **Built Emote from zero:** Took product from vision to production.
- **Latency reduction:** Drove inference latency from ~15s to ~3s.

## Master's Thesis

Developed a machine learning pipeline for cancer metastasis prediction.
"""
    resume = normalize(md_text)

    # Basic structure
    assert resume.header.name == "Siddharth Saminathan"
    assert resume.header.email == "test@example.com"
    assert "Chennai" in resume.header.location

    # Skills parsed from table
    assert len(resume.skills) == 2
    assert resume.skills[0].label == "Programming"
    assert resume.skills[0].items == ["Python", "SQL"]

    # Experience
    assert len(resume.experience) == 2
    assert resume.experience[0].role == "AI Engineer"
    assert resume.experience[0].company == "Omnex Systems"
    assert resume.experience[0].location == "Chennai"
    assert resume.experience[0].description == "Omnex is an Enterprise AI Quality Platform."
    assert len(resume.experience[0].bullets) == 2

    # Collapsed bullets should be split
    assert len(resume.experience[1].bullets) == 3

    # Achievements
    assert len(resume.achievements) == 2

    # Education
    assert len(resume.education) == 2

    # Languages
    assert len(resume.languages) == 3
    assert "English (Fluent)" in resume.languages

    # Thesis
    assert resume.thesis is not None
    assert "cancer" in resume.thesis.lower()

    print("  PASS: Inline council output test")


def _has_collapsed_bullet_pattern(text: str) -> bool:
    """Check if text contains collapsed bullet patterns like '. - ' followed by capital."""
    import re
    return bool(re.search(r"\.\s+[-–—]\s+[A-Z]", text))


# ═══════════════════════════════════════════════════════════════════════════════
# Test: cv.md (nested ### structure)
# ═══════════════════════════════════════════════════════════════════════════════

def test_normalize_cv_md():
    """Parse original cv.md (nested ### roles inside ## Work Experience)."""
    cv_path = Path(__file__).resolve().parent.parent / "cv.md"
    if not cv_path.exists():
        cv_path = Path("cv.md")
        if not cv_path.exists():
            print("SKIP: cv.md not found")
            return

    md_text = cv_path.read_text()
    resume = normalize(md_text)

    # Header
    assert resume.header.name == "Siddharth Saminathan"

    # Experience: cv.md has roles under ### sub-headings within Work Experience
    assert len(resume.experience) == 4

    # Verify bullet splitting for Emote entry with collapsed bullets
    emote = [e for e in resume.experience if "Emote" in e.company]
    if emote:
        bullets = emote[0].bullets
        assert len(bullets) >= 3, f"Expected >=3 bullets for Emote, got {len(bullets)}: {bullets}"
        for b in bullets:
            assert not _has_collapsed_bullet_pattern(b), \
                f"Collapsed bullet in Emote: {b[:100]}"

    # Forbidden sections should NOT appear
    # The resume should NOT contain Target Roles or Deal-breakers as achievements/profile
    if resume.achievements:
        for ach in resume.achievements:
            assert "Target Role" not in ach
            assert "Deal-breaker" not in ach

    print(f"  PASS: cv.md — {len(resume.experience)} roles, "
          f"{len(resume.skills)} skill rows, {len(resume.achievements)} achievements")


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Forbidden Section Filtering
# ═══════════════════════════════════════════════════════════════════════════════

def test_forbidden_sections_filtered():
    """Verify forbidden sections are excluded from the normalized output."""
    md_text = """\
## Siddharth Saminathan — CV

## Profile
Test profile content.

## Target Roles
- AI Engineer
- Senior Backend Engineer

## Deal-breakers
- No pure frontend roles
- No legacy Java shops

## Skills
- Programming: Python

## Work Experience

## Test Role — Test Company (2020 – Present)
- Did things.

## Key Achievements
- Won award.

## Fit Score
4.3/5

## Council Verdict
Strong match.

## Warnings
- Check X

## Internal Notes
Private info here.

## Education
- **B.Sc.** — University (2016–2020)
"""
    resume = normalize(md_text)

    # All forbidden sections should be absent
    assert resume.profile == "Test profile content."
    assert len(resume.skills) == 1
    assert len(resume.experience) == 1
    assert len(resume.achievements) == 1
    assert len(resume.education) == 1

    # Profile should NOT contain forbidden content
    assert "Target Role" not in resume.profile
    assert "Deal-breaker" not in resume.profile

    print("  PASS: Forbidden sections filtered")


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

def test_empty_input():
    """Normalizer should handle empty/minimal input gracefully."""
    resume = normalize("")
    assert resume.header.name == ""
    assert resume.profile == ""
    assert resume.skills == []
    assert resume.experience == []
    assert resume.achievements == []
    assert resume.education == []
    assert resume.thesis is None
    assert resume.languages == []

    # Minimal valid input
    resume2 = normalize("## Profile\n\nJust a profile.")
    assert "Just a profile" in resume2.profile

    print("  PASS: Empty/minimal input handled")


def test_skill_table_variants():
    """Handle different skill table formats."""
    # Standard format
    md = """\
## Skills

| Category | Technologies |
|----------|-------------|
| AI | Python, LLMs, RAG |
| Backend | FastAPI, Redis |

## Profile
Test
"""
    resume = normalize(md)
    assert len(resume.skills) == 2
    assert resume.skills[0].label == "AI"
    assert resume.skills[0].items == ["Python", "LLMs", "RAG"]
    assert resume.skills[1].label == "Backend"

    # Bullet format fallback
    md2 = """\
## Skills

- **AI Systems:** LLM APIs, RAG pipelines
- Backend: FastAPI, Redis

## Profile
Test
"""
    resume2 = normalize(md2)
    assert len(resume2.skills) == 2
    assert resume2.skills[0].label == "AI Systems"

    print("  PASS: Skill table variants")


def test_experience_without_description():
    """Experience entries without description paragraphs should work."""
    md = """\
## Work Experience

## Developer — Corp, Remote (2020 – Present)

- Built features.
- Fixed bugs.

## Profile
Profile text.
"""
    resume = normalize(md)
    assert len(resume.experience) == 1
    assert resume.experience[0].description == ""
    assert len(resume.experience[0].bullets) == 2
    assert resume.experience[0].bullets[0] == "Built features."

    print("  PASS: Experience without description")


def test_collapsed_bullet_splitting():
    """Verify collapsed bullet detection and splitting."""
    # Simulated Council output with collapsed bullets
    md = """\
## Work Experience

## Engineer — Test Corp (2020 – Present)

- Built production AI system for manufacturing workflows. - Designed orchestration layer with tool routing. - Drove performance improvements reducing latency by 40%.
"""
    resume = normalize(md)

    assert len(resume.experience) == 1
    bullets = resume.experience[0].bullets
    assert len(bullets) == 3, f"Expected 3 bullets, got {len(bullets)}: {bullets}"
    assert "Built production AI system" in bullets[0]
    assert "Designed orchestration layer" in bullets[1]
    assert "Drove performance improvements" in bullets[2]

    # No bullet should contain " - " collapsed separators
    for b in bullets:
        assert not _has_collapsed_bullet_pattern(b)

    print("  PASS: Collapsed bullet splitting")


def test_education_parsing():
    """Verify education line parsing."""
    md = """\
## Education

- **M.Sc. Statistics and Machine Learning** — Linköping University, Sweden (2020–2022)
- **B.Tech Computer Science** — SRM University, India (2016–2020)
- PhD in AI — MIT (2022–2026)

## Profile
Test
"""
    resume = normalize(md)

    assert len(resume.education) == 3
    assert resume.education[0].degree == "M.Sc. Statistics and Machine Learning"
    assert resume.education[0].institution == "Linköping University"
    assert "Sweden" in resume.education[0].details
    assert resume.education[0].dates == "2020–2022"
    assert resume.education[2].degree == "PhD in AI"
    assert resume.education[2].institution == "MIT"

    print("  PASS: Education parsing")


def test_serialization():
    """NormalizedResume should serialize cleanly for downstream use."""
    resume = NormalizedResume(
        header=HeaderInfo(
            name="Test User",
            email="test@example.com",
        ),
        profile="Test profile.",
        skills=[SkillRow(label="AI", items=["Python", "SQL"])],
        experience=[
            ExperienceEntry(
                role="Engineer",
                company="Corp",
                dates="2020–Present",
                bullets=["Built things.", "Fixed bugs."],
            )
        ],
        achievements=["Won award."],
        education=[EducationEntry(
            degree="B.Sc. CS",
            institution="University",
            dates="2016–2020",
        )],
        thesis="Research paper.",
        languages=["English", "Spanish"],
    )

    d = _serialize(resume)

    assert d["header"]["name"] == "Test User"
    assert d["header"]["email"] == "test@example.com"
    assert d["profile"] == "Test profile."
    assert len(d["skills"]) == 1
    assert d["skills"][0]["label"] == "AI"
    assert d["skills"][0]["items"] == ["Python", "SQL"]
    assert len(d["experience"]) == 1
    assert d["experience"][0]["bullets"] == ["Built things.", "Fixed bugs."]
    assert d["achievements"] == ["Won award."]
    assert d["thesis"] == "Research paper."
    assert d["languages"] == ["English", "Spanish"]

    print("  PASS: Serialization")


def test_contact_field_variants():
    """Handle different contact field formats."""
    md = """\
## Contact

- Phone: +1 555-1234
- **Email:** user@domain.com
- Location: San Francisco, CA
- **Portfolio:** https://myportfolio.io/projects
- GitHub: https://github.com/username
- LinkedIn: https://linkedin.com/in/username

## Profile
Test
"""
    resume = normalize(md)

    assert resume.header.phone == "+1 555-1234"
    assert resume.header.email == "user@domain.com"
    assert resume.header.location == "San Francisco, CA"
    assert "myportfolio.io" in resume.header.portfolio_url
    assert resume.header.github_display == "username"
    assert resume.header.linkedin_display == "username"

    print("  PASS: Contact field variants")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        test_normalize_council_output,
        test_normalize_cv_md,
        test_forbidden_sections_filtered,
        test_empty_input,
        test_skill_table_variants,
        test_experience_without_description,
        test_collapsed_bullet_splitting,
        test_education_parsing,
        test_serialization,
        test_contact_field_variants,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
