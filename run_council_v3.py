"""
Run the Resume Council v3.0 against a real job.
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from careerloop.council.orchestrator import ResumeCouncilOrchestrator

def run_council_v3(job_id: str, intent: str, person_id: str = "default"):
    """
    Main entry point for running the 8-system Resume Council pipeline.
    """
    print(f"\n{'#'*72}")
    print(f"  Resume Council v3.0 (8-System Architecture)")
    print(f"  Job:    {job_id}")
    print(f"  Person: {person_id}")
    print(f"{'#'*72}\n")

    orchestrator = ResumeCouncilOrchestrator(root=str(ROOT))
    result = orchestrator.run(job_id, intent, person_id)

    if result.application_pack:
        print(f"\n[SUCCESS] Application Pack generated at: {result.output_dir}")
        print("-" * 72)
        print(f"User Summary: {result.application_pack.user_review_summary}")
        print("-" * 72)
    else:
        print("\n[FAILURE] Resume Council run failed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Resume Council v3.0")
    parser.add_argument("--job-id", required=True, help="Job ID from ledger or fixture")
    parser.add_argument("--person-id", default="default", help="Person ID for output organization")
    parser.add_argument("--intent", default="PREPARE_APPLICATION",
                        choices=["INTERESTED", "APPLY", "PREPARE_APPLICATION"])
    args = parser.parse_args()
    
    run_council_v3(args.job_id, args.intent, args.person_id)
