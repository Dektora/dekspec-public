"""`run` orchestration + draft-artifact writer for `dekspec ingest`.

This module is the orchestration entry point of INT-059's brownfield-ingest
command (IB-098). `run`:

  1. validates the input path is a markdown (`.md`) file — rejecting any other
     extension cleanly, since markdown is the only supported MVP input format
     (INT-059 OI-3; `docx` / `pdf` are deferred to a future Intent);
  2. reads the file as UTF-8 and runs IB-097's deterministic `classify`;
  3. resolves a *staging directory* — `out_dir`, or a fresh
     `./dekspec-ingest-<timestamp>/` — which is NEVER the consumer's live
     `dekspec/` tree (INT-059 OI-4);
  4. emits one draft DekSpec artifact per confidently-classified section group
     into the staging directory, each at status `DRAFT`;
  5. writes the confidence-scored classification report alongside the drafts;
  6. returns an `IngestResult` the CLI formats.

Every emitted artifact is an unpromoted *draft* — status `DRAFT`, never
`PROPOSED` or higher. The staging directory is a review area: the engineer
reviews the drafts against the report and copies the keepers into the real
`dekspec/` tree by hand. `run` writes nothing outside the staging directory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .classifier import Classification, IRKind, classify
from .report import ReportData, _report_dict, render_markdown, shape_report

# Markdown is the only supported MVP input format (INT-059 OI-3).
_MARKDOWN_SUFFIXES = {".md", ".markdown"}

# Placeholder artifact IDs for emitted drafts. They are deliberately high,
# obviously-not-real numbers — a reviewer promoting a draft allocates a
# canonical ID via `dekspec id allocate` and renames the file. The parsers
# accept any `<KIND>-NNN-*.md` filename, so these parse cleanly as drafts.
_PLACEHOLDER_ID = "900"

# Draft artifacts are emitted at DRAFT — a section confident enough to be
# emitted has been classified, so DRAFT (not TODO) is the honest status
# (IB-098 §Constraints "Draft-artifact emission" / OI-1).
_DRAFT_STATUS = "DRAFT"


class IngestError(Exception):
    """Raised on a usage error — a non-markdown input path, a missing input
    file, or a non-empty pre-existing staging directory. The CLI layer turns
    this into a non-zero exit with the message on stderr."""


@dataclass(frozen=True)
class IngestResult:
    """The structured outcome of an ingest run, for the CLI to format."""

    source_path: str
    staging_dir: str
    report: ReportData
    report_file: str
    """Relative filename of the classification report inside the staging dir."""

    artifact_files: tuple[str, ...]
    """Relative filenames of every draft artifact emitted into the staging dir."""


# --------------------------------------------------------------------------
# Draft-artifact emission — existing IR kinds in DRAFT shape
# --------------------------------------------------------------------------


def _slug(text: str) -> str:
    """Build a filesystem-safe, lower-cased slug from heading text."""
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_/" and (out and out[-1] != "-"):
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "section"


def _render_adr_draft(group: list[Classification]) -> tuple[str, str]:
    """Render one ADR draft from the ADR Context/Decision/Consequences sections.

    Returns `(filename, markdown)`. The emitted markdown carries the required
    headed sections of an ADR (`Status`, `Context and Decision Drivers`,
    `Decision`, `Consequences`) populated with the matching source bodies, so
    it parses cleanly through `parse_adr`.
    """
    by_kind = {clf.ir_kind: clf for clf in group}
    context = by_kind.get(IRKind.ADR_CONTEXT)
    decision = by_kind.get(IRKind.ADR_DECISION)
    consequences = by_kind.get(IRKind.ADR_CONSEQUENCES)

    title_src = decision or context or consequences
    title = title_src.section.heading if title_src else "Ingested decision"
    filename = f"ADR-{_PLACEHOLDER_ID}-{_slug(title)}.md"

    context_body = (
        context.section.body.strip()
        if context
        else "[Ingested draft — no Context section was classified. Fill in.]"
    )
    decision_body = (
        decision.section.body.strip()
        if decision
        else "[Ingested draft — no Decision section was classified. Fill in.]"
    )
    consequences_body = (
        consequences.section.body.strip()
        if consequences
        else "[Ingested draft — no Consequences section was classified.]"
    )

    md = f"""# ADR-{_PLACEHOLDER_ID}: {title}

## Status

{_DRAFT_STATUS}

*Ingested draft — allocate a canonical ID with `dekspec id allocate`, review
against the classification report, then promote via `/dekspec:write-adr`.*

## Context and Decision Drivers

{context_body}

## Decision

{decision_body}

## Consequences

{consequences_body}

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| {_today()} | Substantive | Draft emitted by `dekspec ingest`. | dekspec ingest |
"""
    return filename, md


def _render_ae_draft(clf: Classification) -> tuple[str, str]:
    """Render one AE draft from an AE-responsibility section.

    The emitted markdown carries `Status`, `Subtype`, and `Purpose and Scope`
    so it parses cleanly through `parse_ae` (which requires a `subtype`).
    """
    title = clf.section.heading or "Ingested component"
    filename = f"AE-{_PLACEHOLDER_ID}-{_slug(title)}.md"
    body = clf.section.body.strip() or "[Ingested draft — section body was empty.]"

    md = f"""# AE-{_PLACEHOLDER_ID}: {title}

## Status

{_DRAFT_STATUS}

*Ingested draft — allocate a canonical ID with `dekspec id allocate`, review
against the classification report, then promote via `/dekspec:write-ae`.*

## Subtype

component

*Ingest defaults the subtype to `component`; correct it during promotion.*

## Purpose and Scope

{body}

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| {_today()} | Substantive | Draft emitted by `dekspec ingest`. | dekspec ingest |
"""
    return filename, md


def _render_ws_draft(clf: Classification) -> tuple[str, str]:
    """Render one WS draft from a WS-business-rule section.

    The emitted markdown carries `Status` and the business-rule body so it
    parses cleanly through `parse_ws`.
    """
    title = clf.section.heading or "Ingested behavior"
    filename = f"WS-{_PLACEHOLDER_ID}-{_slug(title)}.md"
    body = clf.section.body.strip() or "[Ingested draft — section body was empty.]"

    md = f"""# Working Spec: {title}

## Status

{_DRAFT_STATUS}

*Ingested draft — allocate a canonical ID with `dekspec id allocate`, review
against the classification report, then promote via `/dekspec:write-ws`.*

## Business Rules

{body}

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| {_today()} | Substantive | Draft emitted by `dekspec ingest`. | dekspec ingest |
"""
    return filename, md


def _today() -> str:
    """Date stamp for emitted amendment-log rows (UTC, ISO date)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _plan_artifacts(
    classifications: list[Classification],
) -> list[tuple[str, str, list[int]]]:
    """Group classifications into draft artifacts.

    The three ADR slots (Context / Decision / Consequences) coalesce into one
    ADR draft; each AE-responsibility section becomes its own AE draft; each
    WS-business-rule section its own WS draft. `UNCLASSIFIED` sections become
    no artifact (they still appear in the report). Returns a list of
    `(filename, markdown, [contributing section orders])` — deterministic in
    source order.
    """
    adr_group = [
        clf
        for clf in classifications
        if clf.ir_kind
        in (IRKind.ADR_CONTEXT, IRKind.ADR_DECISION, IRKind.ADR_CONSEQUENCES)
    ]
    plan: list[tuple[str, str, list[int]]] = []

    if adr_group:
        filename, md = _render_adr_draft(adr_group)
        plan.append((filename, md, [clf.section.order for clf in adr_group]))

    for clf in classifications:
        if clf.ir_kind == IRKind.AE_RESPONSIBILITY:
            filename, md = _render_ae_draft(clf)
            plan.append((filename, md, [clf.section.order]))
        elif clf.ir_kind == IRKind.WS_BUSINESS_RULE:
            filename, md = _render_ws_draft(clf)
            plan.append((filename, md, [clf.section.order]))

    return plan


# --------------------------------------------------------------------------
# `run` — the orchestration entry point
# --------------------------------------------------------------------------


def _default_staging_dir() -> Path:
    """A fresh, filesystem-safe, sortable timestamped staging directory in the
    current working directory (used when `--out` is omitted)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / f"dekspec-ingest-{stamp}"


def run(path: str | Path, out_dir: str | Path | None = None) -> IngestResult:
    """Ingest a markdown document into a staging directory of draft artifacts.

    Reads the markdown file at `path`, classifies its sections via IB-097's
    deterministic `classify`, emits one draft artifact per confidently-
    classified section group into `out_dir` (or a fresh timestamped staging
    directory), writes the classification report, and returns an
    `IngestResult`.

    Raises `IngestError` on a usage error: a missing input file, a non-`.md`
    extension, or a non-empty pre-existing staging directory. `run` writes
    nothing outside the staging directory and never touches a live `dekspec/`
    tree (INT-059 OI-4).

    Promotion refs: INT-059 §Desired Outcome (draft artifacts at status
    `TODO`/`DRAFT` + a confidence-scored classification report), INT-059
    §Open Issues OI-3 (markdown-only input), OI-4 (staging-directory output),
    AE-005 (the CLI subcommand is a thin adapter over this `run`).
    """
    src = Path(path)

    # --- Input validation (OI-3): markdown only, file must exist. ----------
    if src.suffix.lower() not in _MARKDOWN_SUFFIXES:
        raise IngestError(
            f"Unsupported input format '{src.suffix or '(no extension)'}' for "
            f"'{src}'. `dekspec ingest` accepts markdown (.md) only at this "
            f"release; docx / pdf support is a future Intent."
        )
    if not src.is_file():
        raise IngestError(f"Input file not found: {src}")

    document = src.read_text(encoding="utf-8")
    classifications = classify(document)

    # --- Staging directory (OI-4): never the live dekspec/ tree. -----------
    staging = Path(out_dir) if out_dir is not None else _default_staging_dir()
    if staging.exists():
        if not staging.is_dir():
            raise IngestError(f"Staging path is not a directory: {staging}")
        if any(staging.iterdir()):
            raise IngestError(
                f"Staging directory '{staging}' already exists and is not "
                f"empty. Pass --out pointing at a new or empty directory so "
                f"`dekspec ingest` never clobbers existing files."
            )
    else:
        staging.mkdir(parents=True)

    # --- Emit draft artifacts. ---------------------------------------------
    plan = _plan_artifacts(classifications)
    artifact_files: dict[int, str] = {}
    written: list[str] = []
    for filename, markdown, orders in plan:
        (staging / filename).write_text(_lf(markdown), encoding="utf-8")
        written.append(filename)
        for order in orders:
            artifact_files[order] = filename

    # --- Shape + write the classification report. --------------------------
    report = shape_report(classifications, artifact_files)
    report_file = "classification-report.md"
    (staging / report_file).write_text(
        _lf(render_markdown(report)), encoding="utf-8"
    )

    return IngestResult(
        source_path=str(src),
        staging_dir=str(staging),
        report=report,
        report_file=report_file,
        artifact_files=tuple(written),
    )


def _lf(text: str) -> str:
    """Ensure LF line endings and exactly one trailing newline."""
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    return body if body.endswith("\n") else body + "\n"


def result_json(result: IngestResult) -> str:
    """Render an `IngestResult` as a JSON document — the `--json` CLI path.

    The per-section classification rows come from `report.py`'s JSON renderer,
    so the `--json` and Markdown outputs agree on the underlying data.
    """
    envelope = _report_dict(result.report)
    envelope["source_path"] = result.source_path
    envelope["staging_dir"] = result.staging_dir
    envelope["report_file"] = result.report_file
    envelope["artifact_files"] = list(result.artifact_files)
    return json.dumps(envelope, indent=2) + "\n"


def result_summary(result: IngestResult) -> str:
    """Render an `IngestResult` as a human-readable CLI summary (default)."""
    counts = result.report.counts
    lines: list[str] = []
    lines.append(f"dekspec ingest — {result.source_path}")
    lines.append(
        f"  Sections classified: {counts['total']}  |  "
        f"Draft artifacts emitted: {counts['emitted']}"
    )
    lines.append(f"  Staging directory:   {result.staging_dir}")
    lines.append(f"  Classification report: {result.report_file}")
    if result.artifact_files:
        lines.append("  Draft artifacts (unpromoted — review before promoting):")
        for filename in result.artifact_files:
            lines.append(f"    - {filename}")
    else:
        lines.append("  No section classified confidently — no drafts emitted.")
    lines.append(render_markdown(result.report))
    lines.append(
        "Nothing has landed in a live dekspec/ tree. Review the report, then "
        "promote keepers via the /dekspec:write-* skills."
    )
    return "\n".join(lines)
