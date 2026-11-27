from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.analyses import _summary
from app.api.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate, Dashboard
from app.db import get_session
from app.models import Analysis, Application, ApplicationStage, JobPosting, Resume

router = APIRouter(tags=["applications"])


def _out(a: Application) -> ApplicationOut:
    return ApplicationOut(
        id=a.id,
        job_id=a.job_id,
        stage=a.stage,
        applied_at=a.applied_at,
        notes=a.notes,
        updated_at=a.updated_at,
        company=a.job.company,
        job_title=a.job.title,
    )


@router.post("/api/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, session: Session = Depends(get_session)) -> ApplicationOut:
    if session.get(JobPosting, body.job_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "공고를 찾을 수 없습니다")
    app_ = Application(**body.model_dump())
    session.add(app_)
    session.commit()
    session.refresh(app_)
    return _out(app_)


@router.get("/api/applications", response_model=list[ApplicationOut])
def list_applications(session: Session = Depends(get_session)) -> list[ApplicationOut]:
    return [_out(a) for a in session.scalars(select(Application).order_by(Application.updated_at.desc()))]


@router.patch("/api/applications/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int, body: ApplicationUpdate, session: Session = Depends(get_session)
) -> ApplicationOut:
    app_ = session.get(Application, application_id)
    if app_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "지원 기록을 찾을 수 없습니다")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(app_, key, value)
    session.commit()
    session.refresh(app_)
    return _out(app_)


@router.delete("/api/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, session: Session = Depends(get_session)) -> None:
    app_ = session.get(Application, application_id)
    if app_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "지원 기록을 찾을 수 없습니다")
    session.delete(app_)
    session.commit()


@router.get("/api/dashboard", response_model=Dashboard, tags=["dashboard"])
def dashboard(session: Session = Depends(get_session)) -> Dashboard:
    by_stage = dict(session.execute(select(Application.stage, func.count()).group_by(Application.stage)).all())
    recent = session.scalars(select(Analysis).order_by(Analysis.created_at.desc()).limit(5))
    return Dashboard(
        resumes=session.scalar(select(func.count()).select_from(Resume)) or 0,
        jobs=session.scalar(select(func.count()).select_from(JobPosting)) or 0,
        analyses=session.scalar(select(func.count()).select_from(Analysis)) or 0,
        applications_by_stage={s.value: by_stage.get(s, 0) for s in ApplicationStage},
        recent_analyses=[_summary(a) for a in recent],
    )
