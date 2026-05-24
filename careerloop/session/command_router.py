"""Unified command routing — single handler for slash commands and natural-language intents."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from careerloop.session.states import UserState

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    text: str
    new_state: str | None = None


class CommandRouter:
    """All user-facing commands route through here.

    Slash commands in chat_cli.py AND supervisor_graph intent handlers
    both call these same methods, ensuring consistent behavior.
    """

    def __init__(self, root: str | None = None):
        self.root = root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )

    # ── /status ────────────────────────────────────────────────

    def status(self, session) -> CommandResult:
        data = getattr(session, "temp_profile_data", {}) or {}
        state = getattr(session, "state", "UNKNOWN")
        lines = [
            f"**State:** {state}",
            f"**Roles:** {data.get('target_roles', 'N/A')}",
            f"**Cities:** {data.get('target_cities', 'N/A')}",
            f"**Salary:** {data.get('salary_expectations', 'N/A')}",
            f"**Notice:** {data.get('notice_period', 'N/A')}",
            f"**Mode:** {data.get('aggressiveness', 'N/A')}",
        ]
        return CommandResult(text="\n".join(lines))

    # ── /brief ─────────────────────────────────────────────────

    def brief(self) -> CommandResult:
        today_str = datetime.now(timezone.utc).date().isoformat()
        brief_path = os.path.join(self.root, "output", "daily_briefs", f"{today_str}.md")
        if os.path.exists(brief_path):
            with open(brief_path) as f:
                return CommandResult(text=f.read())
        return CommandResult(
            text="No brief generated today. Type `/scan` to search for new jobs."
        )

    # ── /scan ──────────────────────────────────────────────────

    def scan(self) -> CommandResult:
        try:
            from careerloop.daily_runner import DailyRunner
            runner = DailyRunner(self.root)
            result = runner.run(do_scan=True)

            if result.get("already_generated"):
                today_str = datetime.now(timezone.utc).date().isoformat()
                brief_path = os.path.join(self.root, "output", "daily_briefs", f"{today_str}.md")
                if os.path.exists(brief_path):
                    with open(brief_path) as f:
                        text = f.read()
                    return CommandResult(
                        text=f"Brief already generated today.\n\n{text}",
                        new_state="BRIEF_AVAILABLE",
                    )
                return CommandResult(
                    text=f"Brief already generated today ({today_str}).",
                    new_state="BRIEF_AVAILABLE",
                )

            shortlist_text = result.get("shortlist_text", "")
            return CommandResult(
                text=f"Scan complete! {result['new_jobs_found']} raw → {result['unique_added']} new → {result['scored']} scored.\n\n{shortlist_text}",
                new_state="BRIEF_AVAILABLE",
            )
        except Exception as e:
            logger.exception("Scan failed")
            return CommandResult(text=f"Scan failed: {e}")

    # ── /pipeline ──────────────────────────────────────────────

    def pipeline(self) -> CommandResult:
        try:
            from careerloop.application_ledger import ApplicationLedger
            ledger = ApplicationLedger(self.root)
            status_counts: dict[str, int] = {}
            for e in ledger.entries:
                s = e.get("status", "UNKNOWN")
                status_counts[s] = status_counts.get(s, 0) + 1
            lines = ["**Job Pipeline**\n"]
            for status, count in sorted(status_counts.items()):
                lines.append(f"  • {status}: {count}")
            top = ledger.get_top_scored(min_score=1, limit=5)
            if top:
                lines.append("\n**Top 5 Matches:**")
                for i, job in enumerate(top, 1):
                    score = ledger._get_score(job) or 0
                    lines.append(
                        f"  {i}. **{job.get('title','?')}** @ {job.get('company','?')} — {score:.0f}/100"
                    )
            return CommandResult(text="\n".join(lines))
        except Exception as e:
            return CommandResult(text=f"Could not load pipeline: {e}")

    # ── /profile ───────────────────────────────────────────────

    def profile(self, session) -> CommandResult:
        data = getattr(session, "temp_profile_data", {}) or {}
        cv = data.get("cv_content", "")
        if cv:
            preview = cv[:500] + ("..." if len(cv) > 500 else "")
        else:
            preview = "No CV on file."
        lines = ["**Full Profile**\n", f"**CV Preview:** {preview}"]
        for key, val in data.items():
            if key == "cv_content":
                continue
            lines.append(f"**{key}:** {val}")
        return CommandResult(text="\n".join(lines))

    # ── /reset ─────────────────────────────────────────────────

    def reset(self, session) -> CommandResult:
        session.state = UserState.IDLE
        session.temp_profile_data = None
        return CommandResult(
            text="Session reset. You'll re-enter onboarding on your next message.",
            new_state="IDLE",
        )

    # ── /help ──────────────────────────────────────────────────

    def help(self) -> CommandResult:
        return CommandResult(
            text="\n".join([
                "**Commands:**",
                "  `/status` — View your session state and profile",
                "  `/brief` — Show today's daily job brief",
                "  `/scan` — Search for new jobs",
                "  `/pipeline` — View all jobs in your pipeline",
                "  `/profile` — View your full profile details",
                "  `/reset` — Reset your session",
                "  `/help` — Show this help",
                "",
                "**Chat naturally:** ask for your daily briefing, pipeline status, or new job matches.",
            ])
        )
