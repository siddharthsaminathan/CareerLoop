#!/usr/bin/env python3
"""
CareerLoop Live Test — End-to-end test with real India sources.

Runs the full pipeline and reports:
- Search queries generated
- Sources tried + per-source results
- India filter rejections
- Verification results
- Final verified shortlist
- Chat message sample
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

CAREER_OPS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CAREER_OPS_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_live_test():
    from careerloop.profile_manager import ProfileManager
    from careerloop.discovery import DiscoveryEngine
    from careerloop.whatsapp_ux import daily_brief, job_review_card

    print("=" * 60)
    print("🧪 CareerLoop Live Integration Test")
    print(f"   {datetime.now(timezone.utc).strftime('%B %d, %Y — %H:%M UTC')}")
    print("=" * 60)

    # Load profile
    profile_mgr = ProfileManager(CAREER_OPS_ROOT)
    profile = profile_mgr.get_full_profile()
    print(f"\n👤 Profile: {profile_mgr.full_name}")
    print(f"   Target roles: {profile.get('target_roles', [])}")
    print(f"   City: {profile.get('city', profile.get('location_city', ''))}")
    print(f"   Startup tolerance: {profile.get('startup_tolerance', 5)}/10")

    # Run discovery
    print("\n" + "─" * 60)
    print("📡 Running full discovery pipeline...")
    print("─" * 60)

    engine = DiscoveryEngine(CAREER_OPS_ROOT)
    report = engine.discover_india_jobs(profile)

    # Report queries
    print(f"\n📋 Queries Generated ({len(report['queries'])}):")
    for i, q in enumerate(report["queries"], 1):
        print(f"   {i}. {q['query']}")

    # Report per-source stats
    stats = report["source_stats"]
    print(f"\n📊 Source Results:")
    print(f"   DDG search URLs:      {stats.get('ddg_urls', 0)}")
    print(f"   JobSpy results:       {stats.get('jobspy_jobs', 0)}")
    print(f"   CSV imports:          {stats.get('csv_imports', 0)}")
    print(f"   ScrapeGraph extracted: {stats.get('scrapegraph_extracted', 0)}")
    print(f"   India filter passed:  {stats.get('india_passed', 0)}")
    print(f"   India filter rejected: {stats.get('india_rejected', 0)}")
    print(f"   After merge:          {stats.get('after_merge', 0)}")
    print(f"   Verified active:      {stats.get('verified_active', 0)}")
    print(f"   Final shortlist:      {stats.get('final_count', 0)}")

    # Report rejections
    rejected = report.get("rejected_jobs", [])
    if rejected:
        print(f"\n❌ Rejected ({len(rejected)}):")
        for j in rejected[:5]:
            print(f"   • {j.get('title','')} @ {j.get('company','')}: {j.get('_rejection_reason','')}")

    # Report unverified
    unverified = report.get("unverified_jobs", [])
    if unverified:
        print(f"\n⚠️  Unverified ({len(unverified)}):")
        for j in unverified[:5]:
            print(f"   • {j.get('title','')} @ {j.get('company','')}: {j.get('verification_reason','')}")

    # Final shortlist
    final = report.get("final_shortlist", [])
    print(f"\n✅ Final Verified India Jobs ({len(final)}):")
    for i, job in enumerate(final[:10], 1):
        route = getattr(job, 'application_url', '') or ''
        print(f"   {i}. {job.company} — {job.role_title}")
        print(f"      📍 {job.location} | Source: {job.source}")
        print(f"      🔗 {route[:80]}")

    # Chat sample
    if final:
        top = {
            "company": final[0].company,
            "role_title": final[0].role_title,
            "overall_score": 75,
            "why_user_might_like_it": "Verified active India job matching profile",
            "risks": ["Score pending LLM evaluation"],
        }
        brief = daily_brief(len(final), min(len(final), 5), top, 0,
                           profile_mgr.full_name.split()[0])
        print(f"\n💬 Chat Sample:")
        print("─" * 40)
        print(brief)
        print("─" * 40)
    else:
        print(f"\n💬 Chat Sample:")
        print("─" * 40)
        print(f"Morning, {profile_mgr.full_name.split()[0]}.")
        print(f"Searched {len(report['queries'])} queries across DDG + JobSpy.")
        print(f"Found {stats.get('ddg_urls',0)} URLs but {stats.get('verified_active',0)} verified.")
        if stats.get('india_rejected', 0) > 0:
            print(f"{stats['india_rejected']} jobs rejected (not India).")
        print("Will try again tomorrow with adjusted queries.")
        print("─" * 40)

    # Verdict
    print(f"\n{'=' * 60}")
    if len(final) >= 5:
        print("✅ PASS: 5+ verified active India jobs found")
    elif len(final) > 0:
        print(f"⚠️  PARTIAL: {len(final)} verified jobs (target: 5-10)")
        print("   Check which sources failed above")
    else:
        print("❌ FAIL: 0 verified India jobs")
        print("   Check search results and filter rejections above")
    print("=" * 60)

    return report


if __name__ == "__main__":
    run_live_test()
