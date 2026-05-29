import json
import logging
import re
from typing import Dict, Any

from careerloop.session.models import Action, ActionType, ResponseEnvelope
from careerloop.session.session_store import SessionStore
from careerloop.session.states import UserJourneyState
from careerloop.memory.connection import DatabaseManager

# Repository V2 — optional; falls back to raw SQL if unavailable
try:
    from careerloop.memory.repository_v2 import (
        JobRepository, DiscoveryRepository, UserJobRepository,
        BriefRepository, ApplicationRepository, PeopleRepository
    )
    _REPO_V2 = True
except ImportError:
    JobRepository = None
    DiscoveryRepository = None
    UserJobRepository = None
    BriefRepository = None
    ApplicationRepository = None
    PeopleRepository = None
    _REPO_V2 = False

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
                {"command": "Today's matches", "description": "Show your latest job brief"},
                {"command": "Scan for jobs", "description": "Search for new matching jobs"},
                {"command": "My pipeline", "description": "See all tracked applications"},
                {"command": "My status", "description": "Check your profile and journey state"},
                {"command": "My profile", "description": "See full profile details"},
                {"command": "Start fresh", "description": "Reset your session"},
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
                        "SELECT run_id, run_type, status FROM careerloop.background_runs WHERE user_id = %s ORDER BY started_at DESC LIMIT 5",
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
        roles_val = "N/A"
        cities_val = "N/A"
        salary_val = "N/A"
        notice_val = "N/A"
        mode_val = "N/A"
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT master_cv_markdown, work_style_prefs, "
                        "target_roles, target_cities, salary_expectations, "
                        "notice_period, career_mode "
                        "FROM careerloop.users WHERE id = %s",
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

                        # Read from JSONB first, fall back to top-level columns
                        roles_val = prefs.get("target_roles", None) or row.get("target_roles") or "N/A"
                        cities_val = prefs.get("target_cities", None) or prefs.get("locations", None) or row.get("target_cities") or "N/A"
                        salary_val = prefs.get("salary_expectations", None) or row.get("salary_expectations") or "N/A"
                        notice_val = prefs.get("notice_period", None) or row.get("notice_period") or "N/A"
                        mode_val = prefs.get("aggressiveness", None) or row.get("career_mode") or "N/A"
        except Exception as e:
            logger.error(f"Error loading profile: {e}")

        cv_preview = cv[:500] if cv else "No CV on file."
        return ResponseEnvelope(
            response_type="card",
            text="",
            cards=[
                {"label": "CV Preview", "value": cv_preview},
                {"label": "Target Roles", "value": str(roles_val)},
                {"label": "Target Cities", "value": str(cities_val)},
                {"label": "Salary", "value": str(salary_val)},
                {"label": "Notice Period", "value": str(notice_val)},
                {"label": "Mode", "value": str(mode_val)},
            ]
        )

    def start_scan(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        import uuid
        import os
        import threading
        from datetime import datetime, timezone
        from careerloop.daily_runner import DailyRunner

        run_id = uuid.uuid4().hex[:12]
        user_id = action.user_id

        # 1. Enqueue in background_runs
        bg_inserted = False
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO careerloop.background_runs (run_id, user_id, run_type, status, started_at) VALUES (%s, %s, 'scan', 'RUNNING', NOW())",
                        (run_id, user_id)
                    )
                    cursor.execute(
                        "INSERT INTO careerloop.run_events (event_id, run_id, message) VALUES (%s, %s, 'Initializing scan runner...')",
                        (str(uuid.uuid4()), run_id)
                    )
                    # Repository V2: structured scan lifecycle event
                    try:
                        cursor.execute(
                            "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                            (str(uuid.uuid4()), run_id, "Starting job discovery...", "SCAN_STARTED")
                        )
                    except Exception:
                        pass
                bg_inserted = True
        except Exception as e:
            logger.error(f"Error initializing background run in DB: {e}")

        if not bg_inserted:
            return ResponseEnvelope(response_type="error", text="Scan failed: could not create background run.")


        # 2. Start scan in background thread (non-blocking - HTTP response returns immediately)
        root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))

        def _scan_thread(run_id: str, user_id: str, root: str):
            """Run the full scan + brief pipeline in a daemon thread."""
            try:
                runner = DailyRunner(root)

                with self.db.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO careerloop.run_events (event_id, run_id, message) VALUES (%s, %s, 'Executing discovery scan...')",
                            (str(uuid.uuid4()), run_id)
                        )
                        try:
                            cursor.execute(
                                "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                (str(uuid.uuid4()), run_id, "Searching configured portals for new job postings...", "SOURCE_STARTED")
                            )
                        except Exception:
                            pass

                # Cache-hit: check careerloop.jobs before external scan
                try:
                    from careerloop.memory.repository_v2 import get_fresh_cached_jobs
                    _prefs = {}
                    try:
                        with self.db.get_connection() as _pconn:
                            with _pconn.cursor() as _pcur:
                                _pcur.execute("SELECT work_style_prefs FROM public.users WHERE id = %s", (user_id,))
                                _prow = _pcur.fetchone()
                                if _prow and _prow.get("work_style_prefs"):
                                    import json as _json
                                    _prefs = _json.loads(_prow["work_style_prefs"]) if isinstance(_prow["work_style_prefs"], str) else _prow["work_style_prefs"]
                    except Exception:
                        pass
                    _cached = get_fresh_cached_jobs(_prefs, freshness_window_days=14, limit=20)
                    if len(_cached) >= 5:
                        logger.info(f"Cache-hit: {len(_cached)} fresh cached jobs -- skipping external scan")
                        with self.db.get_connection() as _cconn:
                            with _cconn.cursor() as _ccur:
                                _ccur.execute(
                                    "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                    (str(uuid.uuid4()), run_id, f"Cache-hit: {len(_cached)} fresh jobs found in global cache", "CACHE_HIT")
                                )
                except Exception:
                    pass

                res = runner.run(do_scan=True)
                today_str = datetime.now(timezone.utc).date().isoformat()

                # If brief already generated today, log completion and return
                if res.get("already_generated"):
                    try:
                        with self.db.get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "SELECT id FROM careerloop.daily_briefs WHERE user_id = %s AND date_str = %s ORDER BY date_str DESC LIMIT 1",
                                    (user_id, today_str)
                                )
                                existing = cur.fetchone()
                                if existing:
                                    with self.db.get_connection() as conn2:
                                        with conn2.cursor() as cur2:
                                            cur2.execute(
                                                "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE run_id = %s",
                                                (run_id,)
                                            )
                                            cur2.execute(
                                                "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                                (str(uuid.uuid4()), run_id, "Brief already generated today - loaded from DB.", "BRIEF_CREATED")
                                            )
                    except Exception:
                        pass
                    return

                brief_id = str(uuid.uuid4())

                with self.db.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM careerloop.daily_brief_items WHERE brief_id IN (SELECT id FROM careerloop.daily_briefs WHERE user_id = %s AND date_str = %s)",
                            (user_id, today_str)
                        )
                        cursor.execute(
                            "DELETE FROM careerloop.daily_briefs WHERE user_id = %s AND date_str = %s",
                            (user_id, today_str)
                        )
                        cursor.execute(
                            "INSERT INTO careerloop.daily_briefs (id, user_id, date_str, run_id, summary) VALUES (%s, %s, %s, %s, %s)",
                            (brief_id, user_id, today_str, run_id, res.get("shortlist_text", ""))
                        )

                        top_jobs = res.get("top_jobs", [])
                        for idx, item in enumerate(top_jobs, 1):
                            job = item["job"]
                            score = item["score"]
                            breakdown = item["breakdown"]

                            cursor.execute(
                                "INSERT INTO careerloop.daily_brief_items (id, brief_id, item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation) "
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

                        for idx, item in enumerate(top_jobs[:5], 1):
                            job = item["job"]
                            score = item["score"]
                            _company = job.get("company", "?")
                            _title = job.get("title", "?")
                            _location = job.get("location", "?")
                            _msg = f"MATCH #{idx} -- {_title} @ {_company} -- {_location} -- {score:.0f}/100"
                            try:
                                cursor.execute(
                                    "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                    (str(uuid.uuid4()), run_id, _msg, "CANDIDATE_MATCHED")
                                )
                            except Exception:
                                pass

                        new_jobs = res.get("new_jobs_found", 0)
                        unique_added = res.get("unique_added", 0)
                        scored = res.get("scored", 0)
                        summary_lines = [
                            "Scan complete.",
                            f"  {new_jobs} raw jobs found",
                            f"  {unique_added} new (after dedup)",
                            f"  {scored} scored",
                            "Brief ready with top matches.",
                        ]
                        for event_msg in summary_lines:
                            try:
                                cursor.execute(
                                    "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                    (str(uuid.uuid4()), run_id, event_msg, "scan_progress")
                                )
                            except Exception:
                                pass

                        try:
                            filter_msg = f"Scan filter complete -- {new_jobs} raw, {unique_added} new, {scored} scored"
                            cursor.execute(
                                "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                (str(uuid.uuid4()), run_id, filter_msg, "FILTER_SUMMARY")
                            )
                        except Exception:
                            pass

                        try:
                            cursor.execute(
                                "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                                (str(uuid.uuid4()), run_id, "Brief created with top matches.", "BRIEF_CREATED")
                            )
                        except Exception:
                            pass

                        cursor.execute(
                            "UPDATE careerloop.background_runs SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE run_id = %s",
                            (run_id,)
                        )
                        cursor.execute(
                            "INSERT INTO careerloop.run_events (event_id, run_id, message) VALUES (%s, %s, 'Scan completed and daily brief persisted.')",
                            (str(uuid.uuid4()), run_id)
                        )

                # V3 Canonical Pipeline (SEPARATE connection - best-effort, non-blocking)
                import hashlib as _hashlib
                _v3_jobs = 0
                _v3_candidates = 0
                _v3_rels = 0
                _v3_top = top_jobs if top_jobs else []
                if not _v3_top:
                    try:
                        from careerloop.application_ledger import ApplicationLedger
                        _root2 = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
                        _ledger = ApplicationLedger(_root2)
                        _v3_top = _ledger.get_top_scored(min_score=1, limit=10)
                        _v3_top = [{"job": e, "score": _ledger._get_score(e) or 0, "breakdown": e.get("fit_breakdown", {})} for e in _v3_top]
                    except Exception:
                        pass

                try:
                    with self.db.get_connection() as _v3_conn:
                        with _v3_conn.cursor() as _v3_cur:
                            for _v3_idx, item in enumerate(_v3_top, 1):
                                try:
                                    job = item["job"]
                                    score = item["score"]
                                    breakdown = item.get("breakdown", {})
                                    jd_text = job.get("description") or job.get("raw_description", "")
                                    _title_str = job.get("title", "")
                                    _company_str = job.get("company", "")
                                    _location_str = job.get("location", "")
                                    source = job.get("source", "portal_scan")
                                    source_url = job.get("source_url") or job.get("url", "")

                                    if not _company_str and "|" in _title_str:
                                        parts = _title_str.rsplit("|", 1)
                                        if len(parts) == 2:
                                            title_part = parts[0].strip()
                                            source_part = parts[1].strip()
                                            match = re.match(r"(.+?)\s+is\s+hiring\s+(.+?)(?:\s+job)?\s+in\s+(.+?)$", title_part, re.IGNORECASE)
                                            if match:
                                                _company_str = match.group(1).strip()
                                                _title_str = match.group(2).strip()
                                                parsed_location = match.group(3).strip()
                                                if parsed_location:
                                                    _location_str = parsed_location
                                                source = source_part if source_part else "Cutshort"
                                            else:
                                                if " is hiring " in title_part.lower():
                                                    hire_split = title_part.lower().split(" is hiring ", 1)
                                                    _company_str = hire_split[0].strip()
                                                    remaining = hire_split[1].strip() if len(hire_split) > 1 else ""
                                                    loc_match = re.search(r"\s+in\s+(.+?)$", remaining, re.IGNORECASE)
                                                    if loc_match:
                                                        _location_str = loc_match.group(1).strip()
                                                        _title_str = remaining[:loc_match.start()].strip()
                                                    else:
                                                        _title_str = remaining

                                    fp_raw = f"{_title_str.strip().lower()}|{_company_str.strip().lower()}|{_location_str.strip().lower()}"
                                    fingerprint = _hashlib.sha256(fp_raw.encode()).hexdigest()

                                    _v3_cur.execute(
                                        "INSERT INTO careerloop.job_candidates (candidate_id, run_id, source, raw_title, raw_company, raw_location, raw_url, raw_snippet, raw_payload, extraction_status) "
                                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'accepted')",
                                        (str(uuid.uuid4()), run_id, source,
                                         _title_str, _company_str, _location_str, source_url, (jd_text or "")[:500], json.dumps(job)))
                                    _v3_candidates += 1

                                    global_job_id = job.get("job_id") or str(uuid.uuid4())
                                    _v3_cur.execute(
                                        "INSERT INTO careerloop.jobs (id, source, title, company_name, location, content_fingerprint, jd_text, is_india_role, status, scraped_at, apply_url) "
                                        "VALUES (%s, %s, %s, %s, %s, %s, %s, true, 'active', NOW(), %s) "
                                        "ON CONFLICT (content_fingerprint) DO UPDATE SET last_seen_at = NOW(), updated_at = NOW(), apply_url = EXCLUDED.apply_url",
                                        (global_job_id, source, _title_str, _company_str,
                                         _location_str, fingerprint, (jd_text or "")[:5000], source_url))
                                    _v3_jobs += 1

                                    if _company_str:
                                        normalized = re.sub(r"[^a-z0-9]+", "", _company_str.lower())
                                        try:
                                            _v3_cur.execute(
                                                "INSERT INTO careerloop.companies (id, domain_slug, name, normalized_name, first_seen_at, last_updated_at) "
                                                "VALUES (%s, %s, %s, %s, NOW(), NOW()) "
                                                "ON CONFLICT (domain_slug) DO UPDATE SET last_updated_at = NOW(), name = EXCLUDED.name",
                                                (str(uuid.uuid4()), normalized[:50], _company_str, normalized)
                                            )
                                            _v3_cur.execute("SELECT id FROM careerloop.companies WHERE domain_slug = %s", (normalized[:50],))
                                            company_row = _v3_cur.fetchone()
                                            if company_row:
                                                company_id = company_row["id"]
                                                _v3_cur.execute(
                                                    "UPDATE careerloop.jobs SET company_id = %s, company_name = %s, location = %s WHERE id = %s",
                                                    (company_id, _company_str, _location_str, global_job_id)
                                                )
                                            try:
                                                _v3_cur.execute(
                                                    "INSERT INTO careerloop.company_memory (id, user_id, company_normalized, company_intelligence, startup_risk, created_at, updated_at) "
                                                    "VALUES (%s, %s, %s, '', 5.0, NOW(), NOW()) "
                                                    "ON CONFLICT DO NOTHING",
                                                    (str(uuid.uuid4()), user_id, normalized)
                                                )
                                            except Exception:
                                                pass
                                        except Exception:
                                            pass

                                    rejection = breakdown.get("rejected") or breakdown.get("rejection_reason")
                                    match_status = "rejected" if rejection else "matched"
                                    _v3_cur.execute(
                                        "INSERT INTO careerloop.user_job_relationships (user_id, job_id, fit_score, match_status, rejection_reason, shown_in_brief_id, route_recommendation, personalization_payload) "
                                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                                        "ON CONFLICT (user_id, job_id) DO UPDATE SET fit_score = EXCLUDED.fit_score, match_status = EXCLUDED.match_status, shown_in_brief_id = EXCLUDED.shown_in_brief_id, updated_at = NOW()",
                                        (user_id, global_job_id, score, match_status, rejection, brief_id,
                                         breakdown.get("route_recommendation") or "direct_apply", json.dumps(breakdown)))
                                    _v3_rels += 1
                                except Exception:
                                    pass
                    logger.info(f"V3 pipeline: {_v3_candidates} candidates, {_v3_jobs} jobs, {_v3_rels} relationships written")
                except Exception:
                    pass

            except Exception as scan_err:
                logger.error(f"Scan failed: {scan_err}", exc_info=True)
                try:
                    with self.db.get_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "UPDATE careerloop.background_runs SET status = 'FAILED', updated_at = CURRENT_TIMESTAMP WHERE run_id = %s",
                                (run_id,)
                            )
                            cursor.execute(
                                "INSERT INTO careerloop.run_events (event_id, run_id, message) VALUES (%s, %s, %s)",
                                (str(uuid.uuid4()), run_id, f"Scan failed: {str(scan_err)}")
                            )
                except Exception:
                    pass

        thread = threading.Thread(target=_scan_thread, args=(run_id, user_id, root), daemon=True)
        thread.start()

        return ResponseEnvelope(
            text="\U0001f50d Scan started! Your daily brief will be ready in a minute. Say 'show brief' or type a number to review matches once the scan completes.",
            response_type="text",
        )

    def show_brief(self, action: Action, state: UserJourneyState, context: Dict[str, Any]) -> ResponseEnvelope:
        brief = None
        brief_items = []
        repo_used = False

        # Repository V2: try BriefRepository first
        if _REPO_V2 and BriefRepository:
            try:
                brief_data = BriefRepository.get_latest_brief(action.user_id)
                if brief_data:
                    # Normalize to dict if model object
                    if hasattr(brief_data, '__dict__') and not isinstance(brief_data, dict):
                        brief = {"id": getattr(brief_data, "id", ""), "date_str": getattr(brief_data, "date_str", ""), "summary": getattr(brief_data, "summary", "")}
                    else:
                        brief = brief_data
                    brief_id_v2 = brief["id"] if isinstance(brief, dict) else brief.id
                    raw_items = BriefRepository.get_brief_items(brief_id_v2)
                    if raw_items:
                        if hasattr(raw_items[0], '__dict__') and not isinstance(raw_items[0], dict):
                            brief_items = [
                                {
                                    "item_index": getattr(i, "item_index", 0),
                                    "job_id": getattr(i, "job_id", ""),
                                    "title": getattr(i, "title", ""),
                                    "company": getattr(i, "company", ""),
                                    "location": getattr(i, "location", ""),
                                    "fit_score": getattr(i, "fit_score", 0),
                                    "recommendation_reason": getattr(i, "recommendation_reason", ""),
                                    "risk_summary": getattr(i, "risk_summary", ""),
                                    "route_recommendation": getattr(i, "route_recommendation", ""),
                                }
                                for i in raw_items
                            ]
                        else:
                            brief_items = raw_items
                    repo_used = True
            except Exception as e:
                logger.debug(f"BriefRepository unavailable, falling back to raw SQL: {e}")

        # Fall back to raw SQL
        if not repo_used:
            try:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT id, date_str, summary FROM careerloop.daily_briefs WHERE user_id = %s ORDER BY date_str DESC LIMIT 1",
                            (action.user_id,)
                        )
                        brief = cursor.fetchone()
                        if brief:
                            brief_id = brief["id"]
                            cursor.execute(
                                "SELECT item_index, job_id, title, company, location, fit_score, recommendation_reason, risk_summary, route_recommendation "
                                "FROM careerloop.daily_brief_items WHERE brief_id = %s ORDER BY item_index ASC",
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
            lines.append(f"{idx}. **{title}** @ {company} ({location}) — **{(score or 0):.1f}/100**")
            
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
                "active_artifact_id": brief["id"],
                "active_brief_id": brief["id"],
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
                        "FROM careerloop.daily_brief_items WHERE brief_id = %s AND item_index = %s",
                        (brief_id, index)
                    )
                    item = cursor.fetchone()
        except Exception as e:
            logger.error(f"Error loading brief item from database: {e}")
            
        if not item:
            return ResponseEnvelope(response_type="error", text=f"Item index {index} not found in your active daily brief.")

        text = (
            f"### {item['title']} @ {item['company']}\n"
            f"🆔 **Job ID:** {item['job_id']}\n"
            f"📍 **Location:** {item['location'] or 'N/A'}\n"
            f"🎯 **Fit Score:** {(item.get('fit_score') or 0):.1f}/100\n\n"
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
                "active_brief_id": brief_id,
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

            # Repository V2: supplement with richer job detail from global cache
            repo_job = None
            if _REPO_V2 and JobRepository:
                try:
                    fingerprint = job.get("job_fingerprint") or job.get("job_id")
                    if fingerprint:
                        repo_job = JobRepository.find_by_fingerprint(fingerprint)
                        if repo_job and hasattr(repo_job, '__dict__') and not isinstance(repo_job, dict):
                            repo_job = {k: v for k, v in repo_job.__dict__.items() if not k.startswith('_')}
                except Exception as e:
                    logger.debug(f"JobRepository unavailable: {e}")

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
                {"label": "Fit Score", "value": f"{(job.get('fit_score') or 0):.1f}/100"},
            ]

            # Enrich with repository data if available
            if repo_job:
                if repo_job.get("role_summary"):
                    cards.append({"label": "Role Summary", "value": str(repo_job["role_summary"])[:500]})
                if repo_job.get("source_url"):
                    cards.append({"label": "Source URL", "value": str(repo_job["source_url"])})
                if repo_job.get("apply_url"):
                    cards.append({"label": "Apply URL", "value": str(repo_job["apply_url"])})

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
            return ResponseEnvelope(response_type="error", text="I don't have a job selected. Would you like me to show your latest brief?")

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
            intel_text = f"No company intelligence found for {company_name}. Want me to scan for more companies?"

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
            return ResponseEnvelope(response_type="error", text="I don't have a job selected. Would you like me to show your latest brief?")

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
                        "INSERT INTO careerloop.background_runs (run_id, user_id, run_type, status, started_at) VALUES (%s, %s, 'pack_generation', 'QUEUED', CURRENT_TIMESTAMP)",
                        (run_id, action.user_id)
                    )
                    cur.execute(
                        "INSERT INTO careerloop.run_events (event_id, run_id, message) VALUES (%s, %s, 'Application pack queued for generation.')",
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
                        "INSERT INTO careerloop.background_runs (run_id, user_id, run_type, status, started_at) VALUES (%s, %s, 'pack_edit', 'QUEUED', CURRENT_TIMESTAMP)",
                        (run_id, action.user_id)
                    )
                    cur.execute(
                        "INSERT INTO careerloop.run_events (event_id, run_id, message) VALUES (%s, %s, %s)",
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

        # Repository V2: supplement with user_job_relationships data
        repo_matches = []
        if _REPO_V2 and UserJobRepository:
            try:
                relationships = UserJobRepository.get_matches_for_user(action.user_id)
                if relationships:
                    for rel in relationships:
                        if hasattr(rel, '__dict__') and not isinstance(rel, dict):
                            repo_matches.append({
                                "title": getattr(rel, "title", "?"),
                                "company": getattr(rel, "company_name", getattr(rel, "company", "?")),
                                "fit_score": getattr(rel, "fit_score", 0),
                            })
                        else:
                            repo_matches.append({
                                "title": rel.get("title", "?"),
                                "company": rel.get("company_name", rel.get("company", "?")),
                                "fit_score": rel.get("fit_score", 0),
                            })
                    # Merge repo data if ledger was empty
                    if not top_matches and repo_matches:
                        top_matches = sorted(repo_matches, key=lambda x: x.get("fit_score", 0), reverse=True)[:3]
            except Exception as e:
                logger.debug(f"UserJobRepository unavailable: {e}")

        text = f"### Pipeline Status Summary\n"
        text += f"• **Total Tracked Jobs:** {total_count}\n"
        text += f"• **Active Applications:** {active_count}\n\n"
        if top_matches:
            text += "**Top Rated fits:**\n"
            for i, match in enumerate(top_matches, 1):
                text += f"{i}. **{match['title']}** @ {match['company']} — **{(match.get('fit_score') or 0):.1f}/100**\n"

        return ResponseEnvelope(response_type="list", text=text)
