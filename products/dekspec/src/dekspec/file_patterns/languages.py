"""Regular-language models and candidate synthesis for the frozen readings.

Synthesis is deliberately separate from proof: no rewrite rule, heuristic or
sample can authorize a returned conversion. convert proves the whole union.
"""

from __future__ import annotations

import fnmatch
import os
import re

from dekspec.glob_braces import expand_braces

from .automata import Comparison, ProofLimit
from .dialect import class_expression, expression, tokens
from .legacy import _glob_to_regex


def _new_expressions(patterns):
    return [expression(p.replace("\\", "/")) for pattern in patterns for p in expand_braces(pattern)]


def _fnmatch(pattern, *, segment=False):
    out = []
    for kind, value in tokens(pattern):
        if kind == "star":
            out.append("[^/]*" if segment else ".*")
        elif kind == "one":
            out.append("[^/]" if segment else ".")
        elif kind == "class":
            out.append(class_expression(value, local=segment))
        else:
            out.append("(?!)" if segment and value == "/" else re.escape(value))
    return "".join(out)


def _old_expressions(pattern, reading):
    if reading == "components":
        pattern = pattern.strip()
        return [_glob_to_regex(pattern).pattern[1:-1], re.escape(pattern)] if pattern else []
    if os.path.normcase("A") != "A" and reading == "archeology-exclude":
        raise ProofLimit("Archeology equivalence requires case-preserving fnmatch normalization")
    expanded = expand_braces(pattern) if reading == "brief" else [pattern]
    out = []
    for raw in expanded:
        p = raw.replace("\\", "/")
        if reading == "archeology-exclude" and p.endswith("/"):
            directory = p.rstrip("/")
            bare = directory[3:] if directory.startswith("**/") else directory
            if bare:
                out.append("(?:[^/]+/)*" + _fnmatch(bare, segment=True) + "(?:/.*)?")
            # The frozen matcher also accepts a segment literally equal to
            # bare, even when fnmatch interprets its brackets as a class.
            if bare and "/" not in bare:
                out.append("(?:[^/]+/)*" + re.escape(bare) + "(?:/.*)?")
            out.append(re.escape(directory) + "(?:/.*)?")
            continue
        out.append(_fnmatch(p))
        if p.startswith("**/"):
            out.append(_fnmatch(p[3:]))
        if reading == "brief":
            if p.endswith("/**") and p[:-3]:
                out.append(re.escape(p[:-3]) + "(?:/.*)?")
            collapsed = p.replace("**/", "")
            if collapsed != p:
                out.append(_fnmatch(collapsed))
    return out


def _literal(text):
    return "".join({"[": "[[]", "*": "[*]", "?": "[?]"}.get(c, c) for c in text)


def _product(prefixes, choices):
    result = list(dict.fromkeys(p + c for p in prefixes for c in choices))
    if len(result) > 256:
        raise ProofLimit("Candidate search exceeds 256 alternatives")
    return result


def _crossing_star(at_start, at_end, followed_slash):
    if at_start:
        return ["**" if at_end else "**/*"]
    if followed_slash:
        return ["*/**"]
    return ["*", "*/**" if at_end else "*/**/*"]


def _fnmatch_candidates(pattern):
    parts, result = list(tokens(pattern)), [""]
    for i, (kind, value) in enumerate(parts):
        choices = [value]
        if kind == "star":
            choices = _crossing_star(
                i == 0 or parts[i - 1] == ("literal", "/"),
                i + 1 == len(parts),
                i + 1 < len(parts) and parts[i + 1] == ("literal", "/"),
            )
        elif kind == "one" or kind == "class" and fnmatch.fnmatchcase("/", value):
            choices += ["/"]
        result = _product(result, choices)
    return result


def _component_candidates(pattern):
    result, i = [""], 0
    while i < len(pattern):
        char = pattern[i]
        if pattern[i:i + 3] == "**/":
            choices = ["**/"] if i == 0 or pattern[i - 1] == "/" else ["", "*/**/"]
            i += 3
        elif pattern[i:i + 2] == "**":
            choices = _crossing_star(i == 0 or pattern[i - 1] == "/", i + 2 == len(pattern), False)
            i += 2
        else:
            choices = [char if char in "*?" else _literal(char)]
            i += 1
        result = _product(result, choices)
    return result


def _candidates(pattern, reading):
    if reading == "components":
        return _component_candidates(pattern.strip())
    out = []
    for raw in expand_braces(pattern) if reading == "brief" else [pattern]:
        p = raw.replace("\\", "/")
        if reading == "archeology-exclude" and p.endswith("/"):
            directory = p.rstrip("/")
            bare = directory[3:] if directory.startswith("**/") else directory
            # A literal slash cannot occur in a segment. Bracket-class slashes
            # remain folder-local, as they were when matched against segments.
            if bare and not any(k == "literal" and v == "/" for k, v in tokens(bare)):
                out.extend(("**/" + bare, "**/" + bare + "/"))
            if bare and "/" not in bare:
                out.extend(("**/" + _literal(bare), "**/" + _literal(bare) + "/"))
            out.extend((_literal(directory), _literal(directory) + "/**"))
        else:
            out.extend(_fnmatch_candidates(p))
            if p.startswith("**/"):
                out.extend(_fnmatch_candidates(p[3:]))
            if reading == "brief":
                if p.endswith("/**") and p[:-3]:
                    out.extend((_literal(p[:-3]), _literal(p[:-3]) + "/**"))
                collapsed = p.replace("**/", "")
                if collapsed != p:
                    out.extend(_fnmatch_candidates(collapsed))
        if len(out) > 256:
            raise ProofLimit("Candidate search exceeds 256 alternatives")
    return list(dict.fromkeys(out))


def rewrite(pattern: str, reading: str) -> tuple[str, ...]:
    """The sole proof boundary: return an exact, nonempty, bounded rewrite.

    The original spelling wins whenever it is equivalent. Synthesis has no
    authority on its own: every successful result, including each reduction,
    is justified by full language equality in the O-9 universe.
    """
    proof = Comparison(_old_expressions(pattern, reading))
    if proof.equal([]):
        raise ProofLimit("The old pattern covers no path in the repository-relative universe")
    if proof.equal(_new_expressions([pattern])):
        return (pattern,)
    proposed = _candidates(pattern, reading)
    allowed = set(pattern) | set("*?/[]!{},")
    if any(set(p) - allowed for p in proposed):
        raise ProofLimit("An exact candidate needs characters forbidden by O-9")
    if not proof.equal(_new_expressions(proposed)):
        raise ProofLimit("No exact rewrite established; candidate union changes the old coverage")
    for p in tuple(proposed):
        reduced = proposed.copy()
        reduced.remove(p)
        if reduced and proof.equal(_new_expressions(reduced)):
            proposed = reduced
    if not 1 <= len(proposed) <= 8:
        raise ProofLimit(f"Exact rewrite needs {len(proposed)} patterns; the limit is eight")
    return tuple(proposed)
