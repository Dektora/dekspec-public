#!/usr/bin/env python3
"""Pre-save structural validation of a System Vision draft.

This script replaces the deterministic "validate structurally" step of the
`/write-sv` Fan-Out Mode (Step 3.2): it checks H1 form, the six required H2
sections, Status=DRAFT, and Created/Modified stamped to today. The skill keeps
the AI-judgment work (deciding whether to re-dispatch, summarising findings).

Each check is a named rule. The script emits the list of FAILING rule names to
stdout (one per line) and exits non-zero; empty stdout + exit 0 means the draft
passed every structural check.

Stdlib-only by design: vendored into consumer repos where the `dekspec` engine
is not guaranteed importable.

Runnable:   python validate_structure.py path/to/system-vision.md
Importable: from validate_structure import validate
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

# The six load-bearing System Vision sections. The preamble is the text
# between the H1 and the first H2; the rest are H2 headings.
_REQUIRED_H2 = (
    "What This Is",
    "Who This Is For",
    "Why This Exists",
    "What Success Looks Like",
    "What We Are Not Building",
)

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_BAD_H1_PREFIX = "Vision Note:"


def _h2_body(text: str, heading: str) -> str | None:
    """Return the body text under `## <heading>` up to the next H2, or None."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if m is None:
        return None
    return m.group(1).strip()


def _preamble(text: str) -> str:
    """Return the text between the first H1 and the first H2."""
    h1 = _H1_RE.search(text)
    if h1 is None:
        return ""
    after_h1 = text[h1.end():]
    next_h2 = re.search(r"^##\s", after_h1, re.MULTILINE)
    chunk = after_h1[: next_h2.start()] if next_h2 else after_h1
    return chunk.strip()


def _status_value(text: str) -> str | None:
    """Read the Status field — supports `## Status` section + `**Status:**` inline."""
    sect = _h2_body(text, "Status")
    if sect:
        return sect.splitlines()[0].strip()
    m = re.search(r"^\*\*Status:\*\*\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _date_field(text: str, name: str) -> str | None:
    """Read a date field — supports `## <Name>` section + `**<Name>:**` inline."""
    sect = _h2_body(text, name)
    if sect:
        return sect.splitlines()[0].strip()
    m = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def validate(text: str, *, today: str | None = None) -> list[str]:
    """Return the list of failing rule names. Empty list means the draft passes.

    Rules:
      H1_PRESENT      — a top-level `# ` heading exists.
      H1_FORM         — H1 does not use the rejected `# Vision Note:` prefix.
      PREAMBLE        — non-empty text between H1 and the first H2.
      SECTION_<name>  — each of the five required H2 sections present + non-empty.
      STATUS_DRAFT    — Status field reads exactly DRAFT.
      CREATED_TODAY   — Created stamp equals today (YYYY-MM-DD).
      MODIFIED_TODAY  — Modified stamp equals today (YYYY-MM-DD).
    """
    today = today or datetime.date.today().isoformat()
    failures: list[str] = []

    h1 = _H1_RE.search(text)
    if h1 is None:
        failures.append("H1_PRESENT")
    elif h1.group(1).startswith(_BAD_H1_PREFIX):
        failures.append("H1_FORM")

    if not _preamble(text):
        failures.append("PREAMBLE")

    for heading in _REQUIRED_H2:
        body = _h2_body(text, heading)
        if not body:
            rule = "SECTION_" + heading.upper().replace(" ", "_")
            failures.append(rule)

    if _status_value(text) != "DRAFT":
        failures.append("STATUS_DRAFT")

    if _date_field(text, "Created") != today:
        failures.append("CREATED_TODAY")
    if _date_field(text, "Modified") != today:
        failures.append("MODIFIED_TODAY")

    return failures


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate_structure.py",
        description="Pre-save structural validation of a System Vision draft.",
    )
    p.add_argument("path", help="path to the System Vision markdown file")
    p.add_argument(
        "--today",
        default=None,
        help="override today's date (YYYY-MM-DD) for date-stamp checks",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    failures = validate(text, today=args.today)
    if failures:
        for rule in failures:
            print(rule)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
