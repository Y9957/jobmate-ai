"""Analysis pipeline as a LangGraph state machine.

    prepare ─▶ parse_job ─▶ match ─▶ span_check ─┬─▶ semantic_check ─▶ report
                              ▲                  │
                              └──── retry ───────┘   (quote not found in the resume)

* span_check is code: every quote the matcher gives must exist in the resume.
  Failing items go back to `match` with feedback, up to `max_attempts` tries;
  after that they are downgraded to "insufficient" instead of being trusted.
* semantic_check is a second model call that only asks whether the quote alone
  supports the requirement. It catches real-but-irrelevant quotes that pass the
  span check (e.g. a Pandas sentence cited as proof of SQL).
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.llm.base import LLMClient
from app.pipeline import prompts
from app.pipeline.privacy import mask_pii
from app.pipeline.schemas import (
    AnalysisReport,
    Coverage,
    Evidence,
    JobRequirements,
    MatchBatch,
    SemanticBatch,
)
from app.pipeline.span import quote_in_source


class State(TypedDict, total=False):
    resume_text: str
    job_text: str
    pii_masked: dict[str, int]
    evidence: dict[int, Evidence]
    pending: list[int]
    feedback: dict[int, str]
    attempts: int
    trace: list[str]
    report: AnalysisReport


def build_graph(llm: LLMClient, max_attempts: int = 3):
    def log(state: State, msg: str) -> list[str]:
        return [*state.get("trace", []), msg]

    def prepare(state: State) -> State:
        masked, counts = mask_pii(state["resume_text"])
        return {
            "resume_text": masked,
            "pii_masked": counts,
            "trace": log(state, f"prepare: masked {counts or 'nothing'}"),
        }

    def parse_job(state: State) -> State:
        parsed = llm.structured(
            system=prompts.PARSE_JOB_SYSTEM, user=prompts.parse_job_user(state["job_text"]), schema=JobRequirements
        )
        evidence: dict[int, Evidence] = {}
        for i, req in enumerate(parsed.requirements, start=1):
            evidence[i] = Evidence(
                requirement_id=i,
                requirement=req.text,
                requirement_type=req.type,
                job_quote=req.job_quote,
                job_quote_verified=quote_in_source(req.job_quote, state["job_text"]),
                verdict="insufficient",
            )
        unverified = sum(not e.job_quote_verified for e in evidence.values())
        msg = f"parse_job: {len(evidence)} requirements, {unverified} with job quote not found in posting"
        return {
            "evidence": evidence,
            "pending": list(evidence),
            "feedback": {},
            "attempts": 0,
            "trace": log(state, msg),
        }

    def match(state: State) -> State:
        evidence, pending = dict(state["evidence"]), state["pending"]
        items = [(rid, evidence[rid].requirement_type, evidence[rid].requirement) for rid in pending]
        batch = llm.structured(
            system=prompts.MATCH_SYSTEM,
            user=prompts.match_user(state["resume_text"], items, state.get("feedback", {})),
            schema=MatchBatch,
        )
        answered = set()
        for m in batch.matches:
            if m.requirement_id in pending and m.requirement_id not in answered:
                answered.add(m.requirement_id)
                evidence[m.requirement_id] = evidence[m.requirement_id].model_copy(
                    update={"verdict": m.verdict, "resume_quote": m.resume_quote.strip(), "explanation": m.explanation}
                )
        for rid in pending:
            evidence[rid] = evidence[rid].model_copy(update={"match_attempts": evidence[rid].match_attempts + 1})
        missing = [rid for rid in pending if rid not in answered]
        attempt = state.get("attempts", 0) + 1
        return {
            "evidence": evidence,
            "attempts": attempt,
            "feedback": {rid: "이 requirement_id에 대한 답이 없었습니다." for rid in missing},
            "trace": log(state, f"match #{attempt}: {len(answered)}/{len(pending)} answered"),
        }

    def span_check(state: State) -> State:
        evidence, feedback = dict(state["evidence"]), dict(state.get("feedback", {}))
        still_pending: list[int] = []
        for rid in state["pending"]:
            if rid in feedback:  # not answered at all
                still_pending.append(rid)
                continue
            e = evidence[rid]
            if e.resume_quote and quote_in_source(e.resume_quote, state["resume_text"]):
                evidence[rid] = e.model_copy(update={"span_verified": True})
            elif not e.resume_quote and e.verdict != "met":
                evidence[rid] = e.model_copy(update={"span_verified": False})
            else:
                still_pending.append(rid)
                feedback[rid] = (
                    "충족(met)으로 판정했지만 인용문이 비어 있습니다."
                    if not e.resume_quote
                    else f'인용문 "{e.resume_quote}"이(가) 이력서에 없습니다. 이력서 문장을 그대로 복사하거나, '
                    "근거가 없으면 빈 문자열과 not_met으로 답하세요."
                )

        exhausted = state["attempts"] >= max_attempts
        if still_pending and exhausted:
            for rid in still_pending:
                bad = evidence[rid]
                evidence[rid] = bad.model_copy(
                    update={
                        "verdict": "insufficient",
                        "resume_quote": "",
                        "span_verified": False,
                        "notes": [
                            *bad.notes,
                            f"인용문 원문 대조 {max_attempts}회 실패로 근거 없음 처리 "
                            f'(마지막 인용: "{bad.resume_quote}")',
                        ],
                    }
                )
            msg = f"span_check: {len(still_pending)} downgraded after {max_attempts} attempts"
            still_pending, feedback = [], {}
        else:
            msg = f"span_check: {len(state['pending']) - len(still_pending)} ok, {len(still_pending)} retry"
        return {
            "evidence": evidence,
            "pending": still_pending,
            "feedback": {rid: feedback[rid] for rid in still_pending},
            "trace": log(state, msg),
        }

    def after_span(state: State) -> str:
        return "match" if state["pending"] else "semantic_check"

    def semantic_check(state: State) -> State:
        evidence = dict(state["evidence"])
        targets = [e for e in evidence.values() if e.verdict == "met" and e.span_verified]
        if not targets:
            return {"trace": log(state, "semantic_check: nothing to check")}
        batch = llm.structured(
            system=prompts.SEMANTIC_SYSTEM,
            user=prompts.semantic_user([(e.requirement_id, e.requirement, e.resume_quote) for e in targets]),
            schema=SemanticBatch,
        )
        judged = {j.requirement_id: j for j in batch.judgements}
        downgraded = 0
        for e in targets:
            j = judged.get(e.requirement_id)
            if j is None:
                evidence[e.requirement_id] = e.model_copy(update={"notes": [*e.notes, "의미 검증 응답 없음"]})
            elif j.supports:
                evidence[e.requirement_id] = e.model_copy(update={"semantic_verified": True})
            else:
                downgraded += 1
                evidence[e.requirement_id] = e.model_copy(
                    update={
                        "semantic_verified": False,
                        "verdict": "insufficient",
                        "notes": [*e.notes, f"의미 검증 실패로 충족 → 근거 부족: {j.reason}"],
                    }
                )
        return {
            "evidence": evidence,
            "trace": log(state, f"semantic_check: {len(targets)} checked, {downgraded} downgraded"),
        }

    def report(state: State) -> State:
        evidence = [state["evidence"][k] for k in sorted(state["evidence"])]
        coverage = {
            kind: Coverage(
                met=sum(e.verdict == "met" for e in evidence if e.requirement_type == kind),
                total=sum(e.requirement_type == kind for e in evidence),
            )
            for kind in ("required", "preferred", "constraint")
        }
        warnings = [
            f"제한 조건 {'미충족' if e.verdict == 'not_met' else '확인 필요'}: {e.requirement}"
            for e in evidence
            if e.requirement_type == "constraint" and e.verdict != "met"
        ]
        result = AnalysisReport(
            coverage=coverage,
            warnings=warnings,
            evidence=evidence,
            model=llm.name,
            prompt_version=prompts.PROMPT_VERSION,
            pii_masked=state.get("pii_masked", {}),
            trace=log(state, "report"),
        )
        return {"report": result}

    g = StateGraph(State)
    for name, fn in [
        ("prepare", prepare),
        ("parse_job", parse_job),
        ("match", match),
        ("span_check", span_check),
        ("semantic_check", semantic_check),
        ("report", report),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "parse_job")
    g.add_edge("parse_job", "match")
    g.add_edge("match", "span_check")
    g.add_conditional_edges("span_check", after_span, {"match": "match", "semantic_check": "semantic_check"})
    g.add_edge("semantic_check", "report")
    g.add_edge("report", END)
    return g.compile()


def run_analysis(resume_text: str, job_text: str, llm: LLMClient, max_attempts: int = 3) -> AnalysisReport:
    graph = build_graph(llm, max_attempts)
    final = graph.invoke({"resume_text": resume_text, "job_text": job_text})
    return final["report"]
