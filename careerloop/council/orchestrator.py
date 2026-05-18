import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

from careerloop.council.context import CouncilContextLoader
from careerloop.council.graph import get_council_graph
from careerloop.council.models import (
    CouncilResult,
    CanonicalResume,
    PreservationContract,
    CompanyIntelligence,
    RoleDecode,
    UserTruth,
    PositioningStrategy,
    SectionRewrites,
    ApplicationPack,
    QualityReport,
)
from careerloop.council.runtime_context import get_runtime_context
from careerloop.council.safe_model import safe_construct

CAREER_OPS_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, CAREER_OPS_ROOT)


class ResumeCouncilOrchestrator:
    def __init__(self, root: str = None):
        self.root = root or CAREER_OPS_ROOT
        self.context_loader = CouncilContextLoader(self.root)

    def run(
        self,
        job_id: str,
        intent: str,
        person_id: str = "default",
        master_cv: Optional[str] = None,
        user_profile: Optional[dict] = None,
    ) -> CouncilResult:

        # Load from context loader if not provided (default behavior)
        if not master_cv or not user_profile:
            loaded = self.context_loader.load(job_id, intent)
            if not loaded.allowed or not loaded.context:
                return loaded

            context = loaded.context
            master_cv = master_cv or context.master_profile
            user_profile = user_profile or context.user_profile
            job_data = context.job
        else:
            # Fixture mode
            if job_id == "nicobar-test":
                from test_council_v3 import NICOBAR_JD

                job_data = {
                    "title": "AI Product Engineer",
                    "company": "Nicobar Design Pvt. Ltd.",
                    "description": NICOBAR_JD,
                    "source_url": "https://example.com",
                }
            else:
                job_data = {
                    "title": "AI Product Engineer",
                    "company": "Nicobar Design Pvt. Ltd.",
                    "description": "...",
                    "source_url": "https://example.com",
                }

        # Output directory setup
        output_dir = os.path.join(
            self.root, "output", "council", person_id, job_id
        )
        os.makedirs(output_dir, exist_ok=True)

        # Use runtime context for today — never hardcode dates
        ctx = get_runtime_context()

        initial_state = {
            "job_id": job_id,
            "person_id": person_id,
            "job_title": job_data.get("title", ""),
            "company": job_data.get("company", ""),
            "job_url": job_data.get("source_url", ""),
            "jd_text": job_data.get("description", ""),
            "master_cv": master_cv,
            "profile": user_profile,
            "today": ctx["current_month"],
            "errors": [],
            "canonical_resume": None,
            "preservation_contract": None,
            "company_intelligence": None,
            "role_decode": None,
            "user_truth": None,
            "positioning_strategy": None,
            "section_rewrites": None,
            "application_pack": None,
        }

        # Save input snapshot
        with open(os.path.join(output_dir, "00_input_snapshot.json"), "w") as f:
            json.dump(
                {k: v for k, v in initial_state.items() if k != "master_cv"},
                f,
                indent=2,
            )

        # Invoke the LangGraph
        print(
            f"--- Running Resume Council v3.0 for "
            f"{initial_state['job_title']} at {initial_state['company']} ---"
        )
        graph = get_council_graph()
        final_state = graph.invoke(initial_state)

        # Check for errors — write failure report if any node failed
        errors = final_state.get("errors", [])
        if errors:
            print(f"\n  !! Council completed with {len(errors)} error(s)")
            failure_path = os.path.join(output_dir, "failure_report.md")
            failure_report = final_state.get("application_pack", {}).get(
                "failure_report", ""
            )
            if not failure_report:
                failure_report = _build_failure_report(
                    ctx, job_data, errors
                )
            with open(failure_path, "w") as f:
                f.write(failure_report)
            print(f"  → Failure report written to {failure_path}")

        # Save artifacts
        self._save_artifacts(output_dir, final_state)

        # Map state back to CouncilResult using safe_construct
        return CouncilResult(
            job_id=job_id,
            person_id=person_id,
            canonical_resume=safe_construct(
                CanonicalResume, final_state["canonical_resume"]
            )
            if final_state["canonical_resume"]
            else None,
            preservation_contract=safe_construct(
                PreservationContract, final_state["preservation_contract"]
            )
            if final_state["preservation_contract"]
            else None,
            company_intelligence=safe_construct(
                CompanyIntelligence, final_state["company_intelligence"]
            )
            if final_state["company_intelligence"]
            else None,
            role_decode=safe_construct(
                RoleDecode, final_state["role_decode"]
            )
            if final_state["role_decode"]
            else None,
            user_truth=safe_construct(
                UserTruth, final_state["user_truth"]
            )
            if final_state["user_truth"]
            else None,
            positioning_strategy=safe_construct(
                PositioningStrategy, final_state["positioning_strategy"]
            )
            if final_state["positioning_strategy"]
            else None,
            section_rewrites=safe_construct(
                SectionRewrites, final_state["section_rewrites"]
            )
            if final_state["section_rewrites"]
            else None,
            application_pack=safe_construct(
                ApplicationPack, final_state["application_pack"]
            )
            if final_state["application_pack"]
            else None,
            output_dir=output_dir,
        )

    def _save_artifacts(self, output_dir: str, state: dict):
        mapping = {
            "01_canonical_resume.json": "canonical_resume",
            "02_preservation_contract.json": "preservation_contract",
            "03_company_intelligence.json": "company_intelligence",
            "04_role_decode.json": "role_decode",
            "05_user_truth.json": "user_truth",
            "06_positioning_strategy.json": "positioning_strategy",
            "07_section_rewrites.json": "section_rewrites",
        }
        for filename, key in mapping.items():
            if state.get(key):
                with open(os.path.join(output_dir, filename), "w") as f:
                    json.dump(state[key], f, indent=2)

        pack = state.get("application_pack")
        if pack:
            with open(os.path.join(output_dir, "10_final_resume.md"), "w") as f:
                f.write(pack.get("resume_markdown", ""))
            with open(os.path.join(output_dir, "11_cover_note.md"), "w") as f:
                f.write(pack.get("cover_note", ""))
            with open(os.path.join(output_dir, "15_quality_report.md"), "w") as f:
                report = pack.get("quality_report", {}) or {}
                f.write(
                    f"# Quality Report\n\n## Changed\n"
                    + "\n".join(
                        [
                            f"- {x}"
                            for x in report.get("what_changed", [])
                        ]
                    )
                )
            with open(
                os.path.join(output_dir, "16_user_review_summary.md"), "w"
            ) as f:
                f.write(pack.get("user_review_summary", ""))
            with open(
                os.path.join(output_dir, "17_council_run_log.json"), "w"
            ) as f:
                json.dump(state, f, indent=2, default=str)

            # Write failure report if present in pack
            failure = pack.get("failure_report", "")
            if failure:
                with open(
                    os.path.join(output_dir, "failure_report.md"), "w"
                ) as f:
                    f.write(failure)


def _build_failure_report(
    ctx: dict, job_data: dict, errors: list
) -> str:
    """Build a failure report when the council pipeline fails."""
    report = (
        f"# Resume Council Failure Report\n\n"
        f"**Generated:** {ctx['current_datetime']}\n"
        f"**Job:** {job_data.get('title', 'Unknown')} at "
        f"{job_data.get('company', 'Unknown')}\n\n"
        f"## Errors ({len(errors)})\n\n"
    )
    for i, err in enumerate(errors, 1):
        report += f"{i}. {err}\n"
    report += (
        "\n## Next Steps\n\n"
        "1. Fix the underlying issue (API key, model config, input data).\n"
        "2. Re-run the council for this job.\n"
    )
    return report


def main():
    """CLI entrypoint. load_dotenv() is called here, not at module level."""
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run Resume Council v3.0 for one selected job."
    )
    parser.add_argument(
        "--job-id", required=True, help="Job ID from ledger"
    )
    parser.add_argument(
        "--person-id",
        default="default",
        help="Person ID for output organization",
    )
    parser.add_argument(
        "--intent",
        default="PREPARE_APPLICATION",
        choices=["INTERESTED", "APPLY", "PREPARE_APPLICATION"],
    )
    args = parser.parse_args()

    orchestrator = ResumeCouncilOrchestrator()
    result = orchestrator.run(args.job_id, args.intent, args.person_id)

    if result.application_pack:
        print(
            f"\nSUCCESS: Application pack generated in {result.output_dir}"
        )
        print(f"Summary: {result.application_pack.user_review_summary}")
    else:
        print("\nFAILURE: Application pack generation failed.")


if __name__ == "__main__":
    main()
