import pytest

from app.pipeline.privacy import mask_pii
from app.pipeline.span import normalize, quote_in_source, source_context

RESUME = """경력: 데이터 분석 인턴 6개월
- Python과 Pandas로 매출 데이터 20만 건을 정제했습니다.
• FastAPI로   사내 분석 API 3종을
  개발했습니다.
기술: Python, SQL, FastAPI"""


@pytest.mark.parametrize(
    "quote",
    [
        "Python과 Pandas로 매출 데이터 20만 건을 정제했습니다.",
        "- Python과 Pandas로 매출 데이터 20만 건을 정제했습니다.",  # bullet copied along
        "FastAPI로 사내 분석 API 3종을 개발했습니다.",  # spans a line break and extra spaces
        "Python, SQL, FastAPI",
        "Ｐｙｔｈｏｎ, SQL",  # full-width characters
    ],
)
def test_quote_found_despite_cosmetic_differences(quote):
    assert quote_in_source(quote, RESUME)


@pytest.mark.parametrize(
    "quote",
    [
        "Python과 Pandas로 매출 데이터 30만 건을 정제했습니다.",  # one digit changed
        "FastAPI로 사내 API를 개발했습니다.",  # paraphrased
        "Kubernetes 클러스터를 운영했습니다.",  # invented
        "",
        "   ",
    ],
)
def test_quote_rejected_when_not_verbatim(quote):
    assert not quote_in_source(quote, RESUME)


def test_source_context_includes_section_heading():
    resume = "[경력]\n- Git으로 협업했습니다.\n\n[기술]\nJava, Spring Boot, Git"
    assert source_context("Spring Boot", resume) == "[기술] Java, Spring Boot, Git"
    assert source_context("Git으로 협업했습니다.", resume) == "[경력] Git으로 협업했습니다."
    assert source_context("", resume) == ""


def test_normalize_drops_bullets_and_joins_lines():
    assert normalize("1) 첫째\n  • 둘째  줄") == "첫째 둘째 줄"


def test_mask_pii():
    text = "연락처 010-1234-5678 / +82 10 9876 5432, 메일 kim.dev+job@example.co.kr, 주민 900101-1234567"
    masked, counts = mask_pii(text)
    assert "010-1234-5678" not in masked and "example.co.kr" not in masked and "900101" not in masked
    assert counts == {"email": 1, "rrn": 1, "phone": 2}


def test_mask_pii_leaves_numbers_that_are_not_contacts():
    masked, counts = mask_pii("매출 데이터 200000건, 2025.01–2025.06")
    assert counts == {} and "200000" in masked
