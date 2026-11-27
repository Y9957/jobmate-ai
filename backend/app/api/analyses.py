from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import llm_client
from app.api.schemas import AnalysisCreate, AnalysisOut, AnalysisSummary, EvidenceOut, EvidenceUpdate
from app.config import get_settings
from app.db import SessionLocal, get_session
from app.llm.base import LLMClient, LLMError
from app.models import Analysis, JobPosting, MatchEvidence, Resume
from app.services.analysis import QuoteNotInResume, coverage_of, execute, reverify, warnings_of

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def _out(a: Analysis) -> AnalysisOut:
    evidence = sorted(a.evidence, key=lambda e: e.position)
    return AnalysisOut.model_validate(
        {
            **{k: getattr(a, k) for k in AnalysisOut.model_fields if k not in ("warnings", "evidence")},
            "warnings": warnings_of(evidence),
            "evidence": [EvidenceOut.model_validate(e) for e in evidence],
        }
    )


def _summary(a: Analysis) -> AnalysisSummary:
    return AnalysisSummary(
        id=a.id,
        status=a.status,
        resume_id=a.resume_id,
        resume_label=a.resume.label,
        job_id=a.job_id,
        job_title=a.job.title,
        company=a.job.company,
        coverage=a.coverage,
        created_at=a.created_at,
    )


def _load(session: Session, analysis_id: int) -> Analysis:
    a = session.get(Analysis, analysis_id, options=[selectinload(Analysis.evidence)])
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "분석을 찾을 수 없습니다")
    return a


def _run_in_background(analysis_id: int, llm: LLMClient) -> None:
    with SessionLocal() as session:
        execute(session, analysis_id, llm, get_settings().max_match_attempts)


@router.post("", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    body: AnalysisCreate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    llm: LLMClient = Depends(llm_client),
) -> AnalysisOut:
    """Create an analysis and run it after the response is sent. Poll GET /api/analyses/{id} for the result."""
    if session.get(Resume, body.resume_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "이력서를 찾을 수 없습니다")
    if session.get(JobPosting, body.job_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "공고를 찾을 수 없습니다")
    analysis = Analysis(resume_id=body.resume_id, job_id=body.job_id)
    session.add(analysis)
    session.commit()
    background.add_task(_run_in_background, analysis.id, llm)
    return _out(_load(session, analysis.id))


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(job_id: int | None = None, session: Session = Depends(get_session)) -> list[AnalysisSummary]:
    q = select(Analysis).order_by(Analysis.created_at.desc())
    if job_id is not None:
        q = q.where(Analysis.job_id == job_id)
    return [_summary(a) for a in session.scalars(q)]


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, session: Session = Depends(get_session)) -> AnalysisOut:
    session.expire_all()  # see the background task's commits
    return _out(_load(session, analysis_id))


@router.patch("/{analysis_id}/evidence/{evidence_id}", response_model=AnalysisOut)
def update_evidence(
    analysis_id: int,
    evidence_id: int,
    body: EvidenceUpdate,
    session: Session = Depends(get_session),
    llm: LLMClient = Depends(llm_client),
) -> AnalysisOut:
    """Correct one requirement's evidence. The new quote goes through the span and semantic checks again."""
    analysis = _load(session, analysis_id)
    evidence = session.get(MatchEvidence, evidence_id)
    if evidence is None or evidence.analysis_id != analysis_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "근거 항목을 찾을 수 없습니다")
    try:
        reverify(evidence, analysis.resume.masked_text, body.resume_quote, body.verdict, llm)
    except QuoteNotInResume as e:
        detail = {"message": str(e) + ". 이력서 문장을 글자 그대로 복사해 주세요", "closest_line": e.closest}
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail) from e
    except LLMError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "의미 검증 모델에 연결할 수 없습니다") from e
    analysis.coverage = coverage_of(analysis.evidence)
    session.commit()
    return _out(_load(session, analysis_id))


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: int, session: Session = Depends(get_session)) -> None:
    session.delete(_load(session, analysis_id))
    session.commit()
