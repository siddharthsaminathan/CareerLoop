"""
Siddharth job search runner — full Phase A-G pipeline with live audit output.
Every phase prints clearly so you can watch exactly what's happening.
"""
import json
import os
import sys
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

PROFILE_PATH = os.path.join(ROOT, "test data/siddharth/profile.yml")
EXTENDED_PATH = os.path.join(ROOT, "test data/siddharth/profile_extended.yml")
OUTPUT_DIR = os.path.join(ROOT, "test data/output/siddharth")

ROLES = ["AI Product Engineer", "Full Stack AI Engineer", "Applied AI Engineer", "Founding AI Engineer"]
CITIES = ["Bangalore", "Mumbai", "Remote"]
MAX_RESULTS = 60  # per role×city — 4 roles × 3 cities × 60 = up to 720 candidates

TS = datetime.now().strftime("%Y%m%d_%H%M")
AUDIT_LOG = os.path.join(OUTPUT_DIR, f"audit_{TS}.log")


def banner(msg: str, char: str = "="):
    line = char * 60
    print(f"\n{line}", flush=True)
    print(f"  {msg}", flush=True)
    print(f"{line}", flush=True)


def phase(n: int, name: str):
    print(f"\n{'─'*60}", flush=True)
    print(f"  ▶ PHASE {n}: {name}", flush=True)
    print(f"{'─'*60}", flush=True)


def tick(msg: str):
    print(f"  ✓ {msg}", flush=True)


def info(msg: str):
    print(f"  · {msg}", flush=True)


def warn(msg: str):
    print(f"  ⚠ {msg}", flush=True)


def die(msg: str):
    print(f"\n{'!'*60}", flush=True)
    print(f"  💥 FATAL: {msg}", flush=True)
    print(f"{'!'*60}", flush=True)
    traceback.print_exc()
    sys.exit(1)


class TeeOutput:
    """Write to stdout AND audit log simultaneously."""
    def __init__(self, log_path: str):
        self._stdout = sys.stdout
        self._log = open(log_path, "w", buffering=1)

    def write(self, data):
        self._stdout.write(data)
        self._log.write(data)

    def flush(self):
        self._stdout.flush()
        self._log.flush()

    def close(self):
        self._log.close()
        sys.stdout = self._stdout

    # needed so tqdm/other libs don't explode
    def isatty(self):
        return False

    def fileno(self):
        return self._stdout.fileno()


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "v4"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Wire up audit tee
    tee = TeeOutput(AUDIT_LOG)
    sys.stdout = tee

    banner(f"CAREERLOOP SIDDHARTH FULL RUN — {label}")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"  Roles   : {', '.join(ROLES)}", flush=True)
    print(f"  Cities  : {', '.join(CITIES)}", flush=True)
    print(f"  Max/role: {MAX_RESULTS}", flush=True)
    print(f"  Audit   : {AUDIT_LOG}", flush=True)
    serpapi_active = bool(os.environ.get("SERPAPI_KEY"))
    print(f"  SerpAPI : {'✅ ACTIVE' if serpapi_active else '⚠ not set — DDG fallback'}", flush=True)
    deepseek_active = bool(os.environ.get("DEEPSEEK_API_KEY"))
    print(f"  DeepSeek: {'✅ ACTIVE' if deepseek_active else '⚠ not set — LLM steps will skip'}", flush=True)

    phase(0, "IMPORTS + INIT")
    try:
        from careerloop.on_demand import OnDemandSearch
        tick("on_demand.OnDemandSearch imported")
    except Exception as e:
        die(f"Import failed: {e}")

    try:
        searcher = OnDemandSearch(
            ROOT,
            profile_path=PROFILE_PATH,
            extended_profile_path=EXTENDED_PATH,
        )
        tick(f"OnDemandSearch ready — profile: {os.path.basename(PROFILE_PATH)}")
    except Exception as e:
        die(f"OnDemandSearch init failed: {e}")

    all_results = []
    total_jobs = 0

    for role in ROLES:
        for city in CITIES:
            banner(f"SEARCH: {role} @ {city}", char="━")

            phase(1, f"COMPANY DISCOVERY — {city} | {role}")
            info(f"SerpAPI queries targeting funded AI companies, anti-body-shop filters")
            info(f"Also hitting: Wellfound, Crunchbase, Inc42, YC")

            phase(2, "ATS FINGERPRINT + ADAPTER ROUTING")
            info(f"14 adapters: Greenhouse, Lever, Ashby, Workday, SmartRecruiters,")
            info(f"            SAP SuccessFactors, Taleo, iCIMS, TalentRecruit, Darwinbox,")
            info(f"            Workable, Teamtailor, Recruitee, BambooHR")

            phase(3, "JOB BOARD SCRAPE — parallel 6 sources")
            info(f"Sources: Naukri(XHR), JobSpy(LinkedIn+Indeed), Monster/Foundit,")
            info(f"         Glassdoor, Google Jobs, DDG Search")

            phase(4, "JD EXTRACTION — Playwright + DeepSeek")
            info(f"ScrapeGraph (Playwright+LLM) → Indeed JSON API → BeautifulSoup fallback")

            phase(5, "ROLE FILTER + SCORE")
            info(f"Embedding filter → source-aware weighting (+3 ATS, +1.5 scraped, +1 jobspy)")
            info(f"Anti-gatekeeping: rejecting IT outsourcing, body shops, hardware roles")

            phase(6, "LLM VALIDATOR — DeepSeek batch pass")
            info(f"Top-60 validated against role + culture fit")

            phase(7, "RANKING + OUTPUT")

            print(f"\n  🚀 Running pipeline now...\n", flush=True)

            try:
                result = searcher.run(
                    role=role,
                    city=city,
                    max_results=MAX_RESULTS,
                    portal_companies=40,
                    include_boards=True,
                    force_refresh=True,
                )
            except Exception as e:
                warn(f"SEARCH FAILED for {role}/{city}: {e}")
                traceback.print_exc()
                warn("Continuing to next search...")
                continue

            n_ranked = len(result.ranked_jobs)
            total_jobs += n_ranked

            banner(f"RESULTS: {role} @ {city}", char="─")
            print(f"  Keywords   : {', '.join(result.keywords_used[:10])}", flush=True)
            print(f"  Candidates : {result.candidate_count}", flush=True)
            print(f"  After dedup: {result.after_dedup_count}", flush=True)
            print(f"  Ranked     : {n_ranked}", flush=True)
            print(f"  Elapsed    : {result.elapsed_seconds:.1f}s", flush=True)
            for note in result.notes:
                info(note)

            print(f"\n  {'#':>3}  {'SCORE':>6}  {'TITLE':<45}  {'COMPANY':<30}  {'SRC'}", flush=True)
            print(f"  {'─'*3}  {'─'*6}  {'─'*45}  {'─'*30}  {'─'*15}", flush=True)
            for i, item in enumerate(result.ranked_jobs, 1):
                job = item["job"]
                co = (job.get("company_name") or job.get("company") or "?")[:30]
                title = job.get("title", "")[:45]
                src = job.get("_source_type", "")[:15]
                score = item["score"]
                url = job.get("apply_url") or job.get("url", "")
                print(f"  {i:>3}  {score:>6.1f}  {title:<45}  {co:<30}  {src}", flush=True)
                if url:
                    print(f"         → {url[:95]}", flush=True)

            all_results.append({
                "role": role, "city": city,
                "stats": {
                    "candidates": result.candidate_count,
                    "after_dedup": result.after_dedup_count,
                    "ranked": n_ranked,
                    "elapsed_s": result.elapsed_seconds,
                    "keywords": result.keywords_used,
                    "companies_targeted": result.targeted_companies,
                    "notes": result.notes,
                },
                "ranked_jobs": result.ranked_jobs,
            })

    if not all_results:
        die("All searches failed — zero results collected")

    banner("FINAL SUMMARY")
    print(f"  Roles searched : {len(ROLES)}", flush=True)
    print(f"  Total jobs     : {total_jobs}", flush=True)
    for r in all_results:
        print(f"  {r['role']}: {r['stats']['ranked']} ranked ({r['stats']['elapsed_s']:.1f}s)", flush=True)

    out_path = os.path.join(OUTPUT_DIR, f"siddharth_bangalore_{label}_{TS}.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    tick(f"Results saved: {out_path}")
    tick(f"Audit log   : {AUDIT_LOG}")

    if total_jobs >= 200:
        print(f"\n  🎯 ≥200 jobs found ({total_jobs}). Goal met.", flush=True)
    else:
        warn(f"Only {total_jobs} jobs found — may need more roles or broader search")

    tee.close()


if __name__ == "__main__":
    main()
