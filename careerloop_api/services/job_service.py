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
        rel = None
        job_uuid = job.get("job_id")
        if job_uuid:
            rel = self.repo.get_relationship(user_id, str(job_uuid))
        return serializers.job_detail(job, rel)

    def _resolve_uuid(self, job_ident: str) -> tuple:
        job = self.repo.get_by_any_id(job_ident)
        if not job:
            raise APIError("Job not found.", status_code=404, code="job_not_found")
        job_uuid = job.get("job_id")
        if not job_uuid:
            raise APIError(
                "Job has no canonical UUID yet; cannot persist a relationship.",
                status_code=409, code="job_not_canonical",
            )
        return str(job_uuid), job

    def save(self, user_id: str, job_ident: str) -> dict:
        job_uuid, job = self._resolve_uuid(job_ident)
        okw = self.repo.set_match_status(user_id, job_uuid, "saved", swiped_action="right")
        if not okw:
            raise APIError("Could not save job.", status_code=500, code="save_failed")
        return {"job_id": job_uuid, "match_status": "saved", "swiped_action": "right"}

    def skip(self, user_id: str, job_ident: str) -> dict:
        job_uuid, job = self._resolve_uuid(job_ident)
        okw = self.repo.set_match_status(user_id, job_uuid, "skipped", swiped_action="left")
        if not okw:
            raise APIError("Could not skip job.", status_code=500, code="skip_failed")
        return {"job_id": job_uuid, "match_status": "skipped", "swiped_action": "left"}
