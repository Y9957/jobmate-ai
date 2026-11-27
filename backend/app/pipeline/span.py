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
