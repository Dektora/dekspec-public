"""Root-anchored, folder-local patterns (ADR-068).

This leaf can be copied independently of the converter. Its only non-stdlib
import is the existing brace expander, which standalone callers can supply.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable, Iterator
from functools import lru_cache

from dekspec.glob_braces import expand_braces


def tokens(pattern: str) -> Iterator[tuple[str, str]]:
    """Tokenize fnmatch classes, including initial ] and unmatched [."""
    i = 0
    while i < len(pattern):
        start = i
        char = pattern[i]
        i += 1
        if char == "[":
            end = i + (pattern[i:i + 1] == "!")
            end += pattern[end:end + 1] == "]"
            while end < len(pattern) and pattern[end] != "]":
                end += 1
            if end < len(pattern):
                i = end + 1
                yield "class", pattern[start:i]
                continue
        if char == "*":
            while i < len(pattern) and pattern[i] == "*":
                i += 1
            yield "star", pattern[start:i]
        else:
            yield ("one" if char == "?" else "literal"), char


def class_expression(token: str, *, local: bool) -> str:
    # translate is used on ONE class, never a star-containing expression, so
    # fnmatch's atomic-group optimization cannot enter the proof language.
    body = fnmatch.translate(token)[4:-3]  # strip (?s: ... )\Z (or )\z)
    return ("(?!/)" if local else "") + body


def expression(pattern: str) -> str:
    """Regex body of one normalized, brace-expanded new-dialect pattern."""
    if pattern.endswith("/"):
        pattern += "**"
    parts = list(tokens(pattern))
    out = []
    i = 0
    while i < len(parts):
        kind, value = parts[i]
        if kind == "star":
            whole = value == "**" and (i == 0 or parts[i - 1] == ("literal", "/"))
            whole = whole and (i + 1 == len(parts) or parts[i + 1] == ("literal", "/"))
            if whole and i + 1 < len(parts):
                out.append("(?:[^/]+/)*")
                i += 1
            else:
                out.append(".*" if whole else "[^/]*")
        elif kind == "one":
            out.append("[^/]")
        elif kind == "class":
            out.append(class_expression(value, local=True))
        else:
            out.append(re.escape(value))
        i += 1
    return "".join(out)


@lru_cache(maxsize=2048)
def _compile(pattern: str) -> re.Pattern[str]:
    alternatives = (expression(p.replace("\\", "/")) for p in expand_braces(pattern))
    return re.compile("(?:" + "|".join(alternatives) + ")", re.DOTALL)


def matches(path: str, pattern: str) -> bool:
    """Whether a repository-relative path matches one pattern, case-sensitively."""
    return _compile(pattern).fullmatch(path.replace("\\", "/")) is not None


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    """Whether any pattern admits the path; leading ! is an ordinary literal."""
    return any(matches(path, pattern) for pattern in patterns)
