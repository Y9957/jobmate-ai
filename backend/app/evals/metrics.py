"""Scoring. A prediction is judged on two things: the verdict, and whether its quote is real proof.

Outcome per item:
  correct_met     predicted met, gold met, quote is one of the labelled evidence lines
  met_bad_quote   predicted met, gold met, but the quote is missing, invented or points elsewhere
  false_met       predicted met, gold not_met                      (the costly error)
  correct_not     predicted not met, gold not_met
  missed_met      predicted not met, gold met                      (cost of being strict)

"not met" = not_met or insufficient: anything not confirmed is not counted as met.
"""

from collections import Counter, defaultdict

from pydantic import BaseModel

from app.evals.dataset import GoldRequirement
from app.pipeline.schemas import Evidence
from app.pipeline.span import normalize, quote_in_source


def quote_matches_gold(quote: str, gold: GoldRequirement, resume: str) -> bool:
    if not quote or not quote_in_source(quote, resume):
        return False
    q = normalize(quote)
    return any((q in normalize(g)) or (normalize(g) in q) for g in gold.evidence)


def outcome(gold: GoldRequirement, pred: Evidence, resume: str) -> str:
    if pred.verdict == "met":
        if gold.gold == "not_met":
            return "false_met"
        return "correct_met" if quote_matches_gold(pred.resume_quote, gold, resume) else "met_bad_quote"
    return "missed_met" if gold.gold == "met" else "correct_not"


class ItemResult(BaseModel):
    case_id: str
    requirement: str
    tags: list[str]
    gold: str
    verdict: str
    quote: str
    quote_exists: bool
    outcome: str
    notes: list[str]


class Summary(BaseModel):
    items: int
    predicted_met: int
    unsupported_met_rate: float  # predicted met whose quote is not valid proof (headline)
    fabricated_quote_rate: float  # predicted met whose quote is not in the resume at all
    false_met_rate: float  # gold not_met predicted as met
    met_recall: float  # gold met predicted met with a valid quote
    verdict_accuracy: float  # met vs not-met, ignoring quotes
    false_met_by_tag: dict[str, str]
    outcomes: dict[str, int]


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def summarize(results: list[ItemResult]) -> Summary:
    out = Counter(r.outcome for r in results)
    pred_met = [r for r in results if r.verdict == "met"]
    gold_met = sum(r.gold == "met" for r in results)
    gold_not = len(results) - gold_met

    tag_total: dict[str, int] = defaultdict(int)
    tag_false: dict[str, int] = defaultdict(int)
    for r in results:
        if r.gold == "not_met":
            for t in r.tags:
                tag_total[t] += 1
                tag_false[t] += r.outcome == "false_met"

    return Summary(
        items=len(results),
        predicted_met=len(pred_met),
        unsupported_met_rate=_rate(sum(r.outcome != "correct_met" for r in pred_met), len(pred_met)),
        fabricated_quote_rate=_rate(sum(not r.quote_exists for r in pred_met), len(pred_met)),
        false_met_rate=_rate(out["false_met"], gold_not),
        met_recall=_rate(out["correct_met"], gold_met),
        verdict_accuracy=_rate(out["correct_met"] + out["met_bad_quote"] + out["correct_not"], len(results)),
        false_met_by_tag={t: f"{tag_false[t]}/{n}" for t, n in sorted(tag_total.items())},
        outcomes=dict(out),
    )
