"""Discovery Funnel Observability — tracks every job through the pipeline."""

import logging
import uuid

logger = logging.getLogger("careerloop.scan_funnel")


class ScanFunnel:
    """Tracks discovery funnel metrics per scan run. Used by DailyRunner and ScanService."""

    def __init__(self, run_id: str, user_id: str, db):
        self.run_id = run_id
        self.user_id = user_id
        self.db = db

    def record_stage(self, stage: str, count_in: int, count_out: int):
        """Record a funnel stage transition."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO careerloop.scan_metrics (run_id, user_id, stage, count_in, count_out)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (run_id, stage) DO UPDATE SET count_in = EXCLUDED.count_in, count_out = EXCLUDED.count_out""",
                        (self.run_id, self.user_id, stage, count_in, count_out)
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"scan_funnel: failed to record {stage}: {e}")

    def record_rejection(self, job_title: str, company_name: str, source_url: str, stage: str, reason: str):
        """Record WHY a job was rejected at a specific stage."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO careerloop.scan_rejection_reasons (run_id, user_id, job_title, company_name, source_url, rejection_stage, rejection_reason)
                           VALUES (%s, %s::uuid, %s, %s, %s, %s, %s)""",
                        (self.run_id, str(self.user_id), job_title[:500], company_name[:255], source_url[:2048], stage, reason[:500])
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"scan_funnel: failed to record rejection: {e}")

    def emit_funnel_complete(self, stats: dict):
        """Emit a SCAN_FUNNEL run_event with the complete funnel summary."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO careerloop.run_events (event_id, run_id, message, event_type) VALUES (%s, %s, %s, 'SCAN_FUNNEL')",
                        (str(uuid.uuid4()), self.run_id, str(stats))
                    )
                    # Also update background_runs.stats JSONB
                    import json
                    cur.execute(
                        "UPDATE careerloop.background_runs SET stats = %s WHERE run_id = %s",
                        (json.dumps(stats), self.run_id)
                    )
                conn.commit()
        except Exception as e:
            logger.warning(f"scan_funnel: failed to emit funnel: {e}")
