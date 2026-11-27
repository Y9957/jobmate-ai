"""Run the evaluation: one pipeline run per case, three verification settings read from it.

    python -m app.evals.run --split dev
    python -m app.evals.run --split test --limit 2

The full pipeline runs once per case. A / B / C are its snapshots after the first match,
after the span check (with retries), and after the semantic check — so all three are
scored on the same model outputs, and run-to-run variance of the model cannot make one
setting look better or worse than another.

Results go to evals/results/<timestamp>_<split>_<model>_<prompt>.json and a Markdown table.
"""

import argparse
import json
import sys
import time
from datetime import datetime

from pydantic import BaseModel

from app.config import get_settings
from app.evals.dataset import DEFAULT_CASES_DIR, Case, load_cases
from app.evals.metrics import ItemResult, Summary, outcome, summarize
from app.llm import get_llm
from app.llm.base import LLMClient
from app.pipeline import prompts
from app.pipeline.graph import run_matching_stages
from app.pipeline.schemas import Evidence
from app.pipeline.span import quote_in_source

# (key, snapshot, label, which stages' LLM calls it needs)
SYSTEMS = [
    ("baseline", "first_match", "A. 검증 없음 (첫 매칭 결과를 그대로 신뢰)", ("first",)),
    ("span", "after_span", "B. 원문 대조 + 재시도", ("match",)),
    ("full", "after_semantic", "C. 원문 대조 + 재시도 + 의미 검증", ("match", "semantic")),
]
RESULTS_DIR = DEFAULT_CASES_DIR.parent / "results"


class SystemResult(BaseModel):
    system: str
    label: str
    summary: Summary
    llm_calls: int
    items: list[ItemResult]


def item(case: Case, gold, pred: Evidence) -> ItemResult:
    return ItemResult(
        case_id=case.case_id,
        requirement=gold.text,
        tags=list(gold.tags),
        gold=gold.gold,
        verdict=pred.verdict,
        quote=pred.resume_quote,
        quote_exists=bool(pred.resume_quote) and quote_in_source(pred.resume_quote, case.resume),
        outcome=outcome(gold, pred, case.resume),
        notes=pred.notes,
    )


def evaluate(llm: LLMClient, cases: list[Case], max_attempts: int) -> tuple[list[SystemResult], float]:
    items: dict[str, list[ItemResult]] = {key: [] for key, *_ in SYSTEMS}
    calls = {"first": 0, "match": 0, "semantic": 0}
    start = time.time()
    for i, case in enumerate(cases, 1):
        final = run_matching_stages(
            case.resume, [r.as_requirement() for r in case.requirements], llm, max_attempts=max_attempts
        )
        snaps, used = final["snapshots"], final.get("calls", {})
        calls["first"] += 1
        calls["match"] += used.get("match", 0)
        calls["semantic"] += used.get("semantic", 0)
        for key, snap, *_ in SYSTEMS:
            for gold, pred in zip(case.requirements, snaps[snap], strict=True):
                items[key].append(item(case, gold, pred))
        print(f"  {i}/{len(cases)} {case.case_id}  {final['trace'][1:-1]}", file=sys.stderr, flush=True)
    results = [
        SystemResult(
            system=key,
            label=label,
            summary=summarize(items[key]),
            llm_calls=sum(calls[s] for s in stages),
            items=items[key],
        )
        for key, _, label, stages in SYSTEMS
    ]
    return results, round(time.time() - start, 1)


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def to_markdown(model: str, split: str, n_cases: int, results: list[SystemResult]) -> str:
    head = (
        f"데이터 `{split}` · 모델 `{model}` · 프롬프트 `{prompts.PROMPT_VERSION}` · 케이스 {n_cases}개 · "
        f"요구조건 {results[0].summary.items}개\n\n"
        "| 시스템 | 근거 없는 충족 판정 ↓ | 지어낸 인용 ↓ | 잘못된 충족(오탐) ↓ "
        "| 충족 재현율 ↑ | 판정 정확도 ↑ | LLM 호출 |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
    )
    rows = [
        f"| {r.label} | {pct(r.summary.unsupported_met_rate)} | {pct(r.summary.fabricated_quote_rate)} | "
        f"{pct(r.summary.false_met_rate)} | {pct(r.summary.met_recall)} | {pct(r.summary.verdict_accuracy)} | "
        f"{r.llm_calls} |"
        for r in results
    ]
    tags = sorted({t for r in results for t in r.summary.false_met_by_tag})
    tag_table = (
        "\n\n함정 유형별 오탐(정답이 미충족인데 충족으로 판정한 수)\n\n"
        + "| 시스템 | "
        + " | ".join(tags)
        + " |\n|---|"
        + "---:|" * len(tags)
        + "\n"
        + "\n".join(
            f"| {r.system} | " + " | ".join(r.summary.false_met_by_tag.get(t, "-") for t in tags) + " |"
            for r in results
        )
    )
    return head + "\n".join(rows) + tag_table + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--split", choices=["easy", "dev", "test"], required=True)
    p.add_argument("--limit", type=int, default=0, help="only the first N cases (smoke run)")
    a = p.parse_args()

    settings = get_settings()
    llm = get_llm(settings)
    cases = load_cases((a.split,))
    if a.limit:
        cases = cases[: a.limit]

    results, seconds = evaluate(llm, cases, settings.max_match_attempts)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = llm.name.replace(":", "-").replace("/", "-")
    base = RESULTS_DIR / f"{stamp}_{a.split}_{slug}_{prompts.PROMPT_VERSION}"
    payload = {
        "split": a.split,
        "model": llm.name,
        "prompt_version": prompts.PROMPT_VERSION,
        "cases": len(cases),
        "seconds": seconds,
        "results": [r.model_dump() for r in results],
    }
    base.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = to_markdown(llm.name, a.split, len(cases), results) + f"\n전체 실행 시간 {seconds:.0f}s\n"
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print(f"saved: {base.with_suffix('.json')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
