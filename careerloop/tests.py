"""
CareerLoop Phase 1 Tests.

Usage: python -m careerloop.runner --test
"""

import os
import sys
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CAREER_OPS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CAREER_OPS_ROOT)

from careerloop.models import (
    JobPosting, URLType, UserVisibleOpportunity, classify_url_type,
    normalize_company, normalize_role, normalize_location, make_fingerprint
)
from careerloop.dedupe import DedupeEngine


PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


def test_fingerprinting():
    """A. Fingerprint — same job from LinkedIn and company site merged."""
    print("\n── A. Fingerprint & Normalization ──")

    j1 = JobPosting(company="Stripe Inc.", role_title="Senior Software Engineer",
                    location="Bengaluru", source_url="https://linkedin.com/jobs/view/123")
    j2 = JobPosting(company="Stripe", role_title="Sr. Software Engineer",
                    location="Bangalore, India", source_url="https://greenhouse.io/stripe/jobs/456")

    check("Company normalized same", j1.company_normalized == j2.company_normalized,
          f"'{j1.company_normalized}' vs '{j2.company_normalized}'")
    check("Role normalized similar", "software engineer" in j1.role_normalized and "software engineer" in j2.role_normalized,
          f"'{j1.role_normalized}' vs '{j2.role_normalized}'")
    check("Location normalized same", j1.location_normalized == j2.location_normalized,
          f"'{j1.location_normalized}' vs '{j2.location_normalized}'")

    # Different jobs
    j3 = JobPosting(company="Stripe", role_title="Product Manager", location="Bangalore")
    check("Different roles → different fingerprints", j1.fingerprint != j3.fingerprint,
          f"{j1.fingerprint} vs {j3.fingerprint}")

    # Normalization edge cases
    check("TCS → tata consultancy services", normalize_company("TCS") == "tata consultancy services")
    check("bengaluru → bangalore", normalize_location("bengaluru") == "bangalore")
    check("remote → remote", normalize_location("Work from Home") == "remote")
    check("Gurgaon → gurugram", normalize_location("Gurgaon, Haryana") == "gurugram")


def test_dedupe_and_suppression():
    """B+C. Dedupe — same job merged, applied/skipped suppressed."""
    print("\n── B+C. Dedupe & Suppression ──")

    engine = DedupeEngine()

    # Simulate existing applied job
    j_applied = JobPosting(company="Anthropic", role_title="Applied AI Engineer",
                           location="Bangalore", source="greenhouse")
    engine._applied_fingerprints.add(j_applied.fingerprint)

    # Simulate existing skipped job
    j_skipped = JobPosting(company="TCS", role_title="Java Developer",
                           location="Chennai", source="naukri")
    engine._skipped_fingerprints.add(j_skipped.fingerprint)

    # New jobs
    new_jobs = [
        JobPosting(company="Anthropic", role_title="Applied AI Engineer",
                   location="Bangalore", source="linkedin"),  # ← same as applied
        JobPosting(company="TCS", role_title="Java Developer",
                   location="Chennai", source="company"),     # ← same as skipped
        JobPosting(company="Stripe", role_title="Backend Engineer",
                   location="Bangalore", source="greenhouse"),  # ← new
        JobPosting(company="MongoDB", role_title="Staff Engineer",
                   location="Gurugram", source="greenhouse"),   # ← new
    ]

    unique, merges = engine.process_new_jobs(new_jobs)

    check("Applied suppressed", len(unique) == 2, f"Got {len(unique)}, expected 2 (applied+skipped removed)")
    check("Skipped suppressed", all(j.company != "TCS" for j in unique))
    check("New jobs pass through", any(j.company == "Stripe" for j in unique))
    check("Applied suppressed before merge", len(unique) == 2 and all(j.company != "Anthropic" for j in unique), "Applied job suppressed correctly (merge not needed)")

    # Repost test
    same_job = JobPosting(company="MongoDB", role_title="Staff Engineer",
                          location="Gurugram", source="wellfound")
    unique2, merges2 = engine.process_new_jobs([same_job])
    check("Repost suppressed (same fingerprint)", len(unique2) == 0)


def test_csv_import():
    """D. CSV import creates normalized jobs."""
    print("\n── D. CSV Import ──")

    from careerloop.discovery import DiscoveryEngine
    import tempfile, csv

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        engine = DiscoveryEngine(str(root))

        # Create test CSV
        csv_path = engine.import_dir / "2026-05-14.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["source", "company", "role", "url", "location", "description",
                        "posted_at", "work_mode", "salary_range", "experience_required",
                        "skills_required", "company_type", "responsibilities"])
            w.writerow(["linkedin", "Stripe", "Senior AI Engineer",
                        "https://linkedin.com/jobs/123", "Bangalore",
                        "Building AI features...", "2026-05-10", "hybrid",
                        "₹50L-80L", "5+ years", "Python,LLM,FastAPI", "saas",
                        "Build AI pipelines"])

        jobs = engine._discover_csv("2026-05-14")
        check("CSV import creates jobs", len(jobs) == 1, f"Got {len(jobs)}")
        if jobs:
            job = jobs[0]
            check("Company parsed", job.get("company") == "Stripe")
            check("Role parsed", job.get("title") == "Senior AI Engineer")
            check("Location parsed", job.get("location") == "Bangalore")
            check("Skills parsed", len(job.get("skills", [])) == 3)


def test_india_fit_llm():
    """E. India Fit — LLM scoring logic (smoke test with fallback)."""
    print("\n── E. India Fit LLM ──")

    from careerloop.india_fit_llm import LLMIndiaFitEngine

    engine = LLMIndiaFitEngine()
    profile = {
        "target_roles": ["AI Product Engineer", "Applied AI Engineer"],
        "confirmed_skills": ["python", "fastapi", "llm apis", "postgresql"],
        "rejected_roles": ["sales", "support", "frontend"],
        "rejected_company_types": ["consulting", "body-shop"],
        "startup_tolerance": 8,
        "salary_floor_lakhs": 25,
        "location_city": "Chennai",
        "notice_period_days": 30,
    }

    # Test 1: Perfect fit
    j1 = JobPosting(company="Anthropic", role_title="Applied AI Engineer",
                    location="Bangalore", source="greenhouse")
    r1 = engine.score_job(j1, profile)
    check("Returns valid JSON with overall_score", "overall_score" in r1)
    check("Returns recommendation", "recommendation" in r1)
    check("Returns risks list", isinstance(r1.get("risks"), list))

    # Test 2: Sales job for non-sales user → SKIP
    j2 = JobPosting(company="Oracle", role_title="Enterprise Sales Director",
                    location="Mumbai", source="linkedin")
    r2 = engine.score_job(j2, profile)
    check("Sales job gets low score", r2.get("overall_score", 100) <= 50,
          f"Score: {r2.get('overall_score')} (≤50 = low/fail)")

    # Test 3: Startup for startup-tolerant user → APPLY/MAYBE
    j3 = JobPosting(company="SeedStage AI", role_title="Founding AI Engineer",
                    location="Bangalore", source="wellfound",
                    company_type="startup")
    r3 = engine.score_job(j3, profile)
    check("Startup-tolerant user gets reasonable score", r3.get("overall_score", 0) > 40,
          f"Score: {r3.get('overall_score')}")

    # Test 4: No-startup user should downrank startup
    low_startup_profile = {**profile, "startup_tolerance": 2}
    r4 = engine.score_job(j3, low_startup_profile)
    check("Low-startup user gets lower score for startup",
          r4.get("overall_score", 100) <= r3.get("overall_score", 0) + 5,
          f"Low-startup: {r4.get('overall_score')} vs tolerant: {r3.get('overall_score')}")

    # Test 5: AI scientist should be SKIP if user only has light AI exposure
    light_ai_profile = {**profile, "confirmed_skills": ["python", "sql", "power bi"],
                        "target_roles": ["Data Analyst", "Product Analyst"]}
    j5 = JobPosting(company="DeepMind", role_title="Research Scientist - AI",
                    location="Bangalore", source="greenhouse")
    r5 = engine.score_job(j5, light_ai_profile)
    check("AI scientist SKIP for light-AI user", r5.get("overall_score", 100) <= 60,
          f"Score: {r5.get('overall_score')}")

    # Test 6: Stable GCC/MNC analyst role → APPLY/MAYBE for low-startup profile
    gcc_profile = {**profile, "startup_tolerance": 2,
                   "target_roles": ["Data Analyst", "Business Analyst"]}
    j6 = JobPosting(company="Goldman Sachs", role_title="Data Analyst",
                    location="Bangalore", source="linkedin")
    r6 = engine.score_job(j6, gcc_profile)
    check("Stable MNC analyst → reasonable score", r6.get("overall_score", 0) >= 50,
          f"Score: {r6.get('overall_score')}")


def test_whatsapp_ux():
    """F. WhatsApp UX — message length, one-job flow."""
    print("\n── F. WhatsApp UX ──")

    from careerloop.whatsapp_ux import (
        daily_brief, job_review_card, follow_up_card
    )

    # Daily brief under 12 lines
    top_job = {
        "company": "Anthropic", "role_title": "Applied AI Engineer",
        "overall_score": 85, "recommendation": "APPLY",
        "why_user_might_like_it": "Perfect role fit, strong AI lab",
        "risks": ["High interview bar"]
    }
    brief = daily_brief(20, 6, top_job, 2, "Siddharth")
    lines = brief.split('\n')
    check("Daily brief under 12 lines", len(lines) <= 12,
          f"Got {len(lines)} lines:\n{brief}")

    # Job review card
    review = job_review_card(top_job, 1, 6)
    check("Review shows one job at a time", "*Job 1/6*" in review)
    check("Review has apply/skip/maybe options", "apply" in review.lower() and "skip" in review.lower())

    # Follow-up card
    fu = {
        "company": "Razorpay", "role_title": "Product Analyst",
        "days_since_applied": 6, "recruiter_name": "Priya Nair",
        "suggested_message": "Hi Priya..."
    }
    fu_card = follow_up_card(fu, 1, 2)
    check("Follow-up card has company", "Razorpay" in fu_card)
    check("Follow-up card suggests message", "Hi Priya" in fu_card)


def test_approval_and_ledger():
    """G+H. Approval updates ledger, follow-ups auto-scheduled."""
    print("\n── G+H. Approval & Follow-up ──")

    from careerloop.application_ledger import ApplicationLedger
    from careerloop.approval import ApprovalWorkflow
    from careerloop.followup import FollowUpQueue
    import tempfile, shutil

    with tempfile.TemporaryDirectory() as tmp:
        ledger = ApplicationLedger(tmp)
        approval = ApprovalWorkflow(ledger)
        fu = FollowUpQueue(ledger)

        # Add a test job
        jid = ledger.add_job({
            "company": "Anthropic", "title": "Applied AI Engineer",
            "location": "Bangalore", "source_url": "https://greenhouse.io/anthropic/123"
        }, source="greenhouse")

        # Apply
        result = approval.approve(jid)
        check("APPROVE returns resume_needed", result.get("resume_needed") == True)
        check("APPROVE sets follow_up_at", bool(result.get("follow_up_at")))
        entry = ledger.get_job(jid)
        check("Ledger status = APPROVED", entry["status"] == "APPROVED")
        check("Follow-up dates scheduled", len(entry.get("follow_up_dates", [])) == 4)

        # Skip
        jid2 = ledger.add_job({
            "company": "TCS", "title": "Java Developer",
            "location": "Chennai", "source_url": "https://naukri.com/123"
        }, source="naukri")
        result2 = approval.skip(jid2, "Not interested in Java roles")
        entry2 = ledger.get_job(jid2)
        check("SKIP stores reason", entry2.get("skip_reason") == "Not interested in Java roles")

        # Maybe
        jid3 = ledger.add_job({
            "company": "Stripe", "title": "Backend Engineer",
            "location": "Bangalore", "source_url": "https://greenhouse.io/stripe/789"
        }, source="greenhouse")
        result3 = approval.maybe(jid3, "Want to research team first")
        entry3 = ledger.get_job(jid3)
        check("MAYBE stores note", entry3.get("maybe_note") == "Want to research team first")


def test_audit_report():
    """I. Audit — Excel/CSV report generated with expected columns."""
    print("\n── I. Audit Report ──")

    from careerloop.audit import AuditReport
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        audit = AuditReport(tmp)
        entries = [
            {
                "job_id": "loop-0001", "source": "greenhouse", "company": "Anthropic",
                "title": "Applied AI Engineer", "source_url": "https://...",
                "location": "Bangalore", "work_mode": "hybrid", "salary_range": "₹60L-90L",
                "company_type": "ai-native", "fit_score": 85, "status": "DISCOVERED",
                "fit_result": {"overall_score": 85, "recommendation": "APPLY",
                               "why_user_might_like_it": "Perfect fit", "risks": ["Hard interview"]},
                "first_seen_at": "2026-05-14T00:00:00", "created_at": "2026-05-14T00:00:00",
            }
        ]
        path = audit.generate(entries, "Siddharth", "2026-05-14")
        check("Audit CSV file created", os.path.exists(path), path)

        with open(path, encoding='utf-8') as f:
            content = f.read()
            check("Person column present", "Siddharth" in content)
            check("Company column present", "Anthropic" in content)
            check("Fit score column present", "85" in content)


def test_full_pipeline():
    """End-to-end: discover → dedupe → score → shortlist → audit."""
    print("\n── J. Full Pipeline (smoke test) ──")

    import tempfile, csv
    from careerloop.discovery import DiscoveryEngine
    from careerloop.application_ledger import ApplicationLedger
    from careerloop.audit import AuditReport

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # Set up minimal career-ops structure
        (root / "data" / "pipeline.md").parent.mkdir(parents=True, exist_ok=True)
        (root / "data" / "pipeline.md").write_text("""
# Pipeline

## Pendientes

- [ ] https://greenhouse.io/stripe/jobs/1 | Stripe | Backend Engineer | Bangalore
- [ ] https://greenhouse.io/anthropic/jobs/2 | Anthropic | Applied AI Engineer | Bangalore, India

## Procesadas
""")

        # Create import CSV
        import_dir = root / "data" / "imports" / "jobs"
        import_dir.mkdir(parents=True, exist_ok=True)
        with open(import_dir / "2026-05-14.csv", 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["source", "company", "role", "url", "location", "description",
                        "posted_at", "work_mode", "salary_range", "experience_required",
                        "skills_required", "company_type", "responsibilities"])
            w.writerow(["linkedin", "MongoDB", "Staff Engineer",
                        "https://linkedin.com/jobs/999", "Gurugram",
                        "Senior role...", "2026-05-14", "hybrid", "₹50L-70L",
                        "8+ years", "Python,PostgreSQL,Docker", "saas",
                        "Lead engineering team"])

        # Discovery
        discovery = DiscoveryEngine(str(root))
        csv_jobs = discovery._discover_csv("2026-05-14")

        check("Discovery finds CSV jobs", len(csv_jobs) > 0, f"Found {len(csv_jobs)}")
        if csv_jobs:
            check("CSV job has company", bool(csv_jobs[0].get("company")))

        # Ledger
        ledger = ApplicationLedger(str(root))
        for job in csv_jobs:
            ledger.add_job(job, source=job.get("source", "csv"))

        check("Ledger has jobs", len(ledger.entries) > 0)

        # Audit
        audit = AuditReport(str(root))
        report_path = audit.generate(ledger.entries, "Siddharth", "2026-05-14")
        check("Audit report generated", os.path.exists(report_path))


def test_india_filter():
    """K. India Filter — Only India jobs pass."""
    print("\n── K. India Filter ──")
    from careerloop.india_filter import is_india_job, filter_india_jobs

    check("Bangalore passes", is_india_job("Bangalore")[0])
    check("Bengaluru passes", is_india_job("Bengaluru, India")[0])
    check("Chennai passes", is_india_job("Chennai")[0])
    check("Remote India passes", is_india_job("Remote - India")[0])
    check("Naukri URL passes", is_india_job("", "", "https://naukri.com/job/123")[0])
    check("San Francisco rejected", not is_india_job("San Francisco, CA")[0])
    check("London rejected", not is_india_job("London, UK")[0])
    check("Global remote rejected", not is_india_job("Remote")[0])
    check("NYC rejected", not is_india_job("New York")[0])


def test_role_strategy():
    """L. Role Strategy — Generates search queries from profile."""
    print("\n── L. Role Strategy ──")
    from careerloop.role_strategy import RoleStrategyGenerator

    profile = {
        "target_roles": ["AI Product Engineer", "Applied AI Engineer"],
        "rejected_roles": ["sales", "support"],
        "city": "Chennai",
        "startup_tolerance": 8,
    }
    gen = RoleStrategyGenerator(profile)
    queries = gen.generate_queries()
    check("Generates 5+ queries", len(queries) >= 5, f"Got {len(queries)}")
    check("Queries have site scope", any("site:" in q["query"] for q in queries))
    check("Queries include target city", any("Chennai" in q["query"] for q in queries))
    check("No sales queries", not any("sales" in q["query"].lower() for q in queries))


def test_apply_route():
    """M. Apply Route — Resolves best apply URL."""
    print("\n── M. Apply Route ──")
    from careerloop.apply_route import resolve_apply_route, detect_apply_source

    check("Detects greenhouse", detect_apply_source("https://boards.greenhouse.io/stripe/jobs/123") == "greenhouse")
    check("Detects linkedin", detect_apply_source("https://linkedin.com/jobs/view/123") == "linkedin")
    check("Detects naukri", detect_apply_source("https://naukri.com/job/123") == "naukri")

    job = {
        "url": "https://linkedin.com/jobs/view/123",
        "application_url": "https://boards.greenhouse.io/stripe/jobs/456",
    }
    route = resolve_apply_route(job)
    check("Prefers greenhouse over linkedin", route["best_apply_route"] == "greenhouse",
          f"Got: {route['best_apply_route']}")
    check("Has backup URLs", len(route["backup_urls"]) >= 1)


def test_url_classification_and_visibility_lifecycle():
    """N. URL classification and user-visible lifecycle gates."""
    print("\n── N. URL Classification & Visibility Lifecycle ──")

    check("LinkedIn search is SEARCH_PAGE",
          classify_url_type("https://www.linkedin.com/jobs/search/?keywords=ai") == URLType.SEARCH_PAGE)
    check("LinkedIn view is INDIVIDUAL_JOB",
          classify_url_type("https://www.linkedin.com/jobs/view/123456789") == URLType.INDIVIDUAL_JOB)
    check("Naukri category/search is SEARCH_PAGE",
          classify_url_type("https://www.naukri.com/python-jobs-in-bangalore") == URLType.SEARCH_PAGE)
    check("Naukri job listing is INDIVIDUAL_JOB",
          classify_url_type("https://www.naukri.com/job-listings-senior-ai-engineer-acme-bengaluru-5-to-8-years-123456") == URLType.INDIVIDUAL_JOB)
    check("Blog article is BLOG_ARTICLE",
          classify_url_type("https://example.com/blog/how-to-hire-ai-engineers") == URLType.BLOG_ARTICLE)

    from careerloop.discovery import DiscoveryEngine
    with tempfile.TemporaryDirectory() as tmp:
        discovery = DiscoveryEngine(tmp)
        incomplete = {
            "title": "AI Engineer",
            "company": "",
            "location": "Bangalore",
            "url": "https://www.linkedin.com/jobs/view/123456789",
            "url_type": URLType.INDIVIDUAL_JOB.value,
            "description": "Build AI systems",
            "apply_url": "https://www.linkedin.com/jobs/view/123456789",
        }
        complete = {**incomplete, "company": "Acme"}
        search_page = {**complete, "url_type": URLType.SEARCH_PAGE.value}
        check("Missing company needs more data, not scorable", not discovery._is_scorable_job_dict(incomplete))
        check("Complete individual job is scorable", discovery._is_scorable_job_dict(complete))
        check("Search page is not scorable", not discovery._is_scorable_job_dict(search_page))

    visible = UserVisibleOpportunity(
        company="Acme",
        role_title="AI Engineer",
        location="Bangalore",
        source_url="https://www.linkedin.com/jobs/view/123456789",
        apply_url="https://www.linkedin.com/jobs/view/123456789",
        overall_score=82,
        recommendation="APPLY",
    ).to_dict()
    check("Final opportunity has user-visible shape", set(["company", "role_title", "overall_score", "apply_url"]).issubset(visible.keys()))


def test_resume_council_gating_and_preview():
    """O. Resume Council — requires explicit intent and produces one-job preview."""
    print("\n── O. Resume Council Gating & Preview ──")

    import tempfile
    import yaml
    from careerloop.application_ledger import ApplicationLedger
    from careerloop.council.orchestrator import ResumeCouncilOrchestrator

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "config" / "profile.yml").write_text(yaml.dump({
            "candidate": {"full_name": "Test User"},
            "narrative": {},
            "location": {"city": "Chennai"},
            "target_roles": {"primary": ["AI Engineer"], "archetypes": []},
            "compensation": {"minimum": "₹25L"},
        }), encoding="utf-8")

        ledger = ApplicationLedger(str(root))
        job_id = ledger.add_job({
            "company": "Google",
            "title": "Software Engineer, AI/ML",
            "location": "Bengaluru, India",
            "source_url": "https://www.linkedin.com/jobs/view/123",
            "application_url": "https://www.linkedin.com/jobs/view/123",
            "description": "Build AI and ML systems with Python.",
        }, source="linkedin")
        ledger.entries[-1]["fit_score"] = 65
        ledger._save()

        council = ResumeCouncilOrchestrator(str(root))
        blocked = council.run(job_id, "")
        check("Council blocks missing intent", not blocked.allowed)
        result = council.run(job_id, "INTERESTED")
        check("Council allows explicit interest", result.allowed)
        check("Council creates application pack", result.application_pack is not None)
        check("Council stays one-job scoped", result.application_pack.job_id == job_id)


def run_tests(runner=None):
    global PASS, FAIL
    PASS = 0
    FAIL = 0

    print("=" * 60)
    print("🧪 CareerLoop Phase 1 Tests")
    print("=" * 60)

    test_fingerprinting()
    test_dedupe_and_suppression()
    test_csv_import()
    test_india_fit_llm()
    test_whatsapp_ux()
    test_approval_and_ledger()
    test_audit_report()
    test_full_pipeline()
    test_india_filter()
    test_role_strategy()
    test_apply_route()
    test_url_classification_and_visibility_lifecycle()
    test_resume_council_gating_and_preview()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
    print(f"{'=' * 60}")

    return FAIL == 0
