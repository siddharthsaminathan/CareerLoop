"""
Run the LangGraph Resume Council against a real job.

Usage:
    python run_council.py --job-id loop-0129

All 7 stage verdicts are printed to stdout.
Full JSON result is saved to output/council-{job_id}.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import textwrap
from pathlib import Path

# Force UTF-8 output on Windows so box-drawing chars don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Deloitte JD — fetched from LinkedIn (loop-0129)
DELOITTE_JD = """
Job Title: Gen AI Python Developer
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
- Portfolio demonstrating AI agent/application projects

About the Role:
Part of Deloitte's Technology & Transformation practice, this position focuses on converting data
into actionable information supporting data-driven decision-making through advanced analytics and
AI technologies.
""".strip()


JD_BY_ID = {
    "loop-0129": {
        "title": "Gen AI Python Developer",
        "company": "Deloitte",
        "url": "https://www.linkedin.com/jobs/view/4399934799",
        "jd": DELOITTE_JD,
    },
    "nicobar-ai-pm": {
        "title": "AI Product Engineer — CEO's Office",
        "company": "Nicobar Design Pvt. Ltd.",
        "url": "https://www.linkedin.com/feed/update/urn:li:activity:7329475396732014592",
        "jd": """Job Title: AI Product Engineer — CEO's Office
Company: Nicobar Design Pvt. Ltd. (nicobar.com)
Location: India
Employment Type: Full-Time

About Nicobar:
Nicobar is a design-first Indian lifestyle brand that has spent a decade building a brand that looks and feels unmistakably Nicobar. Now they want to build a company that thinks and operates the same way — evolving from a human-centered digital brand into a human-centered AI brand that retains Soul and Authenticity.

Role Context:
This is a greenfield mandate in the CEO's Office — no legacy systems, no committees. Just real problems and full room to build. You'll work directly with the Co-Founder (Raul Rai) and CEO.

What You'll Own:
1. Personalisation at scale — so every customer feels known and remembered, not marketed to
2. Store clienteling — so every store associate starts interactions already knowing the customer
3. Conversational BI — so any team can address any question with real answers in seconds
4. Design Team Workstreams — remove friction so the creative team can make more, better, faster

What They're Looking For:
- Engineers who think about business outcomes first and can explain what they're building and why (with conviction) to cross-functional teams
- NOT someone who chases AI trends
- Someone who can find and prioritize other areas where AI can bring transformation — areas they haven't thought of yet

Requirements:
- Must share something relevant built in past experience: a GitHub repo, a deployed tool, or a short Loom walkthrough
- Must add a brief description explaining what was done and its business impact""",
    },
}


def load_cv() -> str:
    cv_path = ROOT / "cv.md"
    if cv_path.exists():
        return cv_path.read_text(encoding="utf-8")
    raise FileNotFoundError("cv.md not found — run setup first")


def load_profile() -> dict:
    import yaml
    profile_path = ROOT / "config" / "profile.yml"
    if profile_path.exists():
        return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    return {}


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
    raise ValueError(f"Job {job_id} not found and no JD available")


def print_section(title: str, data: dict) -> None:
    width = 72
    if "raw" in data:
        print(textwrap.fill(data["raw"], width=width))
        return
    for key, value in data.items():
        if key == "verdict":
            continue
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            print(f"\n  {label}:")
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        print(f"    {k}: {v}")
                    print()
                else:
                    print(f"    - {item}")
        elif isinstance(value, dict):
            print(f"\n  {label}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"\n  {label}:\n  {textwrap.fill(str(value), width=width - 2, subsequent_indent='  ')}")


def run_council(job_id: str, intent: str = "INTERESTED") -> dict:
    from careerloop.council.graph import get_council_graph

    job = load_job(job_id)
    cv = load_cv()
    profile = load_profile()

    print(f"\n{'#' * 72}")
    print(f"  CareerLoop Resume Council -- LangGraph Edition")
    print(f"  Job:    {job['title']} @ {job['company']}")
    print(f"  Intent: {intent}")
    print(f"{'#' * 72}")

    initial_state = {
        "job_id": job_id,
        "intent": intent,
        "job_title": job["title"],
        "company": job["company"],
        "job_url": job["url"],
        "jd_text": job["jd"],
        "cv_text": cv,
        "profile": profile,
        "company_intelligence": None,
        "role_decode": None,
        "user_truth": None,
        "fit_gap": None,
        "positioning": None,
        "resume_plan": None,
        "application_pack": None,
        "errors": [],
    }

    graph = get_council_graph()
    final_state = graph.invoke(initial_state)

    # ── Print full verdicts ──────────────────────────────────────────────────
    stages = [
        ("Stage 1 · Company Intelligence", final_state.get("company_intelligence") or {}),
        ("Stage 2 · Role Decode",          final_state.get("role_decode") or {}),
        ("Stage 3 · User Truth Check",     final_state.get("user_truth") or {}),
        ("Stage 4 · Fit / Gap Analysis",   final_state.get("fit_gap") or {}),
        ("Stage 5 · Positioning Strategy", final_state.get("positioning") or {}),
        ("Stage 6 · Resume Plan",          final_state.get("resume_plan") or {}),
        ("Stage 7 · Application Pack",     final_state.get("application_pack") or {}),
    ]

    for title, data in stages:
        verdict = data.get("verdict", "")
        print(f"\n\n{'=' * 72}")
        print(f"  {title}")
        if verdict:
            print(f"\n  VERDICT: {verdict}")
        print_section(title, data)

    # ── Save full JSON ───────────────────────────────────────────────────────
    output_dir = ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / f"council-{job_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_state, f, indent=2, ensure_ascii=False)
    print(f"\n\n{'-' * 72}")
    print(f"  Full council saved -> {out_file}")
    print(f"{'-' * 72}\n")

    return final_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LangGraph Resume Council")
    parser.add_argument("--job-id", default="loop-0129", help="Job ID from ledger")
    parser.add_argument("--intent", default="INTERESTED",
                        choices=["INTERESTED", "APPLY", "PREPARE_APPLICATION"])
    args = parser.parse_args()
    run_council(args.job_id, args.intent)
