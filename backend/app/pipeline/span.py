"""Span Check: is the quoted text really in the source document?

This is deliberately plain code, not a model call. A model cannot be trusted to
verify its own quotations; a string comparison can. Only cosmetic differences are
forgiven (whitespace, line breaks, leading bullet marks, full-width characters).
"""

import re
import unicodedata
from difflib import SequenceMatcher

_BULLET = re.compile(r"^\s*(?:[-*•·▪◦‣○●■□]|\d+[.)])\s*")
_SPACE = re.compile(r"\s+")
# Separators a model uses when it glues a heading, company or date onto the quoted line
_GLUE = re.compile(r"\s+[-–—·•|:]\s+|\n")
MIN_REPAIR_CHARS = 8


def _clean_line(line: str) -> str:
    return _SPACE.sub(" ", _BULLET.sub("", line)).strip()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return " ".join(c for c in (_clean_line(line) for line in text.splitlines()) if c)


def quote_in_source(quote: str, source: str) -> bool:
    q = normalize(quote)
    return bool(q) and q in normalize(source)


def repair_quote(quote: str, source: str) -> str | None:
    """Return a verbatim quote, or None.

    If the quote is already in the source it is returned unchanged. Otherwise, when the
    model glued a heading or date onto a real line ("프로젝트명 · 2024.08 - 실제 문장"),
    the longest glued-together piece that exists verbatim in the source is returned.
    Nothing is ever invented or paraphrased: the result is always an exact substring.
    """
    if quote_in_source(quote, source):
        return quote
    pieces = [p.strip() for p in _GLUE.split(quote) if p and p.strip()]
    found = [p for p in pieces if len(normalize(p)) >= MIN_REPAIR_CHARS and quote_in_source(p, source)]
    return max(found, key=len) if found else None


def _lines(source: str) -> list[str]:
    return [c for c in (_clean_line(unicodedata.normalize("NFKC", raw)) for raw in source.splitlines()) if c]


def closest_line(quote: str, source: str, threshold: float = 0.45) -> str | None:
    """The resume line most similar to a quote that failed the check — shown to the model as a hint."""
    q = normalize(quote)
    if not q:
        return None
    scored = [(SequenceMatcher(None, q, line).ratio(), line) for line in _lines(source) if not line.startswith("[")]
    if not scored:
        return None
    best_score, best = max(scored)
    return best if best_score >= threshold else None


def source_context(quote: str, source: str) -> str:
    """The source line(s) the quote came from, so a reviewer sees "Git" as part of a skills list.

    Falls back to the quote itself when it spans several lines or cannot be located.
    """
    q = normalize(quote)
    if not q:
        return ""
    lines = _lines(source)
    for i, line in enumerate(lines):
        if q in line:
            heading = next((lines[j] for j in range(i - 1, -1, -1) if lines[j].startswith("[")), "")
            return f"{heading} {line}".strip() if heading and heading != line else line
    return q
