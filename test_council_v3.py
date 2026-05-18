"""
Validation suite for Resume Council v3.0 (8-System Architecture).
Runs the pipeline against 3 fixture profiles.
"""

import os
import sys
import re
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from careerloop.council.orchestrator import ResumeCouncilOrchestrator
from careerloop.council.compiler import ResumeCompiler
from careerloop.council.models import (
    CanonicalResume,
    SectionRewrites,
    SectionRewrite,
    PreservationContract,
)

NICOBAR_JD = """
Job Title: AI Product Engineer — CEO's Office
Company: Nicobar Design Pvt. Ltd. (nicobar.com)
Location: Delhi
Experience: 3-5 years

THE OPPORTUNITY
We've spent a decade building a brand that looks and feels unmistakably Nicobar. The next chapter is building a company that thinks the same way — every store, every collection, every customer conversation: sharper, faster, unmistakably ours. AI-native, not in theory, but in every room we walk into.

WHAT YOU'LL OWN
01 Customer Personalization : Build the intelligence layer beneath all our customer communication that understands who each customer actually is.
02 Store Clienteling : Build the clienteling tool our store teams reach for every day.
03 Business Intelligence : Replace Microsoft BI dashboards with a live, conversational intelligence layer.
04 Smoothen Design Workstreams : Remove friction so the creative team can make more, better, faster.

WHAT WE'RE LOOKING FOR
Engineering degree from IIT, BITS, NIT or equivalent with 3-5 years of experience.
You've built something real with an LLM API - OpenAI, Claude, Gemini, etc.
Fluent in Python/ NodeJS. Comfortable writing and querying SQL.
Ability to build front-ends that don't embarrass the brand. We're visual people.
"""

def test_fixture(person_id: str, fixture_path: str):
    print(f"\n{'='*80}")
    print(f" TESTING FIXTURE: {person_id}")
    print(f"{'='*80}\n")

    with open(fixture_path, "r") as f:
        cv_text = f.read()

    profile = {
        "candidate": {"full_name": f"Test User {person_id}"},
        "search_preferences": {
            "target_roles": ["Engineer", "Lead"],
            "deal_breakers": ["No mass recruiters"],
            "salary_floor": 100000
        }
    }

    orchestrator = ResumeCouncilOrchestrator(root=str(ROOT))

    result = orchestrator.run(
        job_id="nicobar-test",
        intent="PREPARE_APPLICATION",
        person_id=person_id,
        master_cv=cv_text,
        user_profile=profile
    )

    if result.application_pack:
        print(f"\n[SUCCESS] {person_id} passed.")
        # Leakage test
        final_md = result.application_pack.resume_markdown
        leaked = [x for x in ["No mass recruiters", "100000", "deal_breakers"] if x in final_md]
        if leaked:
            print(f"  !! LEAKAGE DETECTED: {leaked}")
        else:
            print("  ✅ Leakage Test: PASSED (Zero private metadata found)")

        # Link preservation test
        if person_id == "experienced":
            if "github.com/alexchen" in final_md:
                print("  ✅ Link Test: PASSED (Alex Chen's GitHub preserved)")
            else:
                print("  !! Link Test: FAILED (Alex Chen's GitHub lost)")
    else:
        print(f"\n[FAILED] {person_id} run failed.")


# ─── Link Preservation Fixture (links across different section types) ─────

LINK_HEAVY_MD = """# Jane Doe — Full-Stack Engineer

## Contact
- Email: [jane@example.com](mailto:jane@example.com)
- GitHub: [github.com/janedoe](https://github.com/janedoe)
- LinkedIn: [linkedin.com/in/janedoe](https://linkedin.com/in/janedoe)

## Skills
- **Languages:** Python, TypeScript, Go
- **Frameworks:** [React](https://react.dev), [FastAPI](https://fastapi.tiangolo.com)
- **Infrastructure:** [Kubernetes](https://kubernetes.io), AWS

## Work Experience

### Senior Engineer — [Acme Corp](https://acme.example.com) (2021-Present)
- Led migration to microservices. See [case study](https://acme.example.com/case-studies/migration).
- Built [OSS tool](https://github.com/janedoe/acme-tool) (2k stars).

### Engineer — [StartupX](https://startupx.example.com) (2018-2021)
- Developed real-time analytics dashboard. [Demo](https://demo.startupx.example.com).

## Projects

### [Side Project Alpha](https://github.com/janedoe/alpha)
- A CLI tool for managing Kubernetes clusters.

## Internal Metadata (PRIVATE)
- Target: Staff Engineer
- Salary Floor: $200k
"""


def test_link_preservation():
    """Verify that all links survive parse -> assemble round-trip."""
    print(f"\n{'='*80}")
    print(" TEST: Link Preservation (parse -> mock rewrite -> assemble)")
    print(f"{'='*80}\n")

    # 1. Parse
    resume = ResumeCompiler.parse_markdown(LINK_HEAVY_MD)
    print(f"Parsed {len(resume.sections)} sections")
    for s in resume.sections:
        print(f"  [{s.visibility_class.value}] {s.section_title}: {len(s.links)} link(s)")

    # Count total original links
    total_original = sum(len(s.links) for s in resume.sections)
    print(f"\nTotal original links: {total_original}")

    # 2. Build contract
    contract = ResumeCompiler.build_contract(resume, {})
    print(f"Sections excluded: {contract.sections_to_exclude}")

    # 3. Create mock rewrites (KEEP everything - no LLM changes)
    mock_rewrites = SectionRewrites(rewrites={})
    for section in resume.sections:
        if section.section_id not in contract.sections_to_exclude:
            mock_rewrites.rewrites[section.section_id] = SectionRewrite(
                section_id=section.section_id,
                original_text=section.raw_text,
                rewritten_text=section.raw_text,
                change_type="KEEP",
                change_reason="Mock test - no rewrite",
                claims_added=[],
                claims_removed=[],
                evidence_used=[],
                risk_level="low",
            )

    # 4. Assemble
    final_md = ResumeCompiler.assemble(resume, mock_rewrites, contract)
    print(f"\nAssembled markdown ({len(final_md)} chars)")

    # 5. Extract final links
    final_links = ResumeCompiler.extract_links_from_text(final_md)
    print(f"Links in final output: {len(final_links)}")
    for link in final_links:
        print(f"  - {link}")

    # 6. Link audit
    audit = ResumeCompiler._verify_links_preserved(resume, final_md, contract)
    print(f"\nLink Audit:")
    print(f"  Original total: {audit.total_original}")
    print(f"  Final total:    {audit.total_final}")
    print(f"  Missing:        {len(audit.missing_links)}")
    if audit.warnings:
        for w in audit.warnings:
            print(f"  !! {w}")

    # 7. Assertions
    non_private_sections = [
        s for s in resume.sections
        if s.section_id not in contract.sections_to_exclude
    ]
    expected_links = sum(len(s.links) for s in non_private_sections)

    assert expected_links > 0, "Should have links in non-private sections"
    assert audit.total_original == expected_links, (
        f"Audit original count {audit.total_original} != expected {expected_links}"
    )
    assert audit.total_final >= audit.total_original, (
        f"Final links ({audit.total_final}) < original links ({audit.total_original})"
    )
    assert len(audit.missing_links) == 0, (
        f"Missing links: {audit.missing_links}"
    )

    # Verify private content excluded
    assert "Salary Floor" not in final_md, "PRIVATE section leaked into output!"
    assert "Internal Metadata" not in final_md, "PRIVATE section leaked into output!"

    # Verify specific links present
    required_links = [
        "mailto:jane@example.com",
        "https://github.com/janedoe",
        "https://linkedin.com/in/janedoe",
        "https://react.dev",
        "https://fastapi.tiangolo.com",
        "https://kubernetes.io",
        "https://acme.example.com",
        "https://github.com/janedoe/acme-tool",
        "https://startupx.example.com",
        "https://github.com/janedoe/alpha",
    ]
    for link in required_links:
        assert link in final_links, f"Required link missing: {link}"

    print(f"\n  ✅ ALL LINKS PRESERVED ({audit.total_final}/{audit.total_original})")
    print(f"  ✅ PRIVATE SECTION EXCLUDED")
    print(f"  ✅ LINK AUDIT CLEAN")

    # 8. Test link audit with broken data (simulate LLM dropping a link)
    print(f"\n--- Simulating LLM link drop ---")
    broken_rewrites = SectionRewrites(rewrites={})
    for section in resume.sections:
        if section.section_id not in contract.sections_to_exclude:
            stripped = re.sub(r"\[.*?\]\(.*?\)", "", section.raw_text)
            broken_rewrites.rewrites[section.section_id] = SectionRewrite(
                section_id=section.section_id,
                original_text=section.raw_text,
                rewritten_text=stripped,
                change_type="REWRITE",
                change_reason="Simulated link loss",
                claims_added=[],
                claims_removed=[],
                evidence_used=[],
                risk_level="high",
            )

    broken_final = ResumeCompiler.assemble(resume, broken_rewrites, contract)
    broken_audit = ResumeCompiler._verify_links_preserved(resume, broken_final, contract)
    assert len(broken_audit.missing_links) > 0, (
        "Audit should detect missing links when LLM drops them"
    )
    assert len(broken_audit.warnings) > 0, (
        "Audit should produce warnings when links are missing"
    )
    print(f"  ✅ Correctly detected {len(broken_audit.missing_links)} missing links")
    print(f"  ✅ Warning produced: {broken_audit.warnings[0][:80]}...")


if __name__ == "__main__":
    fixtures = [
        ("experienced", "examples/fixtures/experienced_tech.md"),
        ("fresher", "examples/fixtures/fresher_ml.md"),
        ("business", "examples/fixtures/business_lead.md"),
    ]

    for p_id, p_path in fixtures:
        test_fixture(p_id, p_path)

    # Run link preservation test (pure deterministic - no LLM)
    test_link_preservation()
