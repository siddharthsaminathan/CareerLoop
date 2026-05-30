"""Job service — job detail + save/skip."""

from careerloop_api.core.envelope import APIError
from careerloop_api.repositories.jobs_repo import JobsRepo
from careerloop_api.services import serializers


class JobService:
    def __init__(self, db):
        self.db = db
        self.repo = JobsRepo(db)

    def get(self, user_id: str, job_ident: str) -> dict:
        job = self.repo.get_by_any_id(job_ident)
        if not job:
            raise APIError("Job not found.", status_code=404, code="job_not_found")
        rel = self.repo.get_relationship(user_id, job["id"])
        enrichment = self.repo.get_brief_enrichment(user_id, job_ident)
        return serializers.job_detail(job, rel, enrichment)

    def save(self, user_id: str, job_ident: str) -> dict:
        """Save (approve) a job: validate existence, then upsert user_job_relationships."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Validate job exists directly by id (text PK)
                cur.execute(
                    "SELECT id FROM careerloop.jobs WHERE id = %s LIMIT 1",
                    (job_ident,),
                )
                row = cur.fetchone()
                if not row:
                    raise APIError(
                        "Job not found. Run a scan first to discover jobs.",
                        status_code=404, code="job_not_found",
                    )

                job_id = row["id"]

                # Upsert user-job relationship directly under jobs.id
                cur.execute(
                    """
                    INSERT INTO careerloop.user_job_relationships
                        (user_id, job_id, match_status, swiped_action, created_at, updated_at)
                    VALUES (%s, %s, 'saved', 'right', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, job_id) DO UPDATE SET
                        match_status = EXCLUDED.match_status,
                        swiped_action = EXCLUDED.swiped_action,
                        updated_at   = CURRENT_TIMESTAMP
                    """,
                    (user_id, job_id),
                )

        return {"job_id": job_id, "match_status": "saved", "swiped_action": "right"}

    def skip(self, user_id: str, job_ident: str) -> dict:
        """Skip a job card directly using jobs.id."""
        job = self.repo.get_by_any_id(job_ident)
        if not job:
            raise APIError("Job not found.", status_code=404, code="job_not_found")
        job_id = job["id"]
        okw = self.repo.set_match_status(user_id, job_id, "skipped", swiped_action="left")
        if not okw:
            raise APIError("Could not skip job.", status_code=500, code="skip_failed")
        return {"job_id": job_id, "match_status": "skipped", "swiped_action": "left"}
