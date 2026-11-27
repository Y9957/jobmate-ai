"""PII masking applied before any text reaches a model or the database (docs/design.md §5)."""

import re

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    ("rrn", re.compile(r"\b\d{6}\s*-\s*[1-4]\d{6}\b"), "[RRN]"),  # 주민등록번호
    # 010-1234-5678, 02.123.4567, +82 10 1234 5678 (international form drops the leading 0)
    ("phone", re.compile(r"(?<![\d+])(?:\+82[\s-]?0?|0)\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{4}(?!\d)"), "[PHONE]"),
]


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace e-mail addresses, resident registration numbers and phone numbers.

    Names are not masked automatically: a name is not reliably detectable by pattern,
    so the UI asks the user to remove it (and public demos use synthetic resumes only).
    """
    counts: dict[str, int] = {}
    for kind, pattern, token in _PATTERNS:
        text, n = pattern.subn(token, text)
        if n:
            counts[kind] = n
    return text, counts
