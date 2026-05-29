"""Job router — /jobs/{job_id}, save, skip."""

from fastapi import APIRouter, Depends

from careerloop_api.core.envelope import ok
from careerloop_api.deps.auth import get_current_user
from careerloop_api.deps.db import get_db
from careerloop_api.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str, user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return ok(JobService(db).get(user_id, job_id))


@router.post("/{job_id}/save")
def save_job(job_id: str, user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return ok(JobService(db).save(user_id, job_id))


@router.post("/{job_id}/skip")
def skip_job(job_id: str, user_id: str = Depends(get_current_user), db=Depends(get_db)):
    return ok(JobService(db).skip(user_id, job_id))
