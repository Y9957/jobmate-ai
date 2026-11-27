"""Run the evaluation: same prompts, three verification settings, one model.

    python -m app.evals.run                      # all systems, local model from settings
    python -m app.evals.run --systems full --limit 2

Results go to evals/results/<timestamp>_<model>.json and a Markdown table next to it.
"""

import argparse
import json
import sys
import time
from datetime import datetime

from pydantic import BaseModel

from app.config import get_settings
from app.evals.dataset import DEFAULT_CASES_DIR, load_cases
from app.evals.metrics import ItemResult, Summary, outcome, summarize
from app.llm import get_llm
from app.llm.base import LLMClient, T
from app.pipeline import prompts, run_matching
from app.pipeline.span import quote_in_source

SYSTEMS = {
    "baseline": {
        "verify_span": False,
        "verify_semantic": False,
        "label": "A. 검증 없음 (단일 매칭 결과를 그대로 신뢰)",
    },
    "span": {"verify_span": True, "verify_semantic": False, "label": "B. 원문 대조 + 재시도"},
    "full": {"verify_span": True, "verify_semantic": True, "label": "C. 원문 대조 + 재시도 + 의미 검증"},
}
RESULTS_DIR = DEFAULT_CASES_DIR.parent / "results"


class CountingLLM:
    """Wraps a client to count calls per run (a cost proxy that works for free local models too)."""

    def __init__(self, inner: LLMClient):
        self.inner, self.name, self.calls = inner, inner.name, 0

    def structured(self, *, system: str, user: str, schema: type[T]) -> T:
        self.calls += 1
        return self.inner.structured(system=system, user=user, schema=schema)


class SystemResult(BaseModel):
    system: str
    label: str
    summary: Summary
    llm_calls: int
    seconds: float
    items: list[ItemResult]


def run_system(name: str, llm: LLMClient, cases, max_attempts: int) -> SystemResult:
    cfg = SYSTEMS[name]
    counting = CountingLLM(llm)
    items: list[ItemResult] = []
    start = time.time()
    for i, case in enumerate(cases, 1):
        report = run_matching(
            case.resume,
            [r.as_requirement() for r in case.requirements],
            counting,
            max_attempts=max_attempts,
            verify_span=cfg["verify_span"],
            verify_semantic=cfg["verify_semantic"],
        )
        for gold, pred in zip(case.requirements, report.evidence, strict=True):
            items.append(
                ItemResult(
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
            )
        print(f"  [{name}] {i}/{len(cases)} {case.case_id}", file=sys.stderr, flush=True)
    return SystemResult(
        system=name,
        label=cfg["label"],
        summary=summarize(items),
        llm_calls=counting.calls,
        seconds=round(time.time() - start, 1),
        items=items,
    )


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def to_markdown(model: str, split: str, n_cases: int, results: list[SystemResult]) -> str:
    head = (
        f"데이터 `{split}` · 모델 `{model}` · 프롬프트 `{prompts.PROMPT_VERSION}` · 케이스 {n_cases}개 · "
        f"요구조건 {results[0].summary.items}개\n\n"
        "| 시스템 | 근거 없는 충족 판정 ↓ | 지어낸 인용 ↓ | 잘못된 충족(오탐) ↓ "
        "| 충족 재현율 ↑ | 판정 정확도 ↑ | LLM 호출 | 시간 |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    rows = [
        f"| {r.label} | {pct(r.summary.unsupported_met_rate)} | {pct(r.summary.fabricated_quote_rate)} | "
        f"{pct(r.summary.false_met_rate)} | {pct(r.summary.met_recall)} | {pct(r.summary.verdict_accuracy)} | "
        f"{r.llm_calls} | {r.seconds:.0f}s |"
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
    p.add_argument("--systems", default="baseline,span,full")
    p.add_argument("--split", choices=["easy", "dev", "test"], required=True)
    p.add_argument("--limit", type=int, default=0, help="only the first N cases (smoke run)")
    a = p.parse_args()

    settings = get_settings()
    llm = get_llm(settings)
    cases = load_cases((a.split,))
    if a.limit:
        cases = cases[: a.limit]

    results = [run_system(s, llm, cases, settings.max_match_attempts) for s in a.systems.split(",")]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = llm.name.replace(":", "-").replace("/", "-")
    base = RESULTS_DIR / f"{stamp}_{a.split}_{slug}_{prompts.PROMPT_VERSION}"
    payload = {
        "split": a.split,
        "model": llm.name,
        "prompt_version": prompts.PROMPT_VERSION,
        "cases": len(cases),
        "results": [r.model_dump() for r in results],
    }
    base.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = to_markdown(llm.name, a.split, len(cases), results)
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print(f"saved: {base.with_suffix('.json')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
