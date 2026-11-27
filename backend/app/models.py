"""Database schema (design v2, section 4 · 5 · 6).

Privacy: resumes keep only the PII-masked text the analysis needs. The original
PDF is never stored (docs/design.md, section 5).
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    # Stored as VARCHAR + CHECK so the schema stays portable and easy to migrate.
    return Enum(
        cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class RequirementType(enum.StrEnum):
    REQUIRED = "required"  # 필수
    PREFERRED = "preferred"  # 우대
    CONSTRAINT = "constraint"  # 학력·경력 등 명확한 제한 조건 (점수와 분리해 경고)


class Verdict(enum.StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    INSUFFICIENT = "insufficient"  # 근거 부족


class AnalysisStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ApplicationStage(enum.StrEnum):
    INTERESTED = "interested"  # 관심
    PLANNED = "planned"  # 지원 예정
    APPLIED = "applied"  # 지원 완료
    DOCUMENT_PASSED = "document_passed"  # 서류 합격
    INTERVIEW = "interview"  # 면접
    OFFER = "offer"  # 최종 합격
    REJECTED = "rejected"  # 불합격
    WITHDRAWN = "withdrawn"  # 지원 철회


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    masked_text: Mapped[str] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    analyses: Mapped[list[Analysis]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class JobPosting(TimestampMixin, Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_status_checked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    deadline: Mapped[date | None] = mapped_column(Date)

    analyses: Mapped[list[Analysis]] = relationship(back_populates="job", cascade="all, delete-orphan")
    applications: Mapped[list[Application]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    status: Mapped[AnalysisStatus] = mapped_column(
        _enum(AnalysisStatus, "analysis_status"), default=AnalysisStatus.PENDING
    )
    coverage: Mapped[dict | None] = mapped_column(JSON)  # {"required": [3, 4], "preferred": [2, 3], ...}
    summary: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)
    pii_masked: Mapped[dict | None] = mapped_column(JSON)
    trace: Mapped[list | None] = mapped_column(JSON)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    resume: Mapped[Resume] = relationship(back_populates="analyses")
    job: Mapped[JobPosting] = relationship(back_populates="analyses")
    evidence: Mapped[list[MatchEvidence]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class MatchEvidence(Base):
    """One requirement from the posting, the verdict, and the quoted proof from the resume."""

    __tablename__ = "match_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    requirement: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    requirement_type: Mapped[RequirementType] = mapped_column(_enum(RequirementType, "requirement_type"))
    job_quote: Mapped[str | None] = mapped_column(Text)
    job_quote_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    resume_quote: Mapped[str | None] = mapped_column(Text)
    verdict: Mapped[Verdict] = mapped_column(_enum(Verdict, "verdict"))
    span_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    semantic_verified: Mapped[bool | None] = mapped_column(Boolean)
    explanation: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[list | None] = mapped_column(JSON)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    analysis: Mapped[Analysis] = relationship(back_populates="evidence")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"), index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
        _enum(ApplicationStage, "application_stage"), default=ApplicationStage.INTERESTED
    )
    applied_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[JobPosting] = relationship(back_populates="applications")
