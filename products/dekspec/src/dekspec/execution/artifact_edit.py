"""The only edits the execution engine makes to governed artifacts.

A status decision (authorize, complete) is written back to the artifact as a
single status change plus one Amendment Log row naming the evidence. Nothing
else in a governed artifact is ever rewritten by the engine.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

__all__ = ["ArtifactEditError", "append_amendment_row", "set_status"]

_META_STATUS = re.compile(r"^(\*\*Status:\*\*\s*)(\S+)(.*)$", re.MULTILINE)
_H2_STATUS = re.compile(r"(^##\s+Status\s*\n+)([A-Za-z_]+)", re.MULTILINE)


class ArtifactEditError(RuntimeError):
    pass


def set_status(path: Path, expected: set[str], new_status: str, *, author: str, change: str) -> str:
    """Flip the artifact's status from one of ``expected`` to ``new_status``
    and append an Amendment Log row. Returns the previous status."""
    text = path.read_text(encoding="utf-8")
    m = _META_STATUS.search(text)
    if m:
        previous = m.group(2).strip("`*_").upper()
        replace = lambda t: _META_STATUS.sub(lambda mm: mm.group(1) + new_status + mm.group(3), t, count=1)  # noqa: E731
    else:
        m2 = _H2_STATUS.search(text)
        if not m2:
            raise ArtifactEditError(f"{path.name}: no Status to update")
        previous = m2.group(2).upper()
        replace = lambda t: _H2_STATUS.sub(lambda mm: mm.group(1) + new_status, t, count=1)  # noqa: E731
    if previous not in expected:
        raise ArtifactEditError(
            f"{path.name}: status is {previous}; expected one of {', '.join(sorted(expected))}"
        )
    text = append_amendment_row(replace(text), f"| {date.today().isoformat()} | Substantive | {change} | {author} |")
    path.write_text(text, encoding="utf-8")
    return previous


def append_amendment_row(text: str, row: str) -> str:
    """Pure: return ``text`` with ``row`` appended to its Amendment Log table
    (creating the section when absent)."""
    if re.search(r"^## Amendment Log\s*$", text, re.MULTILINE):
        lines = text.rstrip("\n").split("\n")
        start = next(i for i, ln in enumerate(lines) if re.match(r"^## Amendment Log\s*$", ln))
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        table_rows = [i for i in range(start, end) if lines[i].startswith("|")]
        if table_rows:
            lines.insert(table_rows[-1] + 1, row)
        else:
            lines[end:end] = ["", "| Date | Type | Change | Author |", "|------|------|--------|--------|", row]
        text = "\n".join(lines) + "\n"
    else:
        text = text.rstrip("\n") + (
            "\n\n## Amendment Log\n\n| Date | Type | Change | Author |\n"
            "|------|------|--------|--------|\n" + row + "\n"
        )
    return text
