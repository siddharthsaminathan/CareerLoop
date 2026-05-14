"""
One-job Resume Council orchestrator.

Usage:
  python -m careerloop.council.orchestrator --job-id loop-0135 --intent INTERESTED
"""

import argparse
import json
import os
import sys

CAREER_OPS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, CAREER_OPS_ROOT)

from careerloop.council.context import CouncilContextLoader
from careerloop.council.models import CouncilResult
from careerloop.council.stages import (
    analyze_fit_gap,
    assemble_application_pack,
    build_company_intelligence,
    build_positioning,
    build_resume_plan,
    check_user_truth,
    decode_role,
)


class ResumeCouncilOrchestrator:
    def __init__(self, root: str = None):
        self.root = root or CAREER_OPS_ROOT
        self.context_loader = CouncilContextLoader(self.root)

    def run(self, job_id: str, intent: str) -> CouncilResult:
        loaded = self.context_loader.load(job_id, intent)
        if not loaded.allowed or not loaded.context:
            return loaded

        context = loaded.context
        company = build_company_intelligence(context)
        role = decode_role(context)
        truth = check_user_truth(context, role)
        gaps = analyze_fit_gap(role, truth, context.job)
        positioning = build_positioning(context, company, role, truth, gaps)
        plan = build_resume_plan(role, gaps, positioning)
        pack = assemble_application_pack(context, positioning, gaps, plan)

        return CouncilResult(
            allowed=True,
            reason="Resume Council preview generated. User review required before any application action.",
            context=context,
            company_intelligence=company,
            role_decode=role,
            user_truth=truth,
            fit_gap_analysis=gaps,
            positioning_strategy=positioning,
            resume_plan=plan,
            application_pack=pack,
        )


def main():
    parser = argparse.ArgumentParser(description="Run Resume Council for one selected job.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--intent", required=True, choices=["INTERESTED", "APPLY", "PREPARE_APPLICATION"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = ResumeCouncilOrchestrator().run(args.job_id, args.intent)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    print("=" * 60)
    print("CareerLoop Resume Council — Phase 2 Preview")
    print("=" * 60)
    print(result.reason)
    if not result.allowed or not result.application_pack:
        return
    print()
    print(result.application_pack.whatsapp_review_summary)
    print()
    print("Quality report:")
    for k, v in result.application_pack.quality_report.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
