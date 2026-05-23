"""
Siddharth job search runner — reads profile from test data/siddharth/
Dies loud on any error so we always know what broke.
"""
import json
import os
import sys
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# Load .env so DEEPSEEK_API_KEY is available to all adapters
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

PROFILE_PATH = os.path.join(ROOT, "test data/siddharth/profile.yml")
EXTENDED_PATH = os.path.join(ROOT, "test data/siddharth/profile_extended.yml")
OUTPUT_DIR = os.path.join(ROOT, "test data/output/siddharth")

ROLES = ["AI Product Engineer", "AI Systems Architect", "Full Stack AI Engineer"]
CITIES = ["Bangalore"]
MAX_RESULTS = 25


def die(msg: str):
    print(f"\n{'!'*60}", flush=True)
    print(f"💥 FATAL: {msg}", flush=True)
    print(f"{'!'*60}", flush=True)
    traceback.print_exc()
    sys.exit(1)


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "v3"
    print(f"\n{'#'*60}", flush=True)
    print(f"RUN SIDDHARTH {label} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"{'#'*60}\n", flush=True)

    try:
        from careerloop.on_demand import OnDemandSearch
    except Exception as e:
        die(f"Import failed: {e}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        searcher = OnDemandSearch(
            ROOT,
            profile_path=PROFILE_PATH,
            extended_profile_path=EXTENDED_PATH,
        )
    except Exception as e:
        die(f"OnDemandSearch init failed: {e}")

    all_results = []

    for role in ROLES:
        for city in CITIES:
            print(f"\n{'='*60}", flush=True)
            print(f"SEARCH: {role} — {city}", flush=True)
            print(f"{'='*60}", flush=True)

            try:
                result = searcher.run(
                    role=role,
                    city=city,
                    max_results=MAX_RESULTS,
                    portal_companies=20,
                    include_boards=True,
                )
            except Exception as e:
                print(f"\n💥 SEARCH FAILED for {role}/{city}: {e}", flush=True)
                traceback.print_exc()
                print("Continuing to next search...", flush=True)
                continue

            print(f"\nKeywords: {', '.join(result.keywords_used[:8])}", flush=True)
            print(f"Candidates: {result.candidate_count} → dedup: {result.after_dedup_count} → ranked: {len(result.ranked_jobs)}", flush=True)
            print(f"Elapsed: {result.elapsed_seconds}s", flush=True)
            for note in result.notes:
                print(f"  [{note}]", flush=True)

            print(f"\nTop {len(result.ranked_jobs)} jobs:", flush=True)
            for i, item in enumerate(result.ranked_jobs, 1):
                job = item["job"]
                co = job.get("company_name") or job.get("company") or "?"
                title = job.get("title", "")
                loc = job.get("location", "")
                src = job.get("_source_type", "")
                score = item["score"]
                url = job.get("apply_url") or job.get("url", "")
                print(f"  {i:2d}. [{score:5.1f}] {title} @ {co} | {loc} | {src}", flush=True)
                if url:
                    print(f"        {url[:90]}", flush=True)

            all_results.append({
                "role": role, "city": city,
                "stats": {
                    "candidates": result.candidate_count,
                    "after_dedup": result.after_dedup_count,
                    "ranked": len(result.ranked_jobs),
                    "elapsed_s": result.elapsed_seconds,
                    "keywords": result.keywords_used,
                    "companies_targeted": result.targeted_companies,
                    "notes": result.notes,
                },
                "ranked_jobs": result.ranked_jobs,
            })

    if not all_results:
        die("All searches failed — zero results collected")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = os.path.join(OUTPUT_DIR, f"siddharth_bangalore_{label}_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n{'='*60}", flush=True)
    print(f"Saved: {out_path}", flush=True)


if __name__ == "__main__":
    main()
