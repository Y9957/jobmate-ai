"""Span Check: is the quoted text really in the source document?

This is deliberately plain code, not a model call. A model cannot be trusted to
verify its own quotations; a string comparison can. Only cosmetic differences are
forgiven (whitespace, line breaks, leading bullet marks, full-width characters).
"""

import re
import unicodedata

_BULLET = re.compile(r"^\s*(?:[-*•·▪◦‣○●■□]|\d+[.)])\s*")
_SPACE = re.compile(r"\s+")


def _clean_line(line: str) -> str:
    return _SPACE.sub(" ", _BULLET.sub("", line)).strip()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return " ".join(c for c in (_clean_line(line) for line in text.splitlines()) if c)


def quote_in_source(quote: str, source: str) -> bool:
    q = normalize(quote)
    return bool(q) and q in normalize(source)


def source_context(quote: str, source: str) -> str:
    """The source line(s) the quote came from, so a reviewer sees "Git" as part of a skills list.

    Falls back to the quote itself when it spans several lines or cannot be located.
    """
    q = normalize(quote)
    if not q:
        return ""
    lines = [c for c in (_clean_line(unicodedata.normalize("NFKC", raw)) for raw in source.splitlines()) if c]
    for i, line in enumerate(lines):
        if q in line:
            heading = next((lines[j] for j in range(i - 1, -1, -1) if lines[j].startswith("[")), "")
            return f"{heading} {line}".strip() if heading and heading != line else line
    return q
