from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import JobCreate, JobOut, JobSummary
from app.db import get_session
from app.models import JobPosting

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(body: JobCreate, session: Session = Depends(get_session)) -> JobPosting:
    # The link is stored as given. It is never fetched, so whether the posting is still open
    # stays "unchecked" (source_status_checked=False) and the UI says so.
    job = JobPosting(
        company=body.company,
        title=body.title,
        description=body.description,
        source_url=str(body.source_url) if body.source_url else None,
        deadline=body.deadline,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("", response_model=list[JobSummary])
def list_jobs(session: Session = Depends(get_session)) -> list[JobPosting]:
    return list(session.scalars(select(JobPosting).order_by(JobPosting.created_at.desc())))


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobPosting:
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "공고를 찾을 수 없습니다")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, session: Session = Depends(get_session)) -> None:
    job = session.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "공고를 찾을 수 없습니다")
    session.delete(job)
    session.commit()
