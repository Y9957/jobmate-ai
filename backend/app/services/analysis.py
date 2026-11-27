"""Running the pipeline for stored records, and re-verifying evidence a user corrected."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.llm.base import LLMClient, LLMError
from app.models import Analysis, AnalysisStatus, MatchEvidence, RequirementType, Verdict
from app.pipeline import prompts, run_analysis
from app.pipeline.schemas import SemanticBatch
from app.pipeline.span import closest_line, repair_quote, source_context


def coverage_of(evidence: list[MatchEvidence]) -> dict[str, dict[str, int]]:
    return {
        kind.value: {
            "met": sum(e.verdict == Verdict.MET for e in evidence if e.requirement_type == kind),
            "total": sum(e.requirement_type == kind for e in evidence),
        }
        for kind in RequirementType
    }


def warnings_of(evidence: list[MatchEvidence]) -> list[str]:
    return [
        f"제한 조건 {'미충족' if e.verdict == Verdict.NOT_MET else '확인 필요'}: {e.requirement}"
        for e in sorted(evidence, key=lambda x: x.position)
        if e.requirement_type == RequirementType.CONSTRAINT and e.verdict != Verdict.MET
    ]


def execute(session: Session, analysis_id: int, llm: LLMClient, max_attempts: int) -> None:
    """Run the pipeline for one pending analysis and store the result (called as a background task)."""
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        return
    analysis.status = AnalysisStatus.RUNNING
    session.commit()
    try:
        report = run_analysis(analysis.resume.masked_text, analysis.job.description, llm, max_attempts)
    except (LLMError, Exception) as e:  # noqa: BLE001 — any failure must end in a visible "failed" state
        analysis.status = AnalysisStatus.FAILED
        analysis.error = f"{type(e).__name__}: {e}"[:2_000]
        analysis.finished_at = datetime.now(UTC)
        session.commit()
        return

    analysis.evidence = [
        MatchEvidence(
            position=e.requirement_id,
            requirement=e.requirement,
            requirement_type=RequirementType(e.requirement_type),
            job_quote=e.job_quote,
            job_quote_verified=e.job_quote_verified,
            resume_quote=e.resume_quote or None,
            verdict=Verdict(e.verdict),
            span_verified=e.span_verified,
            semantic_verified=e.semantic_verified,
            explanation=e.explanation,
            notes=e.notes,
        )
        for e in report.evidence
    ]
    analysis.coverage = coverage_of(analysis.evidence)
    analysis.model = report.model
    analysis.prompt_version = report.prompt_version
    analysis.trace = report.trace
    analysis.status = AnalysisStatus.DONE
    analysis.finished_at = datetime.now(UTC)
    session.commit()


class QuoteNotInResume(ValueError):
    def __init__(self, closest: str | None):
        self.closest = closest
        super().__init__("인용문이 이력서 원문에 없습니다")


def reverify(evidence: MatchEvidence, resume_text: str, quote: str, verdict: Verdict | None, llm: LLMClient) -> None:
    """Apply a user's correction, then run the same two checks the pipeline runs.

    The user may be wrong too: an edited quote must still be verbatim (span check),
    and a "met" verdict must still pass the semantic check.
    """
    quote = quote.strip()
    notes = list(evidence.notes or [])
    if quote:
        repaired = repair_quote(quote, resume_text)
        if repaired is None:
            raise QuoteNotInResume(closest_line(quote, resume_text))
        quote = repaired
    target = verdict or (Verdict.MET if quote else Verdict.NOT_MET)
    if target == Verdict.MET and not quote:
        raise QuoteNotInResume(None)

    evidence.resume_quote = quote or None
    evidence.span_verified = bool(quote)
    evidence.user_edited = True
    evidence.verdict = target
    evidence.semantic_verified = None
    notes.append(f"사용자가 근거를 수정함 ({target.value})")

    if target == Verdict.MET:
        batch = llm.structured(
            system=prompts.SEMANTIC_SYSTEM,
            user=prompts.semantic_user(
                [(evidence.position, evidence.requirement, quote, source_context(quote, resume_text))]
            ),
            schema=SemanticBatch,
        )
        judged = next((j for j in batch.judgements if j.requirement_id == evidence.position), None)
        if judged is None:
            notes.append("의미 검증 응답 없음")
        elif judged.supports:
            evidence.semantic_verified = True
        else:
            evidence.semantic_verified = False
            evidence.verdict = Verdict.INSUFFICIENT
            notes.append(f"의미 검증 실패로 충족 → 근거 부족: {judged.reason}")
    evidence.notes = notes
