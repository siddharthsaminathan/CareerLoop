#!/usr/bin/env python3
"""
End-to-end dry run: Hayagreev's resume → AI product roles → Chennai + Bangalore.

Reads resume from 'test data/hayagreev_resume_0426.md', runs OnDemandSearch
for each (role, city) combination, scores with IndiaFitEngine, saves output.

Usage: python3 dry_run_hayagreev.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s [%(name)s]: %(message)s",
)
# Show info from our own modules
logging.getLogger("careerloop").setLevel(logging.INFO)

RESUME_PATH = os.path.join(ROOT, "test data", "hayagreev_resume_0426.md")
OUTPUT_DIR = os.path.join(ROOT, "test data", "output")
ROLES = ["AI product engineer", "AI product manager"]
CITIES = ["Chennai", "Bangalore"]
MAX_RESULTS_PER_RUN = 50


def load_resume(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def print_section(title: str):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)


def print_job(rank: int, scored: dict):
    job = scored.get("job", scored)
    score = scored.get("score", 0)
    breakdown = scored.get("breakdown", {})
    title = job.get("title", "(no title)")
    company = job.get("company", "(unknown company)")
    location = job.get("location", "")
    url = job.get("apply_url") or job.get("url", "")
    source = job.get("_source_type", "")
    print(f"\n  [{rank}] Score: {score}/100")
    print(f"       {company} — {title}")
    print(f"       Location: {location}  |  Source: {source}")
    print(f"       URL: {url}")
    if breakdown:
        # breakdown values may be dicts {raw, weighted} or plain numbers
        def _dim_val(v):
            if isinstance(v, dict):
                return v.get("weighted", v.get("raw", 0))
            return float(v) if v else 0
        top_dims = sorted(breakdown.items(), key=lambda x: -_dim_val(x[1]))[:5]
        dims_str = ", ".join(f"{k}={round(_dim_val(v),1)}" for k, v in top_dims)
        print(f"       Top dims: {dims_str}")


def run():
    print_section("CareerLoop — End-to-End Dry Run")
    print(f"  Candidate: Hayagreev Sivakumar")
    print(f"  Roles: {', '.join(ROLES)}")
    print(f"  Cities: {', '.join(CITIES)}")
    print(f"  Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    resume_text = load_resume(RESUME_PATH)
    print(f"\n  Resume loaded: {len(resume_text)} chars")

    from careerloop.on_demand import OnDemandSearch

    searcher = OnDemandSearch(ROOT)

    all_results = []
    combos = [(role, city) for role in ROLES for city in CITIES]
    total_combos = len(combos)

    for i, (role, city) in enumerate(combos, 1):
        print_section(f"[{i}/{total_combos}] {role} / {city}")
        t0 = time.time()

        try:
            result = searcher.run(
                role=role,
                city=city,
                max_results=MAX_RESULTS_PER_RUN,
                portal_companies=20,
                include_boards=True,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

        elapsed = round(time.time() - t0, 2)
        print(f"\n  Keywords used: {', '.join(result.keywords_used[:6])}")
        print(f"  Raw candidates: {result.candidate_count}  →  after dedup: {result.after_dedup_count}")
        print(f"  Elapsed: {elapsed}s")
        if result.notes:
            for note in result.notes:
                print(f"  Note: {note}")

        if result.ranked_jobs:
            print(f"\n  Ranked results ({len(result.ranked_jobs)}):")
            for rank, scored in enumerate(result.ranked_jobs, 1):
                print_job(rank, scored)
        else:
            print("  No jobs found for this combo.")

        all_results.append({
            "role": role,
            "city": city,
            "keywords_used": result.keywords_used,
            "candidate_count": result.candidate_count,
            "after_dedup_count": result.after_dedup_count,
            "elapsed_seconds": elapsed,
            "notes": result.notes,
            "ranked_jobs": result.ranked_jobs,
        })

    # ── Save output ────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    json_path = os.path.join(OUTPUT_DIR, f"dry_run_hayagreev_{stamp}.json")
    md_path = os.path.join(OUTPUT_DIR, f"dry_run_hayagreev_{stamp}.md")

    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    _write_markdown(md_path, all_results)

    print_section("Summary")
    total_jobs = sum(len(r["ranked_jobs"]) for r in all_results)
    print(f"  Total ranked jobs across all combos: {total_jobs}")
    print(f"  Output JSON: {json_path}")
    print(f"  Output MD:   {md_path}")
    print()


def _write_markdown(path: str, all_results: list):
    lines = [
        "# CareerLoop Dry Run — Hayagreev Sivakumar\n",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n",
        f"**Roles:** AI product engineer, AI product manager  \n",
        f"**Cities:** Chennai, Bangalore  \n\n",
        "---\n",
    ]
    for r in all_results:
        lines.append(f"\n## {r['role']} / {r['city']}\n\n")
        lines.append(f"- **Keywords:** {', '.join(r['keywords_used'][:6])}  \n")
        lines.append(f"- **Raw candidates:** {r['candidate_count']} → after dedup: {r['after_dedup_count']}  \n")
        lines.append(f"- **Elapsed:** {r['elapsed_seconds']}s  \n")
        if r["notes"]:
            lines.append(f"- **Notes:** {'; '.join(r['notes'])}  \n")
        lines.append("\n")
        if r["ranked_jobs"]:
            lines.append("| Rank | Score | Company | Role | Location | URL |\n")
            lines.append("|------|-------|---------|------|----------|-----|\n")
            for rank, scored in enumerate(r["ranked_jobs"], 1):
                job = scored.get("job", scored)
                score = scored.get("score", 0)
                company = job.get("company", "?")
                title = job.get("title", "?")
                loc = job.get("location", "")
                url = job.get("apply_url") or job.get("url", "")
                url_md = f"[link]({url})" if url else "-"
                lines.append(f"| {rank} | {score}/100 | {company} | {title} | {loc} | {url_md} |\n")
        else:
            lines.append("_No results found._\n")

    with open(path, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    run()
