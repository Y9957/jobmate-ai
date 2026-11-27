from app.evals.dataset import GoldRequirement
from app.evals.metrics import ItemResult, outcome, summarize
from app.pipeline.schemas import Evidence

RESUME = "가상 이력서\n- PostgreSQL 인덱스를 설계해 쿼리를 개선했습니다.\nSQL, Python"
GOLD_MET = GoldRequirement(
    text="SQL 작성 능력",
    type="required",
    gold="met",
    tags=["paraphrase"],
    evidence=["PostgreSQL 인덱스를 설계해 쿼리를 개선했습니다.", "SQL, Python"],
)
GOLD_NOT = GoldRequirement(text="Kafka 사용 경험", type="preferred", gold="not_met", tags=["absent"])


def pred(verdict, quote=""):
    return Evidence(
        requirement_id=1,
        requirement="x",
        requirement_type="required",
        job_quote="x",
        job_quote_verified=True,
        verdict=verdict,
        resume_quote=quote,
    )


def test_outcomes():
    assert outcome(GOLD_MET, pred("met", "PostgreSQL 인덱스를 설계해 쿼리를 개선했습니다."), RESUME) == "correct_met"
    assert outcome(GOLD_MET, pred("met", "SQL"), RESUME) == "correct_met"  # part of a labelled line
    assert outcome(GOLD_MET, pred("met", "SQL을 3년간 사용했습니다."), RESUME) == "met_bad_quote"  # invented
    assert outcome(GOLD_MET, pred("met", ""), RESUME) == "met_bad_quote"
    assert outcome(GOLD_MET, pred("insufficient"), RESUME) == "missed_met"
    assert outcome(GOLD_NOT, pred("met", "SQL, Python"), RESUME) == "false_met"
    assert outcome(GOLD_NOT, pred("not_met"), RESUME) == "correct_not"


def _item(o, verdict, gold, exists=True, tags=("absent",)):
    return ItemResult(
        case_id="c",
        requirement="r",
        tags=list(tags),
        gold=gold,
        verdict=verdict,
        quote="q",
        quote_exists=exists,
        outcome=o,
        notes=[],
    )


def test_summary_rates():
    s = summarize(
        [
            _item("correct_met", "met", "met"),
            _item("met_bad_quote", "met", "met", exists=False),
            _item("false_met", "met", "not_met", tags=("adjacent_trap",)),
            _item("correct_not", "not_met", "not_met"),
            _item("missed_met", "insufficient", "met"),
        ]
    )
    assert s.predicted_met == 3
    assert s.unsupported_met_rate == round(2 / 3, 4)
    assert s.fabricated_quote_rate == round(1 / 3, 4)
    assert s.false_met_rate == 0.5
    assert s.met_recall == round(1 / 3, 4)
    assert s.verdict_accuracy == 0.6
    assert s.false_met_by_tag == {"absent": "0/1", "adjacent_trap": "1/1"}
