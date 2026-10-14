"""Confidence-scored classification report emitter for `dekspec ingest`.

This module renders the classification report — the human-review surface of
the brownfield-ingest command (INT-059 / IB-098). The report names, for every
source section: the section heading text, the classified IR type, the
classifier's confidence score, the firing signals, and (for sections that
became draft artifacts) the staging-directory file the draft was written to.

The report data is *shaped once* (`shape_report`) into a list of per-section
rows plus summary counts. Two renderers then format that shaped data:

  * `render_markdown` — a human-readable Markdown table (the default).
  * `render_json` — a JSON-serializable dict (the `--json` path).

Both renderers operate on the same shaped data, so the Markdown and JSON
outputs always agree on the underlying per-section facts. The Markdown vs JSON
choice is a pure formatting switch, mirroring the existing
`dekspec audit linkage --json` formatter split in `cli.py`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .classifier import Classification, IRKind

# Confidence is rendered at a fixed decimal precision so report output is
# stable across runs (the classifier already clamps it to [0.0, 1.0]).
_CONFIDENCE_PRECISION = 2


@dataclass(frozen=True)
class ReportRow:
    """One per-source-section row of the classification report."""

    order: int
    heading: str
    ir_kind: str
    confidence: float
    signals: tuple[str, ...]
    artifact_file: str | None
    """Relative staging-directory filename the draft was written to, or
    `None` for an `UNCLASSIFIED` section (which is not emitted as a draft)."""


@dataclass(frozen=True)
class ReportData:
    """The shaped classification report — rows plus summary counts.

    Both renderers (`render_markdown`, `render_json`) consume this; they never
    re-derive facts from raw `Classification` objects, so the two outputs
    cannot disagree on the underlying data.
    """

    rows: tuple[ReportRow, ...]
    counts: dict[str, int]
    """Per-IR-kind section counts plus a `total` and `emitted` tally."""


def shape_report(
    classifications: list[Classification],
    artifact_files: dict[int, str] | None = None,
) -> ReportData:
    """Shape a list of `Classification` into the report data structure.

    `artifact_files` maps a section's `order` to the relative staging-directory
    filename of the draft artifact emitted for it (the runner supplies this).
    A section absent from the map (e.g. `UNCLASSIFIED`) has `artifact_file` of
    `None` — it appears in the report but produced no draft.
    """
    files = artifact_files or {}
    rows: list[ReportRow] = []
    counts: dict[str, int] = {kind.name: 0 for kind in IRKind}
    counts["total"] = 0
    counts["emitted"] = 0

    for clf in classifications:
        rows.append(
            ReportRow(
                order=clf.section.order,
                heading=clf.section.heading,
                ir_kind=clf.ir_kind.name,
                confidence=round(clf.confidence, _CONFIDENCE_PRECISION),
                signals=tuple(clf.signals),
                artifact_file=files.get(clf.section.order),
            )
        )
        counts[clf.ir_kind.name] += 1
        counts["total"] += 1
        if files.get(clf.section.order) is not None:
            counts["emitted"] += 1

    return ReportData(rows=tuple(rows), counts=counts)


def _heading_label(heading: str) -> str:
    """Render an empty heading (the pre-heading preamble) readably."""
    return heading if heading else "(preamble)"


def render_markdown(data: ReportData) -> str:
    """Render the shaped report as a human-readable Markdown document.

    This is the default `dekspec ingest` report format and the content of the
    report file written into the staging directory.
    """
    lines: list[str] = []
    lines.append("# DekSpec ingest — classification report")
    lines.append("")
    lines.append(
        f"Sections classified: {data.counts['total']}  |  "
        f"Draft artifacts emitted: {data.counts['emitted']}"
    )
    lines.append("")
    lines.append("Every source section is listed below. Sections classified")
    lines.append("`UNCLASSIFIED` produced no draft artifact — review them by hand.")
    lines.append("")
    lines.append("| # | Source heading | IR type | Confidence | Draft file | Signals |")
    lines.append("|---|----------------|---------|-----------:|------------|---------|")
    for row in data.rows:
        signals = "; ".join(row.signals) if row.signals else "—"
        artifact = row.artifact_file or "—"
        conf = f"{row.confidence:.{_CONFIDENCE_PRECISION}f}"
        heading = _heading_label(row.heading).replace("|", "\\|")
        signals = signals.replace("|", "\\|")
        lines.append(
            f"| {row.order} | {heading} | {row.ir_kind} | "
            f"{conf} | {artifact} | {signals} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _report_dict(data: ReportData) -> dict[str, object]:
    """The JSON-serializable shape — shared by `render_json` and the runner's
    structured result."""
    return {
        "summary": dict(sorted(data.counts.items())),
        "sections": [
            {
                "order": row.order,
                "heading": row.heading,
                "ir_kind": row.ir_kind,
                "confidence": row.confidence,
                "signals": list(row.signals),
                "artifact_file": row.artifact_file,
            }
            for row in data.rows
        ],
    }


def render_json(data: ReportData) -> str:
    """Render the shaped report as a JSON document (the `--json` path).

    The per-section fields — heading, IR type, confidence, signals — are the
    same facts `render_markdown` shows; only the formatting differs.
    """
    return json.dumps(_report_dict(data), indent=2) + "\n"
