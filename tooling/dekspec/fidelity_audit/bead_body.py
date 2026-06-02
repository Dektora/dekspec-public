"""Bead-body convention parser (ds-d0as / Phase 1.B-B).

Beads under `.beads/issues.jsonl` (br tracker, beads-rust) carry markdown
bodies in their `description` field. The Phase 1.B convention (synthesized
from the dekfactory dark-execution review, 2026-05-28) introduces two
optional markdown lines authors can include in any bead body:

    failure_class: <one of the recommended values>
    failure_notes: <free-form text>

The convention is body-only — no beads-rust schema change required.
This parser is the canonical extractor: a single regex pass over each
bead's description field yields a list of `{bead_id, failure_class,
failure_notes}` records. Downstream audit rules (e.g.
T-BEAD-FAILURE-CLASS-VALID in sub-bead D) consume the output to surface
P3 advisories for unrecognized `failure_class` values without raising
hard failures.

Open-enum + lint-on-boundary (Fowler): the parser does NOT validate
`failure_class` against the recommended vocabulary. That's the audit
rule's job. The parser's job is mechanical extraction only.

Recommended `failure_class` vocabulary:
    wrong-spec | correlated-AI-miss | production-only-failure |
    flaky-test-masked-bug | scope-creep-undetected |
    dependency-version-conflict | concurrency-race | other
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Match a leading-line `failure_class:` or `failure_notes:` (case-insensitive,
# anchored to start-of-line via the multiline flag). Captures the rest of the
# line, then strips wrapping whitespace and surrounding backticks. The pattern
# rejects continuation lines (it requires the keyword at column 0) so a
# narrative line like "the failure_class was wrong-spec" inside prose does NOT
# match.
_FAILURE_CLASS_RE = re.compile(
    r"^failure_class:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
_FAILURE_NOTES_RE = re.compile(
    r"^failure_notes:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)


@dataclass
class BeadFailureClassRecord:
    """One bead's extracted failure_class + failure_notes (if present)."""

    bead_id: str
    failure_class: str | None
    failure_notes: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bead_id": self.bead_id,
            "failure_class": self.failure_class,
            "failure_notes": self.failure_notes,
        }


def _strip_value(raw: str) -> str:
    """Strip wrapping whitespace + a single pair of surrounding backticks."""
    s = raw.strip()
    if s.startswith("`") and s.endswith("`") and len(s) >= 2:
        s = s[1:-1].strip()
    return s


def extract_from_body(description: str) -> tuple[str | None, str | None]:
    """Extract (failure_class, failure_notes) from one bead description body.

    Returns (None, None) when neither line is present. When multiple matches
    appear (unusual — typically a single body has at most one of each), the
    FIRST match wins; downstream audit can flag duplicates if needed.
    """
    if not description:
        return None, None
    fc_match = _FAILURE_CLASS_RE.search(description)
    fn_match = _FAILURE_NOTES_RE.search(description)
    fc = _strip_value(fc_match.group(1)) if fc_match else None
    fn = _strip_value(fn_match.group(1)) if fn_match else None
    return (fc or None), (fn or None)


def parse_bead_failure_class(
    jsonl_path: str | Path,
) -> list[BeadFailureClassRecord]:
    """Walk `.beads/issues.jsonl` and return one record per bead that carries
    a `failure_class:` and/or `failure_notes:` line in its description body.

    Beads with neither line are OMITTED from the result (the caller wants
    only beads with classification signal). To get every bead regardless of
    classification, use `parse_bead_failure_class_all`.

    Returns an empty list when the file is absent or empty. Malformed JSONL
    lines are skipped silently (bead trackers occasionally emit blank lines
    or partial appends mid-write); the parser is tolerant by design.
    """
    return [
        rec
        for rec in parse_bead_failure_class_all(jsonl_path)
        if rec.failure_class is not None or rec.failure_notes is not None
    ]


def parse_bead_failure_class_all(
    jsonl_path: str | Path,
) -> list[BeadFailureClassRecord]:
    """Walk every bead in the JSONL file, returning one record per bead even
    when neither classification line is present.

    Useful for audit rules that need to count beads (denominator) alongside
    classified beads (numerator). Most callers want
    `parse_bead_failure_class` instead.
    """
    p = Path(jsonl_path)
    if not p.exists():
        return []

    records: list[BeadFailureClassRecord] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        bead_id = str(obj.get("id") or "").strip()
        if not bead_id:
            continue
        description = str(obj.get("description") or "")
        fc, fn = extract_from_body(description)
        records.append(
            BeadFailureClassRecord(
                bead_id=bead_id, failure_class=fc, failure_notes=fn
            )
        )
    return records


__all__ = [
    "BeadFailureClassRecord",
    "extract_from_body",
    "parse_bead_failure_class",
    "parse_bead_failure_class_all",
]
