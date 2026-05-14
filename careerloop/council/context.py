"""
Context loading for one-job Resume Council runs.
"""

from pathlib import Path
from typing import Optional

from careerloop.application_ledger import ApplicationLedger
from careerloop.council.models import CouncilContext, CouncilIntent, CouncilResult
from careerloop.profile_manager import ProfileManager


ALLOWED_INTENTS = {
    CouncilIntent.INTERESTED.value,
    CouncilIntent.APPLY.value,
    CouncilIntent.PREPARE_APPLICATION.value,
}


class CouncilContextLoader:
    def __init__(self, root: str):
        self.root = root
        self.profile = ProfileManager(root)
        self.ledger = ApplicationLedger(root)

    def load(self, job_id: str, intent: str) -> CouncilResult:
        normalized_intent = (intent or "").strip().upper()
        if normalized_intent not in ALLOWED_INTENTS:
            return CouncilResult(
                allowed=False,
                reason="Resume Council requires explicit INTERESTED, APPLY, or PREPARE_APPLICATION intent.",
            )

        job = self.ledger.get_job(job_id)
        if not job:
            return CouncilResult(allowed=False, reason=f"No ledger job found for {job_id}.")

        context = CouncilContext(
            job_id=job_id,
            intent=CouncilIntent(normalized_intent),
            user_profile=self.profile.get_full_profile(),
            job=job,
            master_profile=self._load_master_profile(),
            previous_feedback=[],
        )
        return CouncilResult(allowed=True, reason="Council context loaded.", context=context)

    def _load_master_profile(self) -> str:
        candidates = [
            Path(self.root) / "cv.md",
            Path(self.root) / "modes" / "_profile.md",
            Path(self.root) / "modes" / "_profile.template.md",
        ]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8")
        return ""
