"""Request and response bodies of the HTTP API."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models import AnalysisStatus, ApplicationStage, RequirementType, Verdict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- resumes ----------


class ResumeCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=20, max_length=30_000, description="이력서 본문. 저장 전에 연락처가 마스킹된다")
    is_sample: bool = False


class ResumeOut(ORM):
    id: int
    label: str
    masked_text: str
    is_sample: bool
    created_at: datetime


class ResumeSummary(ORM):
    id: int
    label: str
    is_sample: bool
    created_at: datetime


class ExtractedText(BaseModel):
    text: str
    pages: int
    pii_found: dict[str, int]
    note: str = (
        "추출된 텍스트입니다. 줄 순서가 섞였거나 빠진 내용이 없는지 확인한 뒤 저장하세요. 원본 PDF는 저장하지 않습니다."
    )


# ---------- jobs ----------


class JobCreate(BaseModel):
    company: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=20, max_length=30_000, description="공고 본문을 붙여넣는다")
    source_url: HttpUrl | None = None
    deadline: date | None = None


class JobOut(ORM):
    id: int
    company: str
    title: str
    description: str
    source_url: str | None
    source_status_checked: bool
    deadline: date | None
    created_at: datetime


class JobSummary(ORM):
    id: int
    company: str
    title: str
    deadline: date | None
    created_at: datetime


# ---------- analyses ----------


class AnalysisCreate(BaseModel):
    resume_id: int
    job_id: int


class EvidenceOut(ORM):
    id: int
    position: int
    requirement: str
    requirement_type: RequirementType
    job_quote: str | None
    job_quote_verified: bool
    resume_quote: str | None
    verdict: Verdict
    span_verified: bool
    semantic_verified: bool | None
    explanation: str | None
    notes: list[str] | None
    user_edited: bool


class EvidenceUpdate(BaseModel):
    resume_quote: str = Field(
        default="", max_length=2_000, description="이력서에서 그대로 복사한 근거 문장. 비우면 근거 없음"
    )
    verdict: Verdict | None = Field(default=None, description="생략하면 인용문이 있으면 met, 없으면 not_met")


class Coverage(BaseModel):
    met: int
    total: int


class AnalysisOut(ORM):
    id: int
    resume_id: int
    job_id: int
    status: AnalysisStatus
    coverage: dict[str, Coverage] | None
    warnings: list[str]
    model: str | None
    prompt_version: str | None
    error: str | None
    pii_masked: dict[str, int] | None
    trace: list[str] | None
    created_at: datetime
    finished_at: datetime | None
    evidence: list[EvidenceOut]


class AnalysisSummary(BaseModel):
    id: int
    status: AnalysisStatus
    resume_id: int
    resume_label: str
    job_id: int
    job_title: str
    company: str
    coverage: dict[str, Coverage] | None
    created_at: datetime


# ---------- applications ----------


class ApplicationCreate(BaseModel):
    job_id: int
    stage: ApplicationStage = ApplicationStage.INTERESTED
    applied_at: date | None = None
    notes: str | None = Field(default=None, max_length=2_000)


class ApplicationUpdate(BaseModel):
    stage: ApplicationStage | None = None
    applied_at: date | None = None
    notes: str | None = Field(default=None, max_length=2_000)


class ApplicationOut(ORM):
    id: int
    job_id: int
    stage: ApplicationStage
    applied_at: date | None
    notes: str | None
    updated_at: datetime
    company: str
    job_title: str


class Dashboard(BaseModel):
    resumes: int
    jobs: int
    analyses: int
    applications_by_stage: dict[str, int]
    recent_analyses: list[AnalysisSummary]
