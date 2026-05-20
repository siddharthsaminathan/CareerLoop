"""
Run the 8-system LangGraph Resume Council against a real job.

Usage:
    python run_council.py --job-id loop-0129 --person siddharth
    python run_council.py --job-id varsha-hm-merchandiser --person varsha

Output for each run:
    output/council/{person}/{job_id}/
        00_input_snapshot.json
        01_canonical_resume.json
        02_preservation_contract.json
        03_company_intelligence.json
        04_role_decode.json
        05_user_truth.json
        06_positioning_strategy.json
        07_section_rewrites.json
        08_truth_guard_report.json
        09_s7_debug.json          ← per-section timing, model, rewrite stats
        10_final_resume.md        ← post-humanizer (final deliverable)
        11_cover_note.md
        12_pre_humanizer_resume.md← before humanizer
        12_humanized_resume.md    ← same as 10, explicit humanizer output
        13_humanizer_report.json
        14_humanizer_diff.patch
        15_quality_report.md
        17_council_run_log.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import yaml


# ─── Hardcoded JDs (fetched / constructed from real sources) ──────────────────

JD_BY_ID = {
    "loop-0129": {
        "title": "Gen AI Python Developer",
        "company": "Deloitte",
        "url": "https://www.linkedin.com/jobs/view/4399934799",
        "jd": """Job Title: Gen AI Python Developer
Company: Deloitte
Location: Chennai, Tamil Nadu, India
Employment Type: Full-Time, Hybrid
Experience Level: Mid-Senior (4-8 years)

Key Responsibilities:
- Design, develop, and deploy intelligent agents and multi-agent systems using Python frameworks
- Apply agentic design patterns for autonomous, collaborative AI solutions handling complex tasks
- Create robust API calls and microservices integrating AI models with existing platforms
- Develop clean, efficient Python code for generative AI applications
- Collaborate with data scientists, product managers, and engineers on requirements
- Implement testing protocols and CI/CD pipelines for production AI systems
- Stay current with generative AI advancements and agentic frameworks

Required Skills & Qualifications:
- Bachelor's degree in computer science, AI, or related field (or equivalent experience)
- 4+ years professional software development experience with Python focus
- Proven AI agent design and implementation experience
- Deep knowledge of agentic frameworks: LangChain, CrewAI, AutoGen
- RESTful APIs and microservice architecture experience
- Familiarity with generative AI concepts (LLMs, RAG, fine-tuning)
- Cloud platform experience (AWS, GCP, Azure)
- Containerization technologies: Docker, Kubernetes
- Git proficiency

Preferred Qualifications:
- Production-scale AI systems deployment experience
- Asynchronous Python programming knowledge (asyncio)
- SQL and NoSQL database experience
- Data security and privacy best practices understanding
- Portfolio demonstrating AI agent/application projects""",
    },
    "nicobar-ai-pm": {
        "title": "AI Product Engineer -- CEO's Office",
        "company": "Nicobar Design Pvt. Ltd.",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:7329475396732014592",
        "jd": """Job Title: AI Product Engineer -- CEO's Office
Company: Nicobar Design Pvt. Ltd. (nicobar.com)
Location: Delhi
Experience: 3-5 years

THE OPPORTUNITY
We've spent a decade building a brand that looks and feels unmistakably Nicobar. The next chapter is
building a company that thinks the same way -- AI-native, not in theory, but in every room we walk into.

WHAT YOU'LL OWN
01 Customer Personalization: Build the intelligence layer beneath all our customer communication
02 Store Clienteling: Build the clienteling tool our store teams reach for every day
03 Business Intelligence: Replace Microsoft BI dashboards with a live, conversational intelligence layer
04 Smoothen Design Workstreams: Remove friction so the creative team can make more, better, faster
05 Open Mandate: Demand forecasting, AI stylist, gifting concierge, supplier communication

WHAT WE'RE LOOKING FOR
Engineering degree from IIT, BITS, NIT or equivalent with 3-5 years of experience.
You've built something real with an LLM API - OpenAI, Claude, Gemini, etc.
Fluent in Python/NodeJS. Comfortable writing and querying SQL.
Comfortable connecting systems that weren't designed to talk to each other: APIs, webhooks, data pipelines.
Familiarity with Shopify's API ecosystem, or e-commerce data generally.
Experience with MoEngage or any CRM / marketing automation platform.
Exposure to ERP - Microsoft Dynamics 365.
Ability to build front-ends that don't embarrass the brand.""",
    },
    "varsha-hm-merchandiser": {
        "title": "Senior Merchandiser -- Women's Wear (Jersey)",
        "company": "H&M",
        "url": "https://www.linkedin.com/jobs/view/hm-senior-merchandiser-womens-wear",
        "jd": """Job Title: Senior Merchandiser -- Women's Wear (Jersey)
Company: H&M Group
Location: Bengaluru, India
Employment Type: Full-Time
Experience Level: 4-6 years

ABOUT THE ROLE
As a Senior Merchandiser in our Women's Wear Jersey team, you will drive range planning and
assortment strategy for one of our key product categories. You will work closely with the buying team,
designers, and regional teams to ensure the right product is in the right place at the right time -- at
the right price.

KEY RESPONSIBILITIES
- Own the OTB (Open-to-Buy) planning and management for the women's jersey category, ensuring
  optimal stock levels across channels and geographies
- Lead assortment planning for seasonal and replenishment ranges, balancing trend, commercial
  viability, and brand positioning
- Analyze weekly sales performance, sell-through rates, and margin data to make data-driven
  decisions on replenishment, markdowns, and range adjustments
- Collaborate with the buying team on range development, identifying trends and translating them
  into commercial assortment plans
- Manage supplier/vendor relationships, coordinating on production timelines, MOQs, and delivery
  schedules to ensure 95%+ on-time delivery
- Partner with regional teams (India, SEA) to understand local market needs and adapt assortment
  accordingly
- Drive category P&L performance by managing margins, stock turn, and sell-through KPIs
- Lead product lifecycle management (PLM) from range development through end-of-season clearance
- Conduct range reviews with cross-functional teams including design, marketing, and VM

WHAT WE'RE LOOKING FOR
- 4-6 years of experience in fashion buying, merchandising, or category management
- Demonstrated experience with OTB management and assortment planning
- Strong analytical skills -- Advanced Excel (pivot tables, VLOOKUP, data dashboards), experience
  with Metabase, Power BI, or similar BI tools is a plus
- Experience managing PO/PI coordination with multiple vendors and factories
- Understanding of womenswear trends, especially in the jersey/casualwear category
- Proven ability to manage multiple suppliers and factories across India and Asia
- Experience in both offline retail and e-commerce/omnichannel merchandising
- Familiarity with SAP or other ERP systems (PO/inventory tracking)
- Strong cross-functional collaboration skills -- you will work closely with buying, design, VM,
  marketing, and supply chain teams
- Excellent negotiation skills with track record of improving vendor pricing and MOQs

PREFERRED QUALIFICATIONS
- NIFT, Pearl Academy, or equivalent fashion institute qualification
- Experience with fast-fashion or value retail (knowledge of DMart, Zara, Zudio, Mango assortment
  strategies is a plus)
- Exposure to category launch or new market entry projects
- Experience building and operating WIP trackers and production calendars""",
    },
}


# ─── Person profiles ──────────────────────────────────────────────────────────

PERSON_CONFIGS = {
    "siddharth": {
        "cv_path": ROOT / "cv.md",
        "profile_path": ROOT / "config" / "profile.yml",
        "output_name": "siddharth",
    },
    "varsha": {
        "cv_path": ROOT / "test data" / "varsha_resume_0426.md",
        "profile_path": ROOT / "careerloop" / "profile_varsha.yml",
        "output_name": "varsha",
    },
}


# ─── Loaders ──────────────────────────────────────────────────────────────────

def load_person(person: str) -> tuple[str, dict]:
    """Load CV text and profile dict for a person."""
    cfg = PERSON_CONFIGS.get(person)
    if not cfg:
        raise ValueError(f"Unknown person '{person}'. Available: {list(PERSON_CONFIGS)}")

    cv_path = cfg["cv_path"]
    if not cv_path.exists():
        raise FileNotFoundError(f"CV not found: {cv_path}")
    cv_text = cv_path.read_text(encoding="utf-8")

    profile_path = cfg["profile_path"]
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}

    return cv_text, profile


def load_job(job_id: str) -> dict:
    if job_id in JD_BY_ID:
        return JD_BY_ID[job_id]
    # Try ledger
    ledger_path = ROOT / "careerloop" / "ledger.json"
    if ledger_path.exists():
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        jobs = list(data.values()) if isinstance(data, dict) else data
        for j in jobs:
            if j.get("job_id") == job_id:
                return {
                    "title": j.get("title", "Unknown"),
                    "company": j.get("company", "Unknown"),
                    "url": j.get("source_url", ""),
                    "jd": j.get("description") or j.get("jd") or "",
                }
    raise ValueError(f"Job '{job_id}' not found. Available: {list(JD_BY_ID)}")


# ─── Output printing ──────────────────────────────────────────────────────────

def _print_dict(data: dict, indent: int = 2) -> None:
    pad = " " * indent
    width = 72
    for key, value in data.items():
        if key in ("verdict", "raw"):
            continue
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            print(f"\n{pad}{label}:")
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        print(f"{pad}  {k}: {v}")
                    print()
                else:
                    wrapped = textwrap.fill(str(item), width=width - indent - 4,
                                            subsequent_indent=pad + "    ")
                    print(f"{pad}  - {wrapped}")
        elif isinstance(value, dict):
            print(f"\n{pad}{label}:")
            for k, v in value.items():
                print(f"{pad}  {k}: {v}")
        elif value is not None:
            wrapped = textwrap.fill(str(value), width=width - indent - 2,
                                    subsequent_indent=pad + "  ")
            print(f"\n{pad}{label}:\n{pad}  {wrapped}")


def print_stage(title: str, data: dict | None) -> None:
    if not data:
        print(f"\n{'=' * 72}")
        print(f"  {title}")
        print("  (no output)")
        return
    verdict = data.get("verdict", data.get("summary", ""))
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    if verdict:
        print(f"\n  VERDICT: {verdict}")
    _print_dict(data)


def print_truth_guard_report(state: dict) -> None:
    report = state.get("truth_guard_report")
    if not report:
        print("\n  (truth_guard_report not found in state)")
        return
    print(f"\n{'=' * 72}")
    print("  TRUTH GUARD REPORT")
    print(f"\n  Claims scanned:   {report.get('total_claims', '?')}")
    print(f"  Verified:         {report.get('verified', '?')}")
    print(f"  Weak:             {report.get('weak', '?')}")
    print(f"  Unsupported:      {report.get('unsupported', '?')}")
    print(f"  Exaggerated:      {report.get('exaggerated', '?')}")
    print(f"  Fabricated:       {report.get('fabricated', '?')}")
    print(f"  Repairs applied:  {report.get('repairs_applied', '?')}")
    all_claims = report.get("claims", [])
    flagged = [c for c in all_claims if c.get("risk_level") not in ("VERIFIED", "WEAK", "UNCLASSIFIED")]
    if flagged:
        print(f"\n  Flagged claims ({len(flagged)}):")
        for f in flagged:
            print(f"    [{f.get('risk_level','?')}] {str(f.get('text',''))[:80]}")
            if f.get("repair_suggestion"):
                print(f"          -> {str(f.get('repair_suggestion',''))[:80]}")
    if all_claims:
        verified = [c for c in all_claims if c.get("risk_level") == "VERIFIED"]
        if verified:
            print(f"\n  Verified claims ({len(verified)}):")
            for c in verified:
                print(f"    [VERIFIED] {str(c.get('text',''))[:80]}")


# ─── Main runner ──────────────────────────────────────────────────────────────

def run_council(job_id: str, person: str = "siddharth", intent: str = "INTERESTED") -> dict:
    from careerloop.council.graph import get_council_graph

    job = load_job(job_id)
    cv_text, profile = load_person(person)
    person_label = PERSON_CONFIGS[person]["output_name"]

    print(f"\n{'#' * 72}")
    print(f"  CareerLoop Resume Council v3.0 -- LangGraph Edition")
    print(f"  Person: {person_label}")
    print(f"  Job:    {job['title']} @ {job['company']}")
    print(f"  Intent: {intent}")
    print(f"{'#' * 72}")

    initial_state = {
        # Required by new 8-system graph
        "job_id": job_id,
        "person_id": person_label,
        "job_title": job["title"],
        "company": job["company"],
        "job_url": job["url"],
        "jd_text": job["jd"],
        "master_cv": cv_text,
        "profile": profile,
        "today": datetime.now().strftime("%B %Y"),
        # Stage outputs (all None at start)
        "canonical_resume": None,
        "preservation_contract": None,
        "company_intelligence": None,
        "role_decode": None,
        "user_truth": None,
        "positioning_strategy": None,
        "section_rewrites": None,
        "application_pack": None,
        "truth_guard_report": None,
        "pre_humanizer_resume": None,
        "humanizer_output": None,
        "humanizer_report": None,
        "s7_debug": None,
        "errors": [],
    }

    graph = get_council_graph()
    final_state = graph.invoke(initial_state)

    # ── Print all 8 systems ──────────────────────────────────────────────────
    stages = [
        ("System 1 - Document Parser",       final_state.get("canonical_resume")),
        ("System 2 - Preservation Contract", final_state.get("preservation_contract")),
        ("System 3 - Company Intelligence",  final_state.get("company_intelligence")),
        ("System 4 - Role Decoder",          final_state.get("role_decode")),
        ("System 5 - User Truth",            final_state.get("user_truth")),
        ("System 6 - Positioning Strategy",  final_state.get("positioning_strategy")),
        ("System 7 - Section Rewrites",      final_state.get("section_rewrites")),
        ("System 8 - Application Pack",      final_state.get("application_pack")),
    ]

    for title, data in stages:
        print_stage(title, data)

    # ── Truth Guard report ───────────────────────────────────────────────────
    print(f"\n{'#' * 72}")
    print("  TRUTH GUARD FINDINGS")
    print(f"{'#' * 72}")
    print_truth_guard_report(final_state)

    # ── Errors ───────────────────────────────────────────────────────────────
    errors = final_state.get("errors", [])
    if errors:
        print(f"\n{'!' * 72}")
        print(f"  PIPELINE ERRORS ({len(errors)})")
        for e in errors:
            print(f"  !! {e}")

    # ── Save artifacts ───────────────────────────────────────────────────────
    output_dir = ROOT / "output" / "council" / person_label / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage JSONs
    stage_files = {
        "00_input_snapshot.json": {k: v for k, v in initial_state.items() if k != "master_cv"},
        "01_canonical_resume.json": final_state.get("canonical_resume"),
        "02_preservation_contract.json": final_state.get("preservation_contract"),
        "03_company_intelligence.json": final_state.get("company_intelligence"),
        "04_role_decode.json": final_state.get("role_decode"),
        "05_user_truth.json": final_state.get("user_truth"),
        "06_positioning_strategy.json": final_state.get("positioning_strategy"),
        "07_section_rewrites.json": final_state.get("section_rewrites"),
        "08_truth_guard_report.json": final_state.get("truth_guard_report"),
    }
    for fname, data in stage_files.items():
        if data is not None:
            with open(output_dir / fname, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    # Application pack artifacts
    pack = final_state.get("application_pack") or {}
    if pack.get("resume_markdown"):
        (output_dir / "10_final_resume.md").write_text(pack["resume_markdown"], encoding="utf-8")
    if pack.get("cover_note"):
        (output_dir / "11_cover_note.md").write_text(pack["cover_note"], encoding="utf-8")
    if pack.get("quality_report"):
        qr = pack["quality_report"]
        lines = ["# Quality Report\n", f"## Score: {qr.get('overall_score', '?')}/10\n"]
        if qr.get("what_changed"):
            lines += ["\n## What Changed\n"] + [f"- {x}\n" for x in qr["what_changed"]]
        if qr.get("warnings"):
            lines += ["\n## Warnings\n"] + [f"- {x}\n" for x in qr["warnings"]]
        (output_dir / "15_quality_report.md").write_text("".join(lines), encoding="utf-8")

    # S7 debug artifact (per-section timing, model, rewrite stats)
    s7_debug = final_state.get("s7_debug")
    if s7_debug:
        with open(output_dir / "09_s7_debug.json", "w", encoding="utf-8") as f:
            json.dump(s7_debug, f, indent=2, ensure_ascii=False)

    # Humanizer before/after artifacts
    pre_humanizer = final_state.get("pre_humanizer_resume", "")
    if pre_humanizer:
        (output_dir / "12_pre_humanizer_resume.md").write_text(pre_humanizer, encoding="utf-8")
    humanizer_text = final_state.get("humanizer_output", "")
    if humanizer_text:
        (output_dir / "12_humanized_resume.md").write_text(humanizer_text, encoding="utf-8")
    humanizer_rpt = final_state.get("humanizer_report")
    if humanizer_rpt:
        with open(output_dir / "13_humanizer_report.json", "w", encoding="utf-8") as f:
            json.dump(humanizer_rpt, f, indent=2)
    if pre_humanizer and pack.get("resume_markdown"):
        import difflib
        diff_lines = list(
            difflib.unified_diff(
                pre_humanizer.splitlines(),
                pack.get("resume_markdown", "").splitlines(),
                fromfile="pre_humanizer",
                tofile="final_resume",
                lineterm="",
            )
        )
        (output_dir / "14_humanizer_diff.patch").write_text("\n".join(diff_lines), encoding="utf-8")

    # Full run log
    with open(output_dir / "17_council_run_log.json", "w", encoding="utf-8") as f:
        json.dump(final_state, f, indent=2, ensure_ascii=False, default=str)

    # Render HTML and PDFs
    if pack.get("resume_markdown"):
        try:
            from careerloop.rendering.render_all_templates import render_resume
            print(f"\n{'-' * 72}")
            print("  Rendering 9 Templates...")
            render_resume(
                input_path=output_dir / "10_final_resume.md",
                candidate=person_label,
                run_id=job_id,
                out_dir=output_dir / "rendered",
                generate_pdf=True
            )
        except Exception as e:
            print(f"  !! Rendering failed: {e}")

    print(f"\n{'-' * 72}")
    print(f"  Artifacts saved -> {output_dir}")
    print(f"{'-' * 72}\n")

    return final_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Resume Council v3.0")
    parser.add_argument("--job-id", default="loop-0129")
    parser.add_argument("--person", default="siddharth",
                        choices=list(PERSON_CONFIGS.keys()),
                        help="Whose CV and profile to use")
    parser.add_argument("--intent", default="INTERESTED",
                        choices=["INTERESTED", "APPLY", "PREPARE_APPLICATION"])
    parser.add_argument("--force-refresh-s3", action="store_true", help="Skip S3 cache and force fresh research")
    args = parser.parse_args()
    
    if args.force_refresh_s3:
        os.environ["CAREERLOOP_FORCE_REFRESH_S3"] = "1"
        
    run_council(args.job_id, person=args.person, intent=args.intent)
