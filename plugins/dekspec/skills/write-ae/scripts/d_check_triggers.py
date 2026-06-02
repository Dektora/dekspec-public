#!/usr/bin/env python3
"""Regex-based D-series trigger scan for the /write-ae Audit Mode.

The `/write-ae` Audit Mode runs a D-series (D1-D18) drift checklist. A subset of
those checks have purely mechanical *triggers* — fixed regex patterns or phrase
lists — and only the true-vs-false-positive judgment is left to the model. This
script runs that mechanical subset and emits the candidate hits as JSON; the
skill's Audit Mode still decides which hits are genuine drift.

MECHANIZED here (pure-regex triggers, no section context needed):
  D1   — fenced code blocks (``` outside the amendment-log table)
  D2   — math markers: LaTeX `\\(` / `\\[` / `$$`, inline `$...$`
  D3   — function/class names: backticked `name()`, prose `def`/`class`,
         CamelCase regex, ALL_CAPS module-constant regex, library-call
         blacklist prefixes, HuggingFace model-path pattern
  D6   — number-with-unit / dimensionless-number paired with a hedge word
  D13  — mirror-for-reader-convenience phrase list
  D14  — audit-ruler / canonical-process subsection headers
  D15  — single-authoritative-reference overreach phrase list

NOT mechanized (need section scoping or genuine judgment — left to the model):
  D4   — "3+ step procedure": requires knowing the host section + list semantics.
  D5   — per-type dispatch enumerations: needs semantic read of branch contents.
  D7   — schema/dtype tables: column-header heuristic entangled with table intent.
  D8   — code-gap punch-lists: overlaps D16; needs Open-Issues classification.
  D9   — process-narrative in Amendment Log: needs entry-length + date grandfather.
  D10  — stale superseded text: trigger is section-scoped (positive-framing only).
  D11  — motivational Vision restatement: pure judgment, no mechanical trigger.
  D12  — capacity tables: header heuristic, but exemption is judgment-bound.
  D16  — Open-Issues spec-gap-vs-code-gap: classification is a judgment call.
  D17  — measurable targets: overlaps D6, but the WS-citation exemption is judgment.
  D18  — decision rationale: section-scoped phrase match, judgment on the exemption.

Stdlib-only by design: vendored into consumer repos where `dekspec` is not
guaranteed importable.

Runnable:   python d_check_triggers.py path/to/AE-NNN.md
Importable: from d_check_triggers import scan
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# D1 — fenced code blocks.
# --------------------------------------------------------------------------
_FENCE_RE = re.compile(r"^\s*```")

# --------------------------------------------------------------------------
# D2 — math markers + inline math.
# --------------------------------------------------------------------------
_MATH_MARKERS = (r"\(", r"\)", r"\[", r"\]", "$$")
_INLINE_MATH_RE = re.compile(r"(?<!\$)\$(?!\$)[^$\n]+\$(?!\$)")

# --------------------------------------------------------------------------
# D3 — function / class / callable names + library-call blacklist.
# --------------------------------------------------------------------------
_BACKTICK_CALL_RE = re.compile(r"`[^`\n]*\(\)[^`\n]*`")
_PROSE_DEFCLASS_RE = re.compile(r"\b(?:async\s+def|def|class)\s+[A-Za-z_]\w*")
_CAMELCASE_RE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+){1,}\b")
_ALLCAPS_RE = re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b")
_HF_PATH_RE = re.compile(r"\b[A-Za-z0-9_.]+/[A-Za-z0-9_.]+-[A-Za-z0-9_.]+-\d+bit\b")
_LIBRARY_PREFIXES = (
    "torch.",
    "numpy.",
    "asyncio.",
    "psycopg2",
    "psycopg3",
    "pymupdf4llm.",
    "tiktoken.",
    "transformers.",
    "huggingface_hub.",
)
# ALL_CAPS tokens that are not module constants — common English / acronyms /
# DekSpec status words. Keeps the D3 ALL_CAPS heuristic low-noise.
_ALLCAPS_ALLOW = {
    "TODO",
    "DRAFT",
    "PROPOSED",
    "ACCEPTED",
    "LOCKED",
    "DEPRECATED",
    "SUPERSEDED",
    "NOTE",
    "WARNING",
    "JSON",
    "YAML",
    "HTTP",
    "HTTPS",
    "CLI",
    "API",
    "ADR",
    "ADRS",
    "DEKSPEC",
}

# --------------------------------------------------------------------------
# D6 — tunable values: number + unit, or dimensionless number, near a hedge.
# --------------------------------------------------------------------------
_NUMBER_UNIT_RE = re.compile(
    r"\b\d[\d,.]*\s?(?:s|ms|MiB|GiB|GB|KB|tokens)\b"
)
_HEDGE_WORDS = (
    "currently",
    "typically",
    "roughly",
    "~",
    "seed default",
    "default",
    "in the near term",
    "tens of",
    "hundreds of",
    "low thousands",
)

# --------------------------------------------------------------------------
# D13 / D14 / D15 — phrase / header lists.
# --------------------------------------------------------------------------
_D13_PHRASES = (
    "mirrored here for reader convenience",
    "duplicate of",
    "repeated here from",
    "for completeness",
    "exact values mirrored from",
    "mirrored from adr-",
    "mirrored from ws-",
    "mirrored from dn-",
)
_D14_HEADERS = (
    "canonical process",
    "audit ruler",
    "canonical procedure",
    "canonical algorithm",
    "reference implementation",
    "authoritative specification",
    "authoritative procedure",
)
_D15_PHRASES = (
    "single authoritative reference",
    "the full contract",
    "exhaustive specification",
    "the complete definition of",
    "the behavioral contract for",
    "single source of truth for",
    "authoritative specification",
    "complete specification",
)

_HEADER_RE = re.compile(r"^#{2,6}\s+(.*)$")


def scan(text: str) -> dict[str, list[dict[str, object]]]:
    """Scan AE body text and return mechanical D-check trigger hits.

    Return shape: {rule: [{"line": int, "match": str}, ...]}. A rule key is
    present only when it has at least one hit. Line numbers are 1-based.
    """
    hits: dict[str, list[dict[str, object]]] = {}

    def add(rule: str, line: int, match: str) -> None:
        hits.setdefault(rule, []).append({"line": line, "match": match.strip()})

    lines = text.splitlines()
    in_fence = False
    fence_open_line = 0

    for idx, line in enumerate(lines, start=1):
        lower = line.lower()
        stripped = line.strip()

        # D1 — fenced code blocks. Toggle on every fence; flag the opener.
        if _FENCE_RE.match(line):
            if not in_fence:
                in_fence = True
                fence_open_line = idx
                add("D1", idx, stripped or "```")
            else:
                in_fence = False
            continue
        # Inside a fence, skip the other content scans (code is already flagged).
        if in_fence:
            continue

        # D2 — math markers + inline math.
        for marker in _MATH_MARKERS:
            if marker in line:
                add("D2", idx, marker)
                break
        for m in _INLINE_MATH_RE.finditer(line):
            add("D2", idx, m.group(0))

        # D3 — callable / class names + library calls.
        for m in _BACKTICK_CALL_RE.finditer(line):
            add("D3", idx, m.group(0))
        for m in _PROSE_DEFCLASS_RE.finditer(line):
            add("D3", idx, m.group(0))
        for m in _CAMELCASE_RE.finditer(line):
            add("D3", idx, m.group(0))
        for m in _ALLCAPS_RE.finditer(line):
            if m.group(0) not in _ALLCAPS_ALLOW:
                add("D3", idx, m.group(0))
        for m in _HF_PATH_RE.finditer(line):
            add("D3", idx, m.group(0))
        for prefix in _LIBRARY_PREFIXES:
            if prefix in line:
                add("D3", idx, prefix)

        # D6 — tunable values near a hedge.
        num_unit = _NUMBER_UNIT_RE.search(line)
        has_hedge = any(h in lower for h in _HEDGE_WORDS)
        if num_unit and has_hedge:
            add("D6", idx, num_unit.group(0))

        # D13 — mirror phrases.
        for phrase in _D13_PHRASES:
            if phrase in lower:
                add("D13", idx, phrase)

        # D14 — audit-ruler / canonical-process headers (header lines only).
        header_m = _HEADER_RE.match(line)
        if header_m:
            head_lower = header_m.group(1).lower()
            for phrase in _D14_HEADERS:
                if phrase in head_lower:
                    add("D14", idx, header_m.group(1).strip())

        # D15 — single-authoritative-reference overreach phrases.
        for phrase in _D15_PHRASES:
            if phrase in lower:
                add("D15", idx, phrase)

    # Unterminated fence — flag for the model.
    if in_fence:
        add("D1", fence_open_line, "unterminated ``` fence")

    return hits


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="d_check_triggers.py",
        description="Regex-based D-series trigger scan for /write-ae Audit Mode.",
    )
    p.add_argument("path", help="path to the Architecture Element markdown file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    hits = scan(text)
    print(json.dumps(hits, indent=2))
    # Exit 0 always: trigger hits are candidate findings, not the verdict —
    # the model judges true-vs-false positive. A non-zero exit would imply a
    # confirmed defect, which this script deliberately does not assert.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
