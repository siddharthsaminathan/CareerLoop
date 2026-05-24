import json
import logging
import re
from typing import Dict, Any

from careerloop.session.models import Action, ActionType, ResponseEnvelope
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState
from careerloop.memory.connection import DatabaseManager

logger = logging.getLogger("careerloop.session.tool_registry")

class ToolRegistry:
    def __init__(self, db_manager: DatabaseManager, session_store: SessionStore):
        self.db = db_manager
        self.session_store = session_store
        
        self._handlers = {
            ActionType.SHOW_STATUS: self.show_status,
            ActionType.SHOW_PROFILE: self.show_profile,
            ActionType.START_SCAN: self.start_scan,
            ActionType.SHOW_BRIEF: self.show_brief,
            ActionType.SELECT_BRIEF_ITEM: self.select_brief_item,
            ActionType.REVIEW_JOB: self.review_job,
            ActionType.SKIP_JOB: self.skip_job,
            ActionType.SAVE_JOB: self.save_job,
            ActionType.SHOW_COMPANY_INTEL: self.show_company_intel,
            ActionType.SHOW_PEOPLE_TO_REACH: self.show_people_to_reach,
            ActionType.PREPARE_APPLICATION_PACK: self.prepare_application_pack,
            ActionType.EDIT_APPLICATION_PACK: self.edit_application_pack,
            ActionType.MARK_APPLIED: self.mark_applied,
            ActionType.SHOW_PIPELINE: self.show_pipeline,
            ActionType.HELP: self.show_help,
            ActionType.RESET_SESSION: self.reset_session,
            ActionType.GENERAL_CHAT: self.general_chat,
        }

    def execute(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        handler = self._handlers.get(action.action_type)
        if not handler:
            logger.warning(f"No handler found for action {action.action_type}")
            return self.general_chat(action, state, context)
            
        try:
            return handler(action, state, context)
        except Exception as e:
            logger.error(f"Error executing {action.action_type}: {e}", exc_info=True)
            return ResponseEnvelope(
                response_type="error",
                text=f"Encountered an error while executing {action.action_type}: {str(e)}"
            )

    # ---------------------------------------------------------
    # Tool Implementations (Stubs for architectural flow)
    # ---------------------------------------------------------

    def general_chat(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        return ResponseEnvelope(response_type="text", text="")

    def show_help(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        return ResponseEnvelope(
            response_type="list",
            text="",
            cards=[
                {"command": "/brief", "description": "Today's job matches"},
                {"command": "/scan", "description": "Search for new jobs"},
                {"command": "/pipeline", "description": "All tracked jobs"},
                {"command": "/status", "description": "Your profile and state"},
                {"command": "/profile", "description": "Full profile details"},
                {"command": "/reset", "description": "Reset your session"},
            ]
        )
        
    def reset_session(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        return ResponseEnvelope(
            response_type="text",
            text="Session reset. What would you like to do next?",
            state_updates={"state": UserJourneyState.NEW_USER, "active_artifact_type": None, "active_artifact_id": None, "active_job_id": None, "active_brief_id": None, "active_pack_id": None, "current_selection_index": None}
        )

    def show_status(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        bg_runs = []
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT run_id, run_type, status FROM background_runs WHERE user_id = %s ORDER BY started_at DESC LIMIT 5",
                        (action.user_id,)
                    )
                    rows = cur.fetchall()
                    bg_runs = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error loading background runs: {e}")

        return ResponseEnvelope(
            response_type="text",
            text="",
            cards=[
                {"label": "Journey State", "value": state.value},
                {"label": "Active Artifact", "value": context.get("active_artifact_type", "none")},
                {"label": "Background Runs", "value": bg_runs if bg_runs else "none"},
            ]
        )

    def show_profile(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        cv = ""
        prefs = {}
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT master_cv_markdown, work_style_prefs FROM users WHERE id = %s",
                        (action.user_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        cv = row.get("master_cv_markdown", "") or ""
                        prefs_raw = row.get("work_style_prefs", "{}")
                        if isinstance(prefs_raw, str):
                            try:
                                prefs = json.loads(prefs_raw)
                            except Exception:
                                prefs = {}
                        else:
                            prefs = prefs_raw or {}
        except Exception as e:
            logger.error(f"Error loading profile: {e}")

        cv_preview = cv[:500] if cv else "No CV on file."
        return ResponseEnvelope(
            response_type="card",
            text="",
            cards=[
                {"label": "CV Preview", "value": cv_preview},
                {"label": "Target Roles", "value": prefs.get("target_roles", "N/A")},
                {"label": "Target Cities", "value": prefs.get("target_cities", "N/A")},
                {"label": "Salary", "value": prefs.get("salary_expectations", "N/A")},
                {"label": "Notice Period", "value": prefs.get("notice_period", "N/A")},
                {"label": "Mode", "value": prefs.get("aggressiveness", "N/A")},
            ]
        )

    def start_scan(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        import uuid
        import os
        from datetime import datetime, timezone
        from careerloop.daily_runner import DailyRunner

        run_id = uuid.uuid4().hex[:12]
        user_id = action.user_id

        # 1. Enqueue in background_runs
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO background_runs (run_id, user_id, run_type, status, started_at) VALUES (%s, %s, 'scan', 'RUNNING', CURRENT_TIMESTAMP)",
                        (run_id, user_id)
                    )
                    cursor.execute(
                        "INSERT INTO run_events (event_id, run_id, message) VALUES (%s, %s, 'Initializing scan runner...')",
                        (str(uuid.uuid4()), run_id)
                    )
        except Exception as e:
            logger.error(f"Error initializing background run in DB: {e}")

        # 2. Call DailyRunner
        try:
            root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
            runner = DailyRunner(root)
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO run_events (event_id, run_id, message) VALUES (%s, %s, 'Executing discovery scan...')",
                        (str(uuid.uuid4()), run_id)
                    )

            res = runner.run(do_scan=True)
            today_str = datetime.now(timezone.utc).date().isoformat()
            brief_id = str(uuid.uuid4())

            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Clear out today's old briefs to stay clean
                    cursor.execute(
                        "DELETE FROM daily_brief_items WHERE brief_id IN (SELECT id FROM daily_briefs WHERE user_id = %s AND date_str = %s)",
                        (user_id, today_str)
                    )
                    cursor.execute(
                        "DELETE FROM daily_briefs WHERE user_id = %s AND date_str = %s",
                        (user_id, today_str)
                    )
                    cursor.execute(
                        "INSERT INTO daily_briefs (id, user_id, date_str, run_id, summary) VALUES (%s, %s, %s, %s, %s)",
                        (brief_id, user_id, today_str, run_id, res.get("shortlist_text", ""))
                    )

                    top_jobs = res.get("top_jobs", [])
                    for idx, item in enumerate(top_jobs, 1):
                        job = item["job"]
                        score = item["score"]
                        breakdown = item["breakdown"]
                        
                        cursor.execute(
                            "INSERT INTO daily_brief_items (id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                str(uuid.uuid4()),
                                brief_id,
                                idx,
                                job["job_id"],
                                job.get("title", ""),
                                job.get("company", ""),
                                job.get("location", ""),
                                score,
                                breakdown.get("recommendation_reason") or breakdown.get("reason", "Highly compatible role matching your target filters."),
                                breakdown.get("risk_summary") or breakdown.get("risks", "No critical structural or tenure risks found."),
                                breakdown.get("route_recommendation") or breakdown.get("outreach", "Leverage LinkedIn warm outreach playbook to the Engineering Manager.")
                            )
                        )

                    # Emit MATCH events for top 5 jobs
                    for idx, item in enumerate(top_jobs[:5], 1):
                        job = item["job"]
                        score = item["score"]
                        company = job.get("company", "?")
                        title = job.get("title", "?")
                        location = job.get("location", "?")
                        msg = f"MATCH #{idx} — {title} @ {company} — {location} — {score:.0f}/100"
                        try:
                            cursor.execute(
                                "INSERT INTO run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                (str(uuid.uuid4()), run_id, msg, "scan_match")
                            )
                        except Exception:
                            pass

                    # Emit filtering summary to run_events
                    if res and not res.get("already_generated"):
                        new_jobs = res.get("new_jobs_found", 0)
                        unique = res.get("unique_added", 0)
                        scored = res.get("scored", 0)
                        summary_events = [
                            f"Scan filtering summary:",
                            f"  {new_jobs} total found",
                            f"  {scored} matched and scored",
                            f"  {new_jobs - unique} duplicates removed",
                            f"Brief ready with top matches.",
                        ]
                        for event_msg in summary_events:
                            cursor.execute(
                                "INSERT INTO run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                (str(uuid.uuid4()), run_id, event_msg, "scan_progress")
                            )

                    cursor.execute(
                        "UPDATE background_runs SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE run_id = %s",
                        (run_id,)
                    )
                    cursor.execute(
                        "INSERT INTO run_events (event_id, run_id, message) VALUES (%s, %s, 'Scan completed and daily brief persisted.')",
                        (str(uuid.uuid4()), run_id)
                    )

            text = f"Scan complete! Scored {res['scored']} opportunities. Here is your Daily Brief:\n\n{res['shortlist_text']}"
            return ResponseEnvelope(
                response_type="list",
                text=text,
                artifact_context_updates={
                    "active_artifact_type": "daily_brief",
                    "active_artifact_id": brief_id
                },
                state_updates={"state": UserJourneyState.PROFILE_READY}
            )
        except Exception as scan_err:
            logger.error(f"Scan failed: {scan_err}", exc_info=True)
            try:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE background_runs SET status = 'FAILED', updated_at = CURRENT_TIMESTAMP WHERE run_id = %s",
                            (run_id,)
                        )
                        cursor.execute(
                            "INSERT INTO run_events (event_id, run_id, message) VALUES (%s, %s, %s)",
                            (str(uuid.uuid4()), run_id, f"Scan failed: {str(scan_err)}")
                        )
            except Exception:
                pass
            return ResponseEnvelope(
                response_type="error",
                text=f"Scan failed: {str(scan_err)}"
            )

    def show_brief(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        brief = None
        brief_items = []
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, date_str, summary FROM daily_briefs WHERE user_id = %s ORDER BY date_str DESC LIMIT 1",
                        (action.user_id,)
                    )
                    brief = cursor.fetchone()
                    if brief:
                        brief_id = brief["id"]
                        cursor.execute(
                            "SELECT item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation "
                            "FROM daily_brief_items WHERE brief_id = %s ORDER BY item_index ASC",
                            (brief_id,)
                        )
                        brief_items = cursor.fetchall()
        except Exception as e:
            logger.error(f"Error loading brief from database: {e}")

        if not brief or not brief_items:
            return ResponseEnvelope(
                response_type="text",
                text="You do not have a daily brief yet. Would you like me to scan for matching jobs now?"
            )

        lines = [f"# Daily Brief — {brief['date_str']}\n"]
        cards = []
        for item in brief_items:
            idx = item["item_index"]
            title = item["title"]
            company = item["company"]
            location = item["location"] or "India"
            score = item["fit_score"]
            lines.append(f"{idx}. **{title}** @ {company} ({location}) — **{score:.1f}/100**")
            
            cards.append({
                "index": idx,
                "job_id": item["job_id"],
                "title": title,
                "company": company,
                "location": location,
                "fit_score": score,
                "recommendation_reason": item.get("recommendation_reason", ""),
                "risk_summary": item.get("risk_summary", ""),
                "route_recommendation": item.get("route_recommendation", "")
            })
            
        lines.append("\nReply with a number to review details (e.g., '1').")
        text = "\n".join(lines)
        
        return ResponseEnvelope(
            response_type="list",
            text=text,
            cards=cards,
            artifact_context_updates={
                "active_artifact_type": "daily_brief",
                "active_artifact_id": brief["id"]
            },
            state_updates={"state": UserJourneyState.PROFILE_READY}
        )

    def select_brief_item(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        index = action.parsed_args.get("index")
        brief_id = context.get("active_brief_id") or context.get("active_artifact_id")

        if not index:
            return ResponseEnvelope(response_type="error", text="Could not determine which item to select.")
            
        if not brief_id:
            return ResponseEnvelope(response_type="error", text="No active daily brief context found. Try asking for your 'daily brief' first.")
            
        item = None
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation "
                        "FROM daily_brief_items WHERE brief_id = %s AND item_index = %s",
                        (brief_id, index)
                    )
                    item = cursor.fetchone()
        except Exception as e:
            logger.error(f"Error loading brief item from database: {e}")
            
        if not item:
            return ResponseEnvelope(response_type="error", text=f"Item index {index} not found in your active daily brief.")

        text = (
            f"### {item['title']} @ {item['company']}\n"
            f"📍 **Location:** {item['location'] or 'N/A'}\n"
            f"🎯 **Fit Score:** {item['fit_score']:.1f}/100\n\n"
            f"💡 **Why it's a fit:** {item['recommendation_reason'] or 'N/A'}\n\n"
            f"⚠️ **Risks:** {item['risk_summary'] or 'N/A'}\n\n"
            f"🚀 **Action Playbook:** {item['route_recommendation'] or 'N/A'}\n\n"
            f"What would you like to do? (e.g. 'why this job', 'company intel', 'prepare this')"
        )

        return ResponseEnvelope(
            response_type="card",
            text=text,
            artifact_context_updates={
                "active_artifact_type": "job_card",
                "active_job_id": item["job_id"],
                "current_selection_index": index
            },
            state_updates={"state": UserJourneyState.PROFILE_READY}
        )

    def review_job(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        import os as _os
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="No job selected.")

        try:
            from careerloop.application_ledger import ApplicationLedger
            root = _os.path.realpath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
            ledger = ApplicationLedger(root)
            job = next((e for e in ledger.entries if e.get("job_id") == job_id), None)

            if not job:
                return ResponseEnvelope(response_type="error", text="Job not found in ledger.")

            breakdown = job.get("fit_breakdown", {})
            if isinstance(breakdown, str):
                try:
                    breakdown = json.loads(breakdown)
                except Exception:
                    breakdown = {}

            cards = [
                {"label": "Title", "value": job.get("title", "N/A")},
                {"label": "Company", "value": job.get("company", "N/A")},
                {"label": "Location", "value": job.get("location", "N/A")},
                {"label": "Fit Score", "value": f"{job.get('fit_score', 0):.1f}/100"},
            ]
            if isinstance(breakdown, dict):
                for k, v in breakdown.items():
                    if k not in ("rejected",):
                        cards.append({"label": k.replace("_", " ").title(), "value": str(v)})

            return ResponseEnvelope(response_type="card", text="", cards=cards)
        except Exception as e:
            logger.error(f"Error reviewing job {job_id}: {e}")
            return ResponseEnvelope(response_type="error", text=f"Error loading job: {e}")

    def skip_job(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="Please select a job first.")
        
        try:
            from careerloop.application_ledger import ApplicationLedger
            ledger = ApplicationLedger(self.session_store.db_manager._sqlite_path if hasattr(self.session_store.db_manager, "_sqlite_path") else None)
            ledger.transition(job_id, "SKIPPED", "User skipped this job card.")
        except Exception as e:
            logger.error(f"Error skipping job {job_id}: {e}")

        return ResponseEnvelope(
            response_type="text",
            text="Job marked as skipped in ledger.",
            artifact_context_updates={"active_artifact_type": "daily_brief"}
        )

    def save_job(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="Please select a job first.")
        
        try:
            from careerloop.application_ledger import ApplicationLedger
            ledger = ApplicationLedger(self.session_store.db_manager._sqlite_path if hasattr(self.session_store.db_manager, "_sqlite_path") else None)
            ledger.transition(job_id, "SAVED", "User saved this job card to pipeline.")
        except Exception as e:
            logger.error(f"Error saving job {job_id}: {e}")

        return ResponseEnvelope(response_type="text", text="Job saved to pipeline.")

    def show_company_intel(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="No job selected.")

        company_name = ""
        try:
            import os as _os
            from careerloop.application_ledger import ApplicationLedger
            root = _os.path.realpath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
            ledger = ApplicationLedger(root)
            job = next((e for e in ledger.entries if e.get("job_id") == job_id), None)
            if job:
                company_name = job.get("company", "")
        except Exception:
            pass

        if not company_name:
            return ResponseEnvelope(response_type="error", text="Could not find company for this job.")

        # Try company_memory table first
        memory = {}
        try:
            normalized = re.sub(r"[^a-z0-9]+", "", company_name.lower())
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT company_intelligence, startup_risk, company_maturity FROM company_memory WHERE company_normalized = %s",
                        (normalized,)
                    )
                    row = cur.fetchone()
                    if row:
                        memory = dict(row)
        except Exception as e:
            logger.error(f"Error loading company intel for {company_name}: {e}")

        intel_text = memory.get("company_intelligence") if memory else ""
        startup_risk = memory.get("startup_risk", "unknown")
        maturity = memory.get("company_maturity", "unknown")

        # Fallback: check company_registry
        if not intel_text:
            try:
                normalized_dash = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT employee_estimate, sector FROM companies WHERE id = %s OR LOWER(name) = LOWER(%s)",
                            (normalized_dash, company_name)
                        )
                        row = cur.fetchone()
                        if row:
                            sector = row.get("sector", "unknown")
                            employees = row.get("employee_estimate", "unknown")
                            intel_text = f"Sector: {sector}. Estimated employees: {employees}."
            except Exception:
                pass

        if not intel_text:
            intel_text = f"No company intelligence found for {company_name}. Use /scan to discover more companies."

        return ResponseEnvelope(
            response_type="card",
            text="",
            cards=[
                {"label": "Company", "value": company_name},
                {"label": "Intelligence", "value": intel_text},
                {"label": "Startup Risk", "value": startup_risk},
                {"label": "Maturity", "value": maturity},
            ]
        )

    def show_people_to_reach(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="No job selected.")

        company_name = ""
        try:
            import os as _os
            from careerloop.application_ledger import ApplicationLedger
            root = _os.path.realpath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
            ledger = ApplicationLedger(root)
            job = next((e for e in ledger.entries if e.get("job_id") == job_id), None)
            if job:
                company_name = job.get("company", "")
        except Exception:
            pass

        return ResponseEnvelope(
            response_type="card",
            text="",
            cards=[
                {"label": "Company", "value": company_name or "Unknown"},
                {"label": "Suggested Approach", "value": "Target the Engineering Manager or Talent Acquisition lead on LinkedIn."},
                {"label": "Outreach Channel", "value": "LinkedIn InMail or cold email to hiring team."},
            ]
        )

    def prepare_application_pack(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        import uuid
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="No job selected from brief.")

        pack_id = f"pack_{uuid.uuid4().hex[:8]}"
        run_id = uuid.uuid4().hex[:12]

        # Register as background run
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO background_runs (run_id, user_id, run_type, status, started_at) VALUES (%s, %s, 'pack_generation', 'QUEUED', CURRENT_TIMESTAMP)",
                        (run_id, action.user_id)
                    )
                    cur.execute(
                        "INSERT INTO run_events (event_id, run_id, message) VALUES (%s, %s, 'Application pack queued for generation.')",
                        (str(uuid.uuid4()), run_id)
                    )
        except Exception as e:
            logger.error(f"Error queueing pack generation: {e}")

        return ResponseEnvelope(
            response_type="document",
            text="",
            cards=[
                {"label": "Pack ID", "value": pack_id},
                {"label": "Job ID", "value": job_id},
                {"label": "Status", "value": "QUEUED"},
                {"label": "Run ID", "value": run_id},
            ],
            artifact_context_updates={
                "active_artifact_type": "application_pack",
                "active_pack_id": pack_id,
                "active_job_id": job_id,
            }
        )

    def edit_application_pack(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        import uuid
        instruction = action.parsed_args.get("instruction", "")
        pack_id = context.get("active_pack_id")
        if not pack_id:
            return ResponseEnvelope(response_type="error", text="No active application pack to edit.")

        run_id = uuid.uuid4().hex[:12]
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO background_runs (run_id, user_id, run_type, status, started_at) VALUES (%s, %s, 'pack_edit', 'QUEUED', CURRENT_TIMESTAMP)",
                        (run_id, action.user_id)
                    )
                    cur.execute(
                        "INSERT INTO run_events (event_id, run_id, message) VALUES (%s, %s, %s)",
                        (str(uuid.uuid4()), run_id, f"Edit requested: {instruction}")
                    )
        except Exception as e:
            logger.error(f"Error queueing pack edit: {e}")

        return ResponseEnvelope(
            response_type="text",
            text="",
            cards=[
                {"label": "Pack ID", "value": pack_id},
                {"label": "Instruction", "value": instruction},
                {"label": "Status", "value": "QUEUED"},
            ]
        )

    def mark_applied(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        job_id = context.get("active_job_id")
        if not job_id:
            return ResponseEnvelope(response_type="error", text="Please select a job first.")

        try:
            from careerloop.application_ledger import ApplicationLedger
            ledger = ApplicationLedger(self.session_store.db_manager._sqlite_path if hasattr(self.session_store.db_manager, "_sqlite_path") else None)
            ledger.transition(job_id, "APPLIED", "User verified application submission.")
        except Exception as e:
            logger.error(f"Error marking job {job_id} as applied: {e}")

        return ResponseEnvelope(
            response_type="text",
            text="Marked as Applied in the ledger.",
            state_updates={"state": UserJourneyState.APPLICATION_PENDING}
        )

    def show_pipeline(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        active_count = 0
        total_count = 0
        top_matches = []
        try:
            from careerloop.application_ledger import ApplicationLedger
            ledger = ApplicationLedger(self.session_store.db_manager._sqlite_path if hasattr(self.session_store.db_manager, "_sqlite_path") else None)
            total_count = len(ledger.entries)
            active_count = len([e for e in ledger.entries if e.get("status") in ("DISCOVERED", "SHORTLISTED", "APPLIED")])
            top_matches = sorted([e for e in ledger.entries if e.get("fit_score") is not None], key=lambda x: x["fit_score"], reverse=True)[:3]
        except Exception:
            pass

        text = f"### Pipeline Status Summary\n"
        text += f"• **Total Tracked Jobs:** {total_count}\n"
        text += f"• **Active Applications:** {active_count}\n\n"
        if top_matches:
            text += "**Top Rated ledger fits:**\n"
            for i, match in enumerate(top_matches, 1):
                text += f"{i}. **{match['title']}** @ {match['company']} — **{match['fit_score']:.1f}/100**\n"

        return ResponseEnvelope(response_type="list", text=text)
