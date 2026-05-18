import argparse
import dataclasses
import json
import os
import sys
from datetime import datetime
from typing import Optional, Type, TypeVar
from dotenv import load_dotenv

T = TypeVar("T")

def _safe_init(cls: Type[T], data: dict) -> T:
    """Construct a dataclass from a dict, silently dropping unknown keys."""
    valid = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in valid})

load_dotenv()

CAREER_OPS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, CAREER_OPS_ROOT)

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
    QualityReport
)


class ResumeCouncilOrchestrator:
    def __init__(self, root: str = None):
        self.root = root or CAREER_OPS_ROOT
        self.context_loader = CouncilContextLoader(self.root)

    def run(self, job_id: str, intent: str, person_id: str = "default", 
            master_cv: Optional[str] = None, user_profile: Optional[dict] = None) -> CouncilResult:
        
        # Load from context loader if not provided (default behavior)
        if not master_cv or not user_profile:
            loaded = self.context_loader.load(job_id, intent)
            if not loaded.allowed or not loaded.context:
                # If we're using a fixture job ID not in ledger, we might still want to proceed if JD is provided elsewhere
                # But for now, we'll assume job MUST be in ledger OR JD text is passed in initial_state
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
                    "source_url": "https://example.com"
                }
            else:
                job_data = {
                    "title": "AI Product Engineer", 
                    "company": "Nicobar Design Pvt. Ltd.",
                    "description": "...", 
                    "source_url": "https://example.com"
                }

        # Output directory setup
        output_dir = os.path.join(self.root, "output", "council", person_id, job_id)
        os.makedirs(output_dir, exist_ok=True)

        initial_state = {
            "job_id": job_id,
            "person_id": person_id,
            "job_title": job_data.get("title", ""),
            "company": job_data.get("company", ""),
            "job_url": job_data.get("source_url", ""),
            "jd_text": job_data.get("description", ""),
            "master_cv": master_cv,
            "profile": user_profile,
            "today": datetime.now().strftime("%B %Y"),
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
            json.dump({k: v for k, v in initial_state.items() if k != "master_cv"}, f, indent=2)

        # Invoke the LangGraph
        print(f"--- Running Resume Council v3.0 for {initial_state['job_title']} at {initial_state['company']} ---")
        graph = get_council_graph()
        final_state = graph.invoke(initial_state)

        # Save artifacts
        self._save_artifacts(output_dir, final_state)

        # Map state back to CouncilResult
        return CouncilResult(
            job_id=job_id,
            person_id=person_id,
            canonical_resume=_safe_init(CanonicalResume, final_state["canonical_resume"]) if final_state["canonical_resume"] else None,
            preservation_contract=_safe_init(PreservationContract, final_state["preservation_contract"]) if final_state["preservation_contract"] else None,
            company_intelligence=_safe_init(CompanyIntelligence, final_state["company_intelligence"]) if final_state["company_intelligence"] else None,
            role_decode=_safe_init(RoleDecode, final_state["role_decode"]) if final_state["role_decode"] else None,
            user_truth=_safe_init(UserTruth, final_state["user_truth"]) if final_state["user_truth"] else None,
            positioning_strategy=_safe_init(PositioningStrategy, final_state["positioning_strategy"]) if final_state["positioning_strategy"] else None,
            section_rewrites=_safe_init(SectionRewrites, final_state["section_rewrites"]) if final_state["section_rewrites"] else None,
            application_pack=_safe_init(ApplicationPack, final_state["application_pack"]) if final_state["application_pack"] else None,
            output_dir=output_dir
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
                report = pack.get("quality_report", {})
                f.write(f"# Quality Report\n\n## Changed\n" + "\n".join([f"- {x}" for x in report.get("what_changed", [])]))
            with open(os.path.join(output_dir, "16_user_review_summary.md"), "w") as f:
                f.write(pack.get("user_review_summary", ""))
            with open(os.path.join(output_dir, "17_council_run_log.json"), "w") as f:
                json.dump(state, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(description="Run Resume Council v3.0 for one selected job.")
    parser.add_argument("--job-id", required=True, help="Job ID from ledger")
    parser.add_argument("--person-id", default="default", help="Person ID for output organization")
    parser.add_argument("--intent", default="PREPARE_APPLICATION",
                        choices=["INTERESTED", "APPLY", "PREPARE_APPLICATION"])
    args = parser.parse_args()

    orchestrator = ResumeCouncilOrchestrator()
    result = orchestrator.run(args.job_id, args.intent, args.person_id)
    
    if result.application_pack:
        print(f"\nSUCCESS: Application pack generated in {result.output_dir}")
        print(f"Summary: {result.application_pack.user_review_summary}")
    else:
        print("\nFAILURE: Application pack generation failed.")


if __name__ == "__main__":
    main()
