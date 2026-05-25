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
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT master_cv_markdown, work_style_prefs FROM careerloop.users WHERE id = %s",
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

        # 2. Launch async background scan
        import threading
        _db_url = os.getenv("DATABASE_URL", "")

        def _run_scan_background(_rid, _uid, _db_url):
            import uuid as _uuid, hashlib as _hashlib, json as _json
            from careerloop.daily_runner import DailyRunner
            try:
                import psycopg2
                _conn = psycopg2.connect(_db_url)
                _cur = _conn.cursor()
                _cur.execute(
                    "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s,%s,%s,%s)",
                    (str(_uuid.uuid4()), _rid, "Searching job boards...", "SOURCE_STARTED"))
                _conn.commit()

                root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
                runner = DailyRunner(root)
                res = runner.run(do_scan=True)
                today_str = datetime.now(timezone.utc).date().isoformat()

                if res.get("already_generated"):
                    _cur.execute("UPDATE careerloop.background_runs SET status='COMPLETED',updated_at=NOW() WHERE run_id=%s",(_rid,))
                    _cur.execute("INSERT INTO careerloop.run_events (event_id,run_id,message,event_type) VALUES (%s,%s,%s,%s)",
                        (str(_uuid.uuid4()),_rid,"Brief already exists for today.","RUN_COMPLETED"))
                    _conn.commit(); _cur.close(); _conn.close(); return

                brief_id = str(_uuid.uuid4())
                shortlist = res.get("shortlist_text", "")
                top_jobs = res.get("top_jobs", [])
                new_jobs = res.get("new_jobs_found", 0)
                scored_ct = res.get("scored", 0)

                _cur.execute("DELETE FROM careerloop.daily_brief_items WHERE brief_id IN (SELECT id FROM careerloop.daily_briefs WHERE user_id=%s AND date_str=%s)",(_uid,today_str))
                _cur.execute("DELETE FROM careerloop.daily_briefs WHERE user_id=%s AND date_str=%s",(_uid,today_str))
                _cur.execute("INSERT INTO careerloop.daily_briefs (id,user_id,date_str,run_id,summary) VALUES (%s,%s,%s,%s,%s)",
                    (brief_id,_uid,today_str,_rid,shortlist))
                for idx, item in enumerate(top_jobs, 1):
                    j = item["job"]; s = item["score"]; bd = item.get("breakdown",{})
                    _cur.execute(
                        "INSERT INTO careerloop.daily_brief_items (id,brief_id,item_index,job_id,title,company,location,fit_score,recommendation_reason,risk_summary,route_recommendation) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (str(_uuid.uuid4()),brief_id,idx,j.get("job_id",""),j.get("title",""),j.get("company",""),j.get("location",""),s,
                         bd.get("recommendation_reason") or bd.get("reason","Highly compatible."),
                         bd.get("risk_summary") or bd.get("risks","No critical risks."),
                         bd.get("route_recommendation") or bd.get("outreach","LinkedIn outreach.")))

                for idx, item in enumerate(top_jobs[:5], 1):
                    j = item["job"]; s = item["score"]
                    msg = f"MATCH #{idx} — {j.get('title','?')} @ {j.get('company','?')} — {j.get('location','?')} — {s:.0f}/100"
                    _cur.execute("INSERT INTO careerloop.run_events (event_id,run_id,message,event_type) VALUES (%s,%s,%s,%s)",
                        (str(_uuid.uuid4()),_rid,msg,"CANDIDATE_MATCHED"))

                # V3 pipeline from ledger
                _v3_list = top_jobs if top_jobs else []
                if not _v3_list:
                    try:
                        from careerloop.application_ledger import ApplicationLedger
                        _l = ApplicationLedger(root)
                        _v3_list = [{"job":e,"score":_l._get_score(e) or 0,"breakdown":e.get("fit_breakdown",{})} for e in _l.get_top_scored(min_score=1,limit=10)]
                    except Exception: pass

                for item in _v3_list:
                    try:
                        j = item["job"]; s = item["score"]; bd = item.get("breakdown",{})
                        t = j.get("title",""); c = j.get("company",""); loc = j.get("location","")
                        jd = j.get("description") or j.get("raw_description","")
                        src = j.get("source","portal_scan"); surl = j.get("source_url") or j.get("url","")

                        if not c and "|" in t:
                            parts = t.rsplit("|",1); tp = parts[0].strip()
                            m = re.match(r"(.+?)\s+is\s+hiring\s+(.+?)(?:\s+job)?\s+in\s+(.+?)$",tp,re.IGNORECASE)
                            if m: c=m.group(1).strip(); t=m.group(2).strip(); loc=m.group(3).strip()
                            elif " is hiring " in tp.lower():
                                hp=tp.lower().split(" is hiring ",1); c=hp[0].strip()
                                rest=hp[1].strip() if len(hp)>1 else ""
                                rm=re.search(r"\s+in\s+(.+?)$",rest,re.IGNORECASE)
                                if rm: loc=rm.group(1).strip(); t=rest[:rm.start()].strip()
                                else: t=rest

                        fp = _hashlib.sha256(f"{t.strip().lower()}|{c.strip().lower()}|{loc.strip().lower()}".encode()).hexdigest()
                        jid = j.get("job_id") or str(_uuid.uuid4())

                        _cur.execute("INSERT INTO careerloop.job_candidates (candidate_id,run_id,source,raw_title,raw_company,raw_location,raw_url,raw_snippet,raw_payload,extraction_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'accepted')",
                            (str(_uuid.uuid4()),_rid,src,t,c,loc,surl,jd[:500],_json.dumps(j)))
                        _cur.execute("INSERT INTO careerloop.jobs (id,source,title,company_name,location,content_fingerprint,jd_text,is_india_role,status,scraped_at,apply_url) VALUES (%s,%s,%s,%s,%s,%s,%s,true,'active',NOW(),%s) ON CONFLICT (content_fingerprint) DO UPDATE SET last_seen_at=NOW(),updated_at=NOW()",
                            (jid,src,t,c,loc,fp,jd[:5000],surl))
                        rej = bd.get("rejected") or bd.get("rejection_reason")
                        _cur.execute("INSERT INTO careerloop.user_job_relationships (user_id,job_id,fit_score,match_status,rejection_reason,shown_in_brief_id,route_recommendation,personalization_payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id,job_id) DO UPDATE SET fit_score=EXCLUDED.fit_score,match_status=EXCLUDED.match_status,updated_at=NOW()",
                            (_uid,jid,s,"rejected" if rej else "matched",rej,brief_id,bd.get("route_recommendation") or "direct_apply",_json.dumps(bd)))
                        if c:
                            n = re.sub(r"[^a-z0-9]+","",c.lower())[:50]
                            _cur.execute("INSERT INTO careerloop.companies (id,domain_slug,name,normalized_name,first_seen_at,last_updated_at) VALUES (%s,%s,%s,%s,NOW(),NOW()) ON CONFLICT (domain_slug) DO UPDATE SET last_updated_at=NOW(),name=EXCLUDED.name",
                                (str(_uuid.uuid4()),n,c,n))
                    except Exception: pass

                for msg in [f"Scan complete.",f"  {new_jobs} raw jobs found",f"  {scored_ct} scored",f"Brief ready."]:
                    _cur.execute("INSERT INTO careerloop.run_events (event_id,run_id,message,event_type) VALUES (%s,%s,%s,%s)",(str(_uuid.uuid4()),_rid,msg,"scan_progress"))

                _cur.execute("UPDATE careerloop.background_runs SET status='COMPLETED',completed_at=NOW(),updated_at=NOW(),stats=%s WHERE run_id=%s",
                    (_json.dumps({"scored":scored_ct}),_rid))
                _cur.execute("INSERT INTO careerloop.run_events (event_id,run_id,message,event_type) VALUES (%s,%s,%s,%s)",
                    (str(_uuid.uuid4()),_rid,f"Scan complete — {scored_ct} jobs scored.","RUN_COMPLETED"))
                _conn.commit(); _cur.close(); _conn.close()
            except Exception as _e:
                logger.error(f"Background scan failed: {_e}")
                try:
                    _conn=psycopg2.connect(_db_url); _cur=_conn.cursor()
                    _cur.execute("UPDATE careerloop.background_runs SET status='FAILED',error_summary=%s,updated_at=NOW() WHERE run_id=%s",(str(_e)[:500],_rid))
                    _conn.commit(); _cur.close(); _conn.close()
                except Exception: pass

        _thread = threading.Thread(target=_run_scan_background, args=(run_id, user_id, _db_url), daemon=True)
        _thread.start()

        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, %s)",
                    (str(uuid.uuid4()), run_id, "Scan started — searching job boards now.", "SCAN_STARTED"))

        return ResponseEnvelope(
            response_type="text",
            text=f"Scan started! Searching job boards now. I'll message you when results are ready. (run: {run_id[:8]}...)",
            artifact_context_updates={"active_artifact_type": "scan_running"},
            state_updates={"state": UserJourneyState.PROFILE_READY}
        )