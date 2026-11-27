"""Inputs and outputs of every pipeline step, as Pydantic models.

LLM-facing models (the ones passed as `schema=` to the client) are kept small and
flat: local models follow small schemas far more reliably.
"""

from typing import Literal

from pydantic import BaseModel, Field

RequirementKind = Literal["required", "preferred", "constraint"]
VerdictKind = Literal["met", "not_met", "insufficient"]


# ---------- LLM outputs ----------


class ExtractedRequirement(BaseModel):
    text: str = Field(description="요구조건을 한 문장으로 요약")
    type: RequirementKind = Field(
        description="required=필수 자격, preferred=우대 사항, constraint=학력·경력 연수 등 명확한 제한 조건"
    )
    job_quote: str = Field(description="채용공고에서 이 요구조건이 나온 문장을 한 글자도 바꾸지 않고 그대로 복사")


class JobRequirements(BaseModel):
    requirements: list[ExtractedRequirement]


class MatchItem(BaseModel):
    requirement_id: int
    verdict: VerdictKind = Field(description="met=충족, not_met=미충족, insufficient=판단 근거 부족")
    resume_quote: str = Field(description="이력서에서 근거가 되는 문장을 그대로 복사. 근거가 없으면 빈 문자열")
    explanation: str = Field(description="판정 이유 한두 문장")


class MatchBatch(BaseModel):
    matches: list[MatchItem]


class SemanticItem(BaseModel):
    requirement_id: int
    supports: bool = Field(description="인용문만 보고 요구조건 충족을 직접 확인할 수 있으면 true")
    reason: str


class SemanticBatch(BaseModel):
    judgements: list[SemanticItem]


# ---------- Pipeline output ----------


class Evidence(BaseModel):
    requirement_id: int
    requirement: str
    requirement_type: RequirementKind
    job_quote: str
    job_quote_verified: bool
    verdict: VerdictKind
    resume_quote: str = ""
    span_verified: bool = False
    semantic_verified: bool | None = None
    explanation: str = ""
    match_attempts: int = 0
    notes: list[str] = Field(default_factory=list)


class Coverage(BaseModel):
    met: int
    total: int


class AnalysisReport(BaseModel):
    coverage: dict[RequirementKind, Coverage]
    warnings: list[str]
    evidence: list[Evidence]
    model: str
    prompt_version: str
    pii_masked: dict[str, int]
    trace: list[str]
