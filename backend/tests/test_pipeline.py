"""Pipeline behaviour with a scripted model — no network, no cost."""

from app.llm.fake import FakeLLM
from app.pipeline import run_analysis
from app.pipeline.schemas import (
    ExtractedRequirement,
    JobRequirements,
    MatchBatch,
    MatchItem,
    SemanticBatch,
    SemanticItem,
)

RESUME = """홍길동
연락처 010-1234-5678
- Python과 Pandas로 매출 데이터 20만 건을 정제했습니다.
- FastAPI로 사내 분석 API 3종을 개발했습니다.
기술: Python, SQL, FastAPI"""

JOB = """[자격 요건]
- Python 기반 백엔드 개발 경험
- 관련 경력 3년 이상
[우대 사항]
- SQL 활용 능력"""

REQS = JobRequirements(
    requirements=[
        ExtractedRequirement(text="Python 백엔드 개발 경험", type="required", job_quote="Python 기반 백엔드 개발 경험"),
        ExtractedRequirement(text="경력 3년 이상", type="constraint", job_quote="관련 경력 3년 이상"),
        ExtractedRequirement(text="SQL 활용 능력", type="preferred", job_quote="SQL 활용 능력"),
    ]
)


def m(rid, verdict, quote, why="이유"):
    return MatchItem(requirement_id=rid, verdict=verdict, resume_quote=quote, explanation=why)


def test_happy_path_coverage_and_warnings():
    llm = FakeLLM()
    llm.queue(JobRequirements, REQS)
    llm.queue(
        MatchBatch,
        MatchBatch(
            matches=[
                m(1, "met", "FastAPI로 사내 분석 API 3종을 개발했습니다."),
                m(2, "not_met", ""),
                m(3, "met", "기술: Python, SQL, FastAPI"),
            ]
        ),
    )
    llm.queue(
        SemanticBatch,
        SemanticBatch(
            judgements=[
                SemanticItem(requirement_id=1, supports=True, reason="FastAPI는 Python 백엔드"),
                SemanticItem(requirement_id=3, supports=True, reason="SQL 명시"),
            ]
        ),
    )

    report = run_analysis(RESUME, JOB, llm)

    assert report.coverage["required"].model_dump() == {"met": 1, "total": 1}
    assert report.coverage["preferred"].model_dump() == {"met": 1, "total": 1}
    assert report.coverage["constraint"].model_dump() == {"met": 0, "total": 1}
    assert report.warnings == ["제한 조건 미충족: 경력 3년 이상"]
    assert all(e.job_quote_verified for e in report.evidence)
    assert report.evidence[0].span_verified and report.evidence[0].semantic_verified
    assert report.pii_masked == {"phone": 1}


def test_model_never_sees_unmasked_contact_details():
    llm = FakeLLM()
    llm.queue(JobRequirements, REQS)
    llm.queue(MatchBatch, MatchBatch(matches=[m(1, "not_met", ""), m(2, "not_met", ""), m(3, "not_met", "")]))
    run_analysis(RESUME, JOB, llm)
    assert all("010-1234-5678" not in user for _, _, user in llm.calls)


def test_invented_quote_is_retried_with_feedback_then_accepted():
    llm = FakeLLM()
    llm.queue(JobRequirements, REQS)
    llm.queue(
        MatchBatch,
        MatchBatch(
            matches=[
                m(1, "met", "Django로 대규모 백엔드를 운영했습니다."),  # not in the resume
                m(2, "not_met", ""),
                m(3, "not_met", ""),
            ]
        ),
        lambda system, user: MatchBatch(matches=[m(1, "met", "FastAPI로 사내 분석 API 3종을 개발했습니다.")]),
    )
    llm.queue(SemanticBatch, SemanticBatch(judgements=[SemanticItem(requirement_id=1, supports=True, reason="ok")]))

    report = run_analysis(RESUME, JOB, llm)

    assert llm.count(MatchBatch) == 2
    retry_prompt = [user for name, _, user in llm.calls if name == "MatchBatch"][1]
    assert "requirement_id=1" in retry_prompt and "requirement_id=2" not in retry_prompt  # only the failed one
    assert "Django로 대규모 백엔드를 운영했습니다." in retry_prompt  # told what was wrong
    first = report.evidence[0]
    assert first.verdict == "met" and first.span_verified and first.match_attempts == 2


def test_quote_that_never_matches_is_downgraded_not_trusted():
    llm = FakeLLM()
    llm.queue(JobRequirements, REQS)
    bad = lambda system, user: MatchBatch(matches=[m(1, "met", "Kubernetes 운영 3년")])  # noqa: E731
    llm.queue(
        MatchBatch,
        MatchBatch(matches=[m(1, "met", "Kubernetes 운영 3년"), m(2, "not_met", ""), m(3, "not_met", "")]),
        bad,
        bad,
    )

    report = run_analysis(RESUME, JOB, llm, max_attempts=3)

    assert llm.count(MatchBatch) == 3
    first = report.evidence[0]
    assert first.verdict == "insufficient" and first.resume_quote == "" and not first.span_verified
    assert "3회 실패" in first.notes[0]
    assert llm.count(SemanticBatch) == 0  # nothing left to check


def test_real_but_irrelevant_quote_is_caught_by_semantic_check():
    """The failure seen on the local model: a Pandas sentence cited as proof of SQL."""
    llm = FakeLLM()
    llm.queue(JobRequirements, REQS)
    llm.queue(
        MatchBatch,
        MatchBatch(
            matches=[
                m(1, "met", "FastAPI로 사내 분석 API 3종을 개발했습니다."),
                m(2, "not_met", ""),
                m(
                    3, "met", "Python과 Pandas로 매출 데이터 20만 건을 정제했습니다."
                ),  # exists, but says nothing about SQL
            ]
        ),
    )
    llm.queue(
        SemanticBatch,
        SemanticBatch(
            judgements=[
                SemanticItem(requirement_id=1, supports=True, reason="ok"),
                SemanticItem(requirement_id=3, supports=False, reason="SQL 언급 없음"),
            ]
        ),
    )

    report = run_analysis(RESUME, JOB, llm)

    sql = report.evidence[2]
    assert sql.span_verified is True  # the span check alone would have accepted it
    assert sql.semantic_verified is False and sql.verdict == "insufficient"
    assert report.coverage["preferred"].met == 0


def test_missing_answer_is_asked_again():
    llm = FakeLLM()
    llm.queue(JobRequirements, REQS)
    llm.queue(
        MatchBatch,
        MatchBatch(matches=[m(1, "not_met", ""), m(2, "not_met", "")]),  # forgot id 3
        MatchBatch(matches=[m(3, "not_met", "")]),
    )
    report = run_analysis(RESUME, JOB, llm)
    assert llm.count(MatchBatch) == 2
    assert report.evidence[2].verdict == "not_met"


def test_job_quote_not_in_posting_is_flagged():
    llm = FakeLLM()
    llm.queue(
        JobRequirements,
        JobRequirements(
            requirements=[
                ExtractedRequirement(text="Go 경험", type="required", job_quote="Go 언어 3년 이상"),  # not in JOB
            ]
        ),
    )
    llm.queue(MatchBatch, MatchBatch(matches=[m(1, "not_met", "")]))
    report = run_analysis(RESUME, JOB, llm)
    assert report.evidence[0].job_quote_verified is False
