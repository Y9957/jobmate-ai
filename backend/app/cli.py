"""Run the analysis pipeline from the command line.

python -m app.cli samples/resume_sample.txt samples/job_sample.txt
"""

import argparse
import json
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.llm import get_llm
from app.pipeline import run_analysis

MARK = {"met": "충족", "not_met": "미충족", "insufficient": "근거 부족"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("resume", type=Path)
    p.add_argument("job", type=Path)
    p.add_argument("--json", action="store_true", help="print the full report as JSON")
    a = p.parse_args()

    settings = get_settings()
    start = time.time()
    report = run_analysis(
        a.resume.read_text(encoding="utf-8"),
        a.job.read_text(encoding="utf-8"),
        get_llm(settings),
        settings.max_match_attempts,
    )
    elapsed = time.time() - start

    if a.json:
        print(report.model_dump_json(indent=2))
        return 0

    names = {"required": "필수", "preferred": "우대", "constraint": "제한 조건"}
    print(f"모델 {report.model} · 프롬프트 {report.prompt_version} · {elapsed:.1f}s\n")
    print("  ".join(f"{names[k]} {c.met}/{c.total}" for k, c in report.coverage.items()))
    for w in report.warnings:
        print(f"⚠ {w}")
    print()
    for e in report.evidence:
        checks = f"원문대조 {'O' if e.span_verified else '-'} · 의미검증 " + (
            "O" if e.semantic_verified else "X" if e.semantic_verified is False else "-"
        )
        print(f"[{e.requirement_id}] ({names[e.requirement_type]}) {e.requirement} → {MARK[e.verdict]}  [{checks}]")
        if e.resume_quote:
            print(f'    근거: "{e.resume_quote}"')
        print(f"    설명: {e.explanation}")
        for n in e.notes:
            print(f"    ※ {n}")
    print("\n" + json.dumps(report.trace, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
