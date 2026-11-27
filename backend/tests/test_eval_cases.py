"""Integrity of the hand-labelled evaluation set (evals/cases). Catches labelling mistakes, not model mistakes."""

from collections import Counter

import pytest

from app.evals.dataset import load_cases
from app.pipeline.privacy import mask_pii
from app.pipeline.span import quote_in_source

CASES = load_cases()


def test_dataset_is_not_empty():
    assert len(CASES) >= 12
    assert sum(len(c.requirements) for c in CASES) >= 60


def test_case_ids_are_unique():
    assert len({c.case_id for c in CASES}) == len(CASES)


def test_every_split_is_present_and_test_is_big_enough():
    by_split = Counter(c.split for c in CASES)
    assert set(by_split) == {"easy", "dev", "test"}
    assert by_split["test"] >= 5
    assert sum(len(c.requirements) for c in CASES if c.split == "test") >= 40


def test_new_hard_tags_are_always_not_met():
    for c in CASES:
        for r in c.requirements:
            if {"weak_mention", "negation", "level_short"} & set(r.tags):
                assert r.gold == "not_met", f"{c.case_id} / {r.text}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_evidence_line_is_really_in_the_resume(case):
    for r in case.requirements:
        for line in r.evidence:
            assert quote_in_source(line, case.resume), f"{case.case_id} / {r.text}: {line!r}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_met_has_evidence_and_not_met_has_none(case):
    for r in case.requirements:
        assert bool(r.evidence) == (r.gold == "met"), f"{case.case_id} / {r.text}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_resumes_are_synthetic_and_contain_no_contact_details(case):
    assert "가상" in case.resume
    assert mask_pii(case.resume)[1] == {}


def test_dataset_is_balanced_enough():
    gold = Counter(r.gold for c in CASES for r in c.requirements)
    tags = Counter(t for c in CASES for r in c.requirements for t in r.tags)
    assert gold["met"] >= 25 and gold["not_met"] >= 25
    for tag in ("direct", "paraphrase", "absent", "adjacent_trap", "years", "degree"):
        assert tags[tag] >= 3, tag
