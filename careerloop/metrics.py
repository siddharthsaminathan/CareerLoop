"""
North-star metrics — read-only aggregates over the persistence layer.

North star = applications submitted per week.

Sources:
- event_timeline table (event_type='application_submitted' etc.)
- application_ledger table (status transitions)
- companies / jobs tables (discovery throughput)

No background processes — pure SQL queries on demand. Cheap.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone

from careerloop.memory.connection import get_db_manager

logger = logging.getLogger(__name__)


def _iso_n_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@dataclass
class WeeklyMetrics:
    week_ending: str
    applications_submitted: int = 0
    jobs_discovered: int = 0
    jobs_shortlisted: int = 0
    interviews_scheduled: int = 0
    offers_received: int = 0
    rejections: int = 0
    council_runs: int = 0
    companies_added: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class MetricsEngine:
    def __init__(self, career_ops_root: str = None):
        self.db = get_db_manager(career_ops_root)

    # ── North star ───────────────────────────────────────────────────

    def applications_this_week(self, user_id: str = None) -> int:
        return self._count_ledger_status_since(
            statuses=["APPLIED"], days=7, user_id=user_id, field="updated_at"
        )

    def applications_per_week(self, weeks: int = 8, user_id: str = None) -> list[WeeklyMetrics]:
        """Return last N weeks of metrics, most-recent first."""
        out = []
        for w in range(weeks):
            start = _iso_n_days_ago((w + 1) * 7)
            end = _iso_n_days_ago(w * 7)
            wm = self._metrics_in_range(start, end, user_id)
            wm.week_ending = end[:10]
            out.append(wm)
        return out

    # ── Funnel ────────────────────────────────────────────────────────

    def funnel(self, days: int = 30, user_id: str = None) -> dict:
        """End-to-end pipeline counts: discovered → applied → interview → offer."""
        since = _iso_n_days_ago(days)
        params = [since]
        user_clause = ""
        if user_id:
            user_clause = " AND user_id = ?"
            params.append(user_id)

        with self.db.get_connection() as conn:
            def count_at(status: str) -> int:
                row = conn.execute(
                    f"SELECT COUNT(*) AS c FROM application_ledger "
                    f"WHERE status = ? AND updated_at >= ?{user_clause}",
                    [status, since] + ([user_id] if user_id else []),
                ).fetchone()
                return row["c"] if row else 0

            return {
                "window_days": days,
                "discovered": count_at("DISCOVERED"),
                "shortlisted": count_at("SHORTLISTED"),
                "applied": count_at("APPLIED"),
                "interview": count_at("INTERVIEW"),
                "offer": count_at("OFFER"),
                "rejected": count_at("REJECTED"),
            }

    # ── Discovery throughput ─────────────────────────────────────────

    def discovery_throughput(self, days: int = 7) -> dict:
        since = _iso_n_days_ago(days)
        with self.db.get_connection() as conn:
            jobs_row = conn.execute(
                "SELECT COUNT(*) AS c FROM careerloop.jobs WHERE scraped_at >= ?", [since]
            ).fetchone()
            companies_row = conn.execute(
                "SELECT COUNT(*) AS c FROM careerloop.companies WHERE created_at >= ?", [since]
            ).fetchone()
            canon_row = conn.execute(
                "SELECT COUNT(*) AS c FROM careerloop.jobs WHERE scraped_at >= ? AND canonical_id IS NULL",
                [since],
            ).fetchone()
        return {
            "window_days": days,
            "jobs_scraped": jobs_row["c"] if jobs_row else 0,
            "canonical_jobs": canon_row["c"] if canon_row else 0,
            "companies_added": companies_row["c"] if companies_row else 0,
        }

    # ── Internals ─────────────────────────────────────────────────────

    def _metrics_in_range(self, start: str, end: str, user_id: str = None) -> WeeklyMetrics:
        wm = WeeklyMetrics(week_ending=end[:10])
        params_base = [start, end]
        user_clause = ""
        if user_id:
            user_clause = " AND user_id = ?"
            params_base.append(user_id)

        with self.db.get_connection() as conn:
            def count_status(status: str) -> int:
                params = [status, start, end] + ([user_id] if user_id else [])
                row = conn.execute(
                    f"SELECT COUNT(*) AS c FROM application_ledger "
                    f"WHERE status = ? AND updated_at >= ? AND updated_at < ?{user_clause}",
                    params,
                ).fetchone()
                return row["c"] if row else 0

            wm.applications_submitted = count_status("APPLIED")
            wm.jobs_shortlisted = count_status("SHORTLISTED")
            wm.interviews_scheduled = count_status("INTERVIEW")
            wm.offers_received = count_status("OFFER")
            wm.rejections = count_status("REJECTED")

            row = conn.execute(
                "SELECT COUNT(*) AS c FROM careerloop.companies WHERE created_at >= ? AND created_at < ?",
                [start, end],
            ).fetchone()
            wm.companies_added = row["c"] if row else 0

            row = conn.execute(
                "SELECT COUNT(*) AS c FROM careerloop.jobs WHERE scraped_at >= ? AND scraped_at < ?",
                [start, end],
            ).fetchone()
            wm.jobs_discovered = row["c"] if row else 0

            row = conn.execute(
                "SELECT COUNT(*) AS c FROM event_timeline "
                "WHERE event_type = 'council_run' AND created_at >= ? AND created_at < ?",
                [start, end],
            ).fetchone()
            wm.council_runs = row["c"] if row else 0

        return wm

    def _count_ledger_status_since(self, statuses, days, user_id, field="updated_at"):
        since = _iso_n_days_ago(days)
        placeholders = ", ".join(["?"] * len(statuses))
        sql = (
            f"SELECT COUNT(*) AS c FROM application_ledger "
            f"WHERE status IN ({placeholders}) AND {field} >= ?"
        )
        params = list(statuses) + [since]
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        with self.db.get_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["c"] if row else 0


# ── CLI entry ────────────────────────────────────────────────────────────

def main():
    import json, sys
    root = sys.argv[1] if len(sys.argv) > 1 else None
    me = MetricsEngine(root)
    out = {
        "applications_this_week": me.applications_this_week(),
        "funnel_30d": me.funnel(30),
        "throughput_7d": me.discovery_throughput(7),
        "weekly_history": [w.to_dict() for w in me.applications_per_week(8)],
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
