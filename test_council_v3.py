"""
Validation suite for Resume Council v3.0 (8-System Architecture).
Runs the pipeline against 3 fixture profiles.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from careerloop.council.orchestrator import ResumeCouncilOrchestrator

NICOBAR_JD = """
Job Title: AI Product Engineer — CEO's Office
Company: Nicobar Design Pvt. Ltd. (nicobar.com)
Location: Delhi
Experience: 3-5 years

THE OPPORTUNITY
We’ve spent a decade building a brand that looks and feels unmistakably Nicobar. The next chapter is building a company that thinks the same way — every store, every collection, every customer conversation: sharper, faster, unmistakably ours. AI-native, not in theory, but in every room we walk into.

WHAT YOU’LL OWN
01 Customer Personalization : Build the intelligence layer beneath all our customer communication that understands who each customer actually is.
02 Store Clienteling : Build the clienteling tool our store teams reach for every day.
03 Business Intelligence : Replace Microsoft BI dashboards with a live, conversational intelligence layer.
04 Smoothen Design Workstreams : Remove friction so the creative team can make more, better, faster.

WHAT WE’RE LOOKING FOR
Engineering degree from IIT, BITS, NIT or equivalent with 3-5 years of experience.
You’ve built something real with an LLM API - OpenAI, Claude, Gemini, etc.
Fluent in Python/ NodeJS. Comfortable writing and querying SQL.
Ability to build front-ends that don’t embarrass the brand. We’re visual people.
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
    
    # We mock the ledger/loader by passing explicit data
    # Note: Our orchestrator needs a job object if data is provided explicitly.
    # I'll modify the orchestrator slightly to accept jd_text explicitly in initial_state.
    
    orchestrator = ResumeCouncilOrchestrator(root=str(ROOT))
    
    # For testing, we'll manually add the job to the ledger or just use the mock mode I added.
    # Actually, I'll just use a real job_id from the ledger for one run, 
    # but for fixtures, mock mode is better.
    
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

if __name__ == "__main__":
    fixtures = [
        ("experienced", "examples/fixtures/experienced_tech.md"),
        ("fresher", "examples/fixtures/fresher_ml.md"),
        ("business", "examples/fixtures/business_lead.md"),
    ]
    
    for p_id, p_path in fixtures:
        test_fixture(p_id, p_path)
