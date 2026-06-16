#!/usr/bin/env python3
"""Deterministic glossary-term candidate extraction for /write-ggc.

This is the no-auto-write extraction capture stage for the write-ggc skill
(INT-166). It assembles glossary-term candidates from a supplied corpus and
returns a per-candidate 3-way disposition. It NEVER writes
`dekspec/domain-glossary.md` and NEVER calls `--add-term`; it only PROPOSES.
The two existing writers (`--add-term`, `--log`, both driven by `ggc_ops.py`)
remain the only glossary mutators -- this stage routes INTO them.

3-way disposition (per candidate):

  canonical-now  A de-facto term, used consistently with no conflicting senses,
                 not already covered by the glossary. Routed to the `--add-term`
                 path: the returned payload is an `--add-term` handoff the
                 engineer confirms.  route="--add-term".

  ambiguous      A term used with conflicting / overloaded senses in the corpus.
                 It must NOT be promoted as a single canonical term; it earns
                 promotion only via the existing 3-recurrence `--log` pipeline.
                 Routed to the `--log` path as a g&c correction seed.
                 route="--log".

  drop           Noise -- low-frequency, stopword-dominated, or already in the
                 glossary. Discarded. route=None.

Corpus boundary (pinned at INT-166 --decompose):
  IN  = the supplied conversation text + governed-artifact files under
        dekspec/{architecture-elements,intents,missions,adrs,working-specs,
        interface-contracts,impl-briefs}/
  OUT = source code, tooling/**, plugins/** code, and code comments.
The corpus is accepted as an input PARAMETER so the caller (and the outcome
test) controls exactly what is scanned; this module never walks the tree on its
own and never reads source code.

Deterministic: identical corpus + glossary input yields identical output.
Stdlib-only. Importable + argparse CLI, matching `ggc_ops.py`.

Exit codes: 0 = success; 1 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Governed-artifact folders that make up the IN side of the corpus boundary.
# Exposed so the skill prose / CLI can enumerate the pinned set; source code,
# tooling/**, and plugins/** code are intentionally excluded (OUT side).
CORPUS_FOLDERS: tuple[str, ...] = (
    "dekspec/architecture-elements/",
    "dekspec/intents/",
    "dekspec/missions/",
    "dekspec/adrs/",
    "dekspec/working-specs/",
    "dekspec/interface-contracts/",
    "dekspec/impl-briefs/",
)

# A candidate must recur at least this many times to count as a de-facto term
# rather than a one-off mention.
_MIN_FREQUENCY = 2

# Phrases that signal a term is used with conflicting / overloaded senses in the
# surrounding text -> route to `ambiguous` (--log), never canonical-now. Matched
# on word boundaries so "unambiguous" does NOT trip "ambiguous".
_AMBIGUITY_MARKERS: tuple[str, ...] = (
    r"ambiguous",
    r"overloaded",
    r"conflicts?",
    r"conflicting",
    r"two senses",
    r"different meanings?",
)
_AMBIGUITY_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(_AMBIGUITY_MARKERS) + r")(?![a-z])"
)

_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can could did do does for from had has have
    here how if in into is it its means no not of on one or other over should so
    some such that the their them then there these they this those to two up was
    we were what when where which while who will with would you your nothing else
    note happened over lazy quick brown fox jumped dog
    """.split()
)


def _glossary_terms(glossary_path: Path | None) -> set[str]:
    """Lowercased terms already present in the glossary (drop-list)."""
    if glossary_path is None or not Path(glossary_path).is_file():
        return set()
    terms: set[str] = set()
    for line in Path(glossary_path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s.startswith("|") or set(s) <= {"|", "-", ":", " "}:
            continue
        cells = [c.strip(" *") for c in s.strip("|").split("|")]
        if not cells or cells[0].lower() in {"term", "constraint", "rule"}:
            continue
        terms.add(cells[0].lower())
    return terms


def _candidate_phrases(corpus: str) -> dict[str, int]:
    """Frequency map of candidate phrases (bigrams + salient unigrams).

    Deterministic: sorted iteration, stable counting. Bigrams of two non-stop
    words capture multi-word domain terms ("shadow timeline"); standalone
    non-stop unigrams capture single-word terms ("assembly").
    """
    tokens = re.findall(r"[a-z][a-z0-9_]+", corpus.lower())
    freqs: dict[str, int] = {}

    # Bigrams: two adjacent non-stopword tokens.
    for a, b in zip(tokens, tokens[1:]):
        if a in _STOPWORDS or b in _STOPWORDS:
            continue
        if len(a) < 3 or len(b) < 3:
            continue
        phrase = f"{a} {b}"
        freqs[phrase] = freqs.get(phrase, 0) + 1

    # Unigrams: standalone non-stopword tokens.
    for t in tokens:
        if t in _STOPWORDS or len(t) < 4:
            continue
        freqs[t] = freqs.get(t, 0) + 1

    return freqs


def _is_ambiguous(candidate: str, corpus: str) -> bool:
    """True when the corpus uses `candidate` with conflicting/overloaded senses.

    Heuristic, deterministic: looks for an ambiguity marker (matched on word
    boundaries, so "unambiguous" never trips "ambiguous") within a tight window
    around occurrences of the FULL candidate phrase. The window is narrow enough
    that a marker attached to a neighbouring term does not bleed onto this one.
    """
    low = corpus.lower()
    pat = re.compile(r"(?<![a-z])" + re.escape(candidate) + r"(?![a-z])")
    found = False
    for m in pat.finditer(low):
        found = True
        window = low[max(0, m.start() - 60): m.end() + 60]
        if _AMBIGUITY_RE.search(window):
            return True
    if found:
        return False
    # Fall back to the candidate's head word when the full phrase never occurs
    # contiguously (e.g. a unigram absorbed from a bigram context).
    head = candidate.split()[0]
    for m in re.finditer(rf"(?<![a-z]){re.escape(head)}(?![a-z])", low):
        window = low[max(0, m.start() - 60): m.end() + 60]
        if _AMBIGUITY_RE.search(window):
            return True
    return False


def _addterm_payload(candidate: str) -> dict[str, str]:
    """An --add-term handoff payload (engineer confirms before any write)."""
    return {
        "term": candidate,
        "code_convention": candidate.replace(" ", "_"),
        "note": (
            "PROPOSED only -- run `/write-ggc --add-term` to confirm; "
            "this stage never writes the glossary."
        ),
    }


def _log_seed(candidate: str) -> dict[str, str]:
    """A --log correction seed for an overloaded/ambiguous term."""
    return {
        "term": candidate,
        "note": (
            f"'{candidate}' is used with conflicting senses; seed a "
            "`/write-ggc --log` correction -- it earns promotion only via the "
            "existing 3-recurrence pipeline, never directly."
        ),
    }


def extract_candidates(
    corpus: str,
    glossary_path: Path | str | None = None,
) -> dict[str, dict[str, object]]:
    """Propose a 3-way disposition for each glossary-term candidate in `corpus`.

    Returns a mapping `candidate -> {disposition, route, payload}` where
    disposition is one of `canonical-now` / `ambiguous` / `drop`. NEVER writes
    the glossary. `glossary_path` (if given) is read only to drop candidates the
    glossary already covers; it is never mutated.
    """
    gpath = Path(glossary_path) if glossary_path is not None else None
    known = _glossary_terms(gpath)
    freqs = _candidate_phrases(corpus)

    # Prefer multi-word phrases: if a bigram is a de-facto term, suppress its
    # component unigrams so "shadow timeline" wins over "shadow"/"timeline".
    phrase_words: set[str] = set()
    for phrase, n in freqs.items():
        if " " in phrase and n >= _MIN_FREQUENCY:
            phrase_words.update(phrase.split())

    result: dict[str, dict[str, object]] = {}
    for candidate in sorted(freqs):  # sorted -> deterministic output ordering
        n = freqs[candidate]

        if " " not in candidate and candidate in phrase_words:
            continue  # absorbed into a multi-word phrase

        if candidate in known or any(candidate in k for k in known):
            disposition, route, payload = "drop", None, None
        elif n < _MIN_FREQUENCY:
            disposition, route, payload = "drop", None, None
        elif _is_ambiguous(candidate, corpus):
            disposition, route, payload = "ambiguous", "--log", _log_seed(candidate)
        else:
            disposition = "canonical-now"
            route = "--add-term"
            payload = _addterm_payload(candidate)

        result[candidate] = {
            "disposition": disposition,
            "route": route,
            "payload": payload,
            "frequency": n,
        }

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_candidates.py",
        description=(
            "Propose 3-way glossary-term dispositions from a corpus. "
            "PROPOSES only -- never writes the glossary."
        ),
    )
    parser.add_argument(
        "corpus",
        nargs="?",
        help="Corpus text, or '-' / omitted to read from stdin.",
    )
    parser.add_argument(
        "--glossary",
        default="dekspec/domain-glossary.md",
        help="Glossary path (read-only drop-list; never written).",
    )
    args = parser.parse_args(argv)

    if args.corpus and args.corpus != "-":
        corpus = args.corpus
    else:
        corpus = sys.stdin.read()

    gpath = Path(args.glossary) if args.glossary else None
    result = extract_candidates(corpus, glossary_path=gpath)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
