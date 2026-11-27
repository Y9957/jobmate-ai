import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import Base, engine
from app.models import Analysis, JobPosting, MatchEvidence, RequirementType, Resume, Verdict


def test_migrations_match_models():
    """The migration history produces exactly the schema the ORM models describe."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_migrations_downgrade_and_upgrade(alembic_config):
    command.downgrade(alembic_config, "base")
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars().all()
    assert set(tables) <= {"alembic_version"}
    command.upgrade(alembic_config, "head")


def _analysis(session) -> Analysis:
    resume = Resume(label="sample", masked_text="Python 3년, FastAPI 프로젝트", is_sample=True)
    job = JobPosting(company="예시 회사", title="백엔드 개발자", description="Python 필수")
    analysis = Analysis(resume=resume, job=job)
    session.add(analysis)
    session.flush()
    return analysis


def test_evidence_round_trip_and_cascade(session):
    analysis = _analysis(session)
    session.add(
        MatchEvidence(
            analysis=analysis,
            requirement="Python 경험",
            requirement_type=RequirementType.REQUIRED,
            resume_quote="Python 3년",
            verdict=Verdict.MET,
            span_verified=True,
        )
    )
    session.flush()

    stored = session.get(Analysis, analysis.id)
    assert stored.status.value == "pending"
    assert stored.evidence[0].requirement_type is RequirementType.REQUIRED

    session.delete(stored.resume)
    session.flush()
    assert session.execute(text("SELECT count(*) FROM match_evidence")).scalar() == 0


def test_invalid_verdict_rejected_by_database(session):
    analysis = _analysis(session)
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO match_evidence (analysis_id, requirement, requirement_type, verdict) "
                "VALUES (:a, 'x', 'required', 'probably')"
            ),
            {"a": analysis.id},
        )
