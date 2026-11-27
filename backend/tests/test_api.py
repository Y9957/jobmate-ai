"""HTTP API end to end against real PostgreSQL, with a scripted model instead of a live one."""

import pymupdf
import pytest
from sqlalchemy import text

from app.api.deps import llm_client
from app.db import engine
from app.llm.fake import FakeLLM
from app.main import app
from app.pipeline.schemas import (
    ExtractedRequirement,
    JobRequirements,
    MatchBatch,
    MatchItem,
    SemanticBatch,
    SemanticItem,
)

RESUME = """김가상 (가상 인물)
연락처 010-1234-5678 · kim@example.com
[경력]
- FastAPI로 사내 분석 API 3종을 개발했습니다.
- Python과 Pandas로 매출 데이터 20만 건을 정제했습니다.
[기술]
Python, SQL, FastAPI"""

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


@pytest.fixture
def llm():
    fake = FakeLLM()
    app.dependency_overrides[llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(llm_client, None)


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE resumes, job_postings, analyses, match_evidence, applications RESTART IDENTITY CASCADE")
        )
    yield


def _seed(client):
    r = client.post("/api/resumes", json={"label": "샘플", "text": RESUME, "is_sample": True}).json()
    j = client.post("/api/jobs", json={"company": "가상회사", "title": "백엔드 개발자", "description": JOB}).json()
    return r, j


def _queue_happy_path(llm):
    llm.queue(JobRequirements, REQS)
    llm.queue(
        MatchBatch,
        MatchBatch(
            matches=[
                MatchItem(
                    requirement_id=1,
                    verdict="met",
                    resume_quote="FastAPI로 사내 분석 API 3종을 개발했습니다.",
                    explanation="e",
                ),
                MatchItem(requirement_id=2, verdict="not_met", resume_quote="", explanation="e"),
                MatchItem(
                    requirement_id=3,
                    verdict="met",
                    resume_quote="Python과 Pandas로 매출 데이터 20만 건을 정제했습니다.",
                    explanation="e",
                ),
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


def test_resume_is_stored_masked(client):
    r, _ = _seed(client)
    stored = client.get(f"/api/resumes/{r['id']}").json()["masked_text"]
    assert "010-1234-5678" not in stored and "kim@example.com" not in stored
    assert "[PHONE]" in stored and "[EMAIL]" in stored


def test_job_link_is_kept_but_never_marked_checked(client):
    j = client.post(
        "/api/jobs",
        json={"company": "가상", "title": "t", "description": JOB, "source_url": "https://example.com/jobs/1"},
    ).json()
    assert j["source_url"] == "https://example.com/jobs/1" and j["source_status_checked"] is False


def test_analysis_runs_and_result_is_stored(client, llm):
    r, j = _seed(client)
    _queue_happy_path(llm)

    started = client.post("/api/analyses", json={"resume_id": r["id"], "job_id": j["id"]})
    assert started.status_code == 202 and started.json()["status"] == "pending"

    a = client.get(f"/api/analyses/{started.json()['id']}").json()  # background task already ran in TestClient
    assert a["status"] == "done", a["error"]
    assert [e["verdict"] for e in a["evidence"]] == ["met", "not_met", "insufficient"]
    assert a["coverage"]["required"] == {"met": 1, "total": 1}
    assert a["warnings"] == ["제한 조건 미충족: 경력 3년 이상"]
    assert a["evidence"][2]["semantic_verified"] is False and a["evidence"][2]["notes"]
    assert all("010-1234-5678" not in user for _, _, user in llm.calls)

    listed = client.get("/api/analyses").json()
    assert listed[0]["job_title"] == "백엔드 개발자" and listed[0]["coverage"]["preferred"] == {"met": 0, "total": 1}


def test_model_failure_ends_in_failed_status(client, llm):
    r, j = _seed(client)  # nothing queued: the fake raises LLMError
    a_id = client.post("/api/analyses", json={"resume_id": r["id"], "job_id": j["id"]}).json()["id"]
    a = client.get(f"/api/analyses/{a_id}").json()
    assert a["status"] == "failed" and "LLMError" in a["error"]


def test_user_correction_is_reverified(client, llm):
    r, j = _seed(client)
    _queue_happy_path(llm)
    a = client.get(
        f"/api/analyses/{client.post('/api/analyses', json={'resume_id': r['id'], 'job_id': j['id']}).json()['id']}"
    ).json()
    sql = a["evidence"][2]

    # a quote that is not in the resume is refused, with the closest real line as a hint
    bad = client.patch(f"/api/analyses/{a['id']}/evidence/{sql['id']}", json={"resume_quote": "SQL을 5년간 썼습니다"})
    assert bad.status_code == 422 and "closest_line" in bad.json()["detail"]

    # the right line passes both checks
    llm.queue(
        SemanticBatch, SemanticBatch(judgements=[SemanticItem(requirement_id=3, supports=True, reason="SQL 명시")])
    )
    ok = client.patch(f"/api/analyses/{a['id']}/evidence/{sql['id']}", json={"resume_quote": "Python, SQL, FastAPI"})
    assert ok.status_code == 200
    fixed = ok.json()["evidence"][2]
    assert fixed["verdict"] == "met" and fixed["user_edited"] and fixed["span_verified"] and fixed["semantic_verified"]
    assert ok.json()["coverage"]["preferred"] == {"met": 1, "total": 1}


def test_user_cannot_force_met_past_the_semantic_check(client, llm):
    r, j = _seed(client)
    _queue_happy_path(llm)
    a = client.get(
        f"/api/analyses/{client.post('/api/analyses', json={'resume_id': r['id'], 'job_id': j['id']}).json()['id']}"
    ).json()
    exp = a["evidence"][1]
    llm.queue(
        SemanticBatch, SemanticBatch(judgements=[SemanticItem(requirement_id=2, supports=False, reason="기간 없음")])
    )
    res = client.patch(
        f"/api/analyses/{a['id']}/evidence/{exp['id']}",
        json={"resume_quote": "FastAPI로 사내 분석 API 3종을 개발했습니다.", "verdict": "met"},
    ).json()
    assert res["evidence"][1]["verdict"] == "insufficient"


def test_pdf_extract_does_not_store_anything(client):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Backend developer. Python, FastAPI, PostgreSQL. Contact 010-1234-5678")
    pdf = doc.tobytes()
    res = client.post("/api/resumes/extract", files={"file": ("cv.pdf", pdf, "application/pdf")})
    assert res.status_code == 200
    body = res.json()
    assert "FastAPI" in body["text"] and body["pages"] == 1 and body["pii_found"] == {"phone": 1}
    assert client.get("/api/resumes").json() == []


def test_pdf_extract_rejects_garbage(client):
    res = client.post("/api/resumes/extract", files={"file": ("cv.pdf", b"not a pdf", "application/pdf")})
    assert res.status_code == 422


def test_applications_and_dashboard(client):
    _, j = _seed(client)
    created = client.post("/api/applications", json={"job_id": j["id"], "stage": "planned"}).json()
    moved = client.patch(
        f"/api/applications/{created['id']}", json={"stage": "applied", "applied_at": "2026-11-27"}
    ).json()
    assert moved["stage"] == "applied" and moved["company"] == "가상회사"

    d = client.get("/api/dashboard").json()
    assert d["resumes"] == 1 and d["jobs"] == 1
    assert d["applications_by_stage"]["applied"] == 1 and d["applications_by_stage"]["planned"] == 0


def test_not_found(client):
    assert client.get("/api/resumes/999").status_code == 404
    assert client.post("/api/analyses", json={"resume_id": 999, "job_id": 999}).status_code == 404
