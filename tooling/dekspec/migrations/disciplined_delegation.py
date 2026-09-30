"""Source-markdown migration for the disciplined-delegation overhaul (ADR-055–057).

Library span 0.124.0 → 0.125.0. Mechanical, idempotent, and explicit — every
change it makes is written into the artifact's own Amendment Log, so no
status and no authority is reinterpreted silently:

* **Retired statuses** (ADR-057) map to their decision-state successor:

  ==============================  ===========================================
  kind                            mapping
  ==============================  ===========================================
  every kind                      TODO → DRAFT
  Implementation Brief            QUEUED / ACTIVE / REVIEW_IB / REVIEW_IB_FAIL /
                                  REVIEW_PR / REVIEW_PR_FAIL / TESTFAIL /
                                  LOCKED → ACCEPTED; COMPLETED → COMPLETE
  Intent                          IMPLEMENTING / TESTPASS / MERGED / TESTFAIL →
                                  ACCEPTED; OVERSIZED → DRAFT (plus a P2 open
                                  issue: re-split before acceptance); LOCKED →
                                  COMPLETE
  Mission                         TODO → PROPOSED; COMPLETING → ACTIVE
  ==============================  ===========================================

  An IB or Intent that was mid-flight keeps its authorization (ACCEPTED); the
  activity its old status mirrored now lives in the execution record.

* **Authority policy** (ADR-055): every IB without an explicit
  ``**Authority policy:**`` line is stamped ``legacy`` — it was authored under
  ADR-049 and keeps that restrictive meaning until deliberately adopted. The
  retired ``**Review grandfathered:**`` line is removed (``legacy`` subsumes it).

* **Retired Intent field**: ``**Beads before accept:**`` is removed (ADR-056:
  no code beads).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from dekspec.execution.artifact_edit import append_amendment_row

from .markdown import MarkdownMigration, MarkdownMigrationResult, markdown_default_registry

__all__ = ["LIBRARY_FROM", "LIBRARY_TO", "migrate_text"]

LIBRARY_FROM = "0.124.0"
LIBRARY_TO = "0.125.0"
_AUTHOR = "dekspec migrate"

_STATUS_MAPS: dict[str, dict[str, str]] = {
    "implementation_brief": {
        "TODO": "DRAFT", "QUEUED": "ACCEPTED", "ACTIVE": "ACCEPTED", "REVIEW_IB": "ACCEPTED",
        "REVIEW_IB_FAIL": "ACCEPTED", "REVIEW_PR": "ACCEPTED", "REVIEW_PR_FAIL": "ACCEPTED",
        "TESTFAIL": "ACCEPTED", "LOCKED": "ACCEPTED", "COMPLETED": "COMPLETE",
    },
    "intent": {
        "TODO": "DRAFT", "OVERSIZED": "DRAFT", "IMPLEMENTING": "ACCEPTED", "TESTPASS": "ACCEPTED",
        "MERGED": "ACCEPTED", "TESTFAIL": "ACCEPTED", "LOCKED": "COMPLETE",
    },
    "mission": {"TODO": "PROPOSED", "COMPLETING": "ACTIVE"},
}
_DEFAULT_MAP = {"TODO": "DRAFT"}

_META_STATUS = re.compile(r"^(\*\*Status:\*\*\s*)`?([A-Za-z_]+)`?(.*)$", re.MULTILINE)
_H2_STATUS = re.compile(r"(^##\s+Status\s*\n+)([A-Za-z_]+)", re.MULTILINE)
_AUTHORITY = re.compile(r"^\*\*Authority policy:\*\*", re.MULTILINE | re.IGNORECASE)
_REVIEW_GRANDFATHERED = re.compile(r"^\*\*Review grandfathered:\*\*.*\n", re.MULTILINE | re.IGNORECASE)
_BEADS_BEFORE_ACCEPT = re.compile(r"^\*\*Beads before accept:\*\*.*\n", re.MULTILINE | re.IGNORECASE)


def _row(change: str) -> str:
    return f"| {date.today().isoformat()} | Editorial | {change} | {_AUTHOR} |"


def _migrate_status(text: str, kind: str) -> tuple[str, list[str]]:
    mapping = _STATUS_MAPS.get(kind, _DEFAULT_MAP)
    notes: list[str] = []
    m = _META_STATUS.search(text)
    if m:
        old = m.group(2).upper()
        new = mapping.get(old)
        if new:
            text = _META_STATUS.sub(lambda mm: mm.group(1) + new + mm.group(3), text, count=1)
            notes.append(f"status {old} → {new}")
    else:
        m2 = _H2_STATUS.search(text)
        if m2:
            old = m2.group(2).upper()
            new = mapping.get(old)
            if new:
                text = _H2_STATUS.sub(lambda mm: mm.group(1) + new, text, count=1)
                notes.append(f"status {old} → {new}")
    if notes:
        old, new = notes[0][len("status "):].split(" → ")
        text = append_amendment_row(text, _row(
            f"Status {old} retired by ADR-057 (lifecycles record decisions, not activity) → {new}. "
            "Activity formerly mirrored by the status is execution evidence now."))
        if kind == "intent" and old == "OVERSIZED":
            text = _add_open_issue(text, "Analysis sized this Intent over the cap (was OVERSIZED); re-split "
                                         "before acceptance — **Source:** dekspec migrate — **Severity:** `P2`")
    return text, notes


def _add_open_issue(text: str, issue: str) -> str:
    line = f"- [ ] {issue}"
    m = re.search(r"^## Open Issues\s*$", text, re.MULTILINE)
    if not m:
        return append_amendment_row(text, _row("could not add the OVERSIZED open issue: no §Open Issues"))
    insert_at = text.find("\n", m.end()) + 1
    return text[:insert_at] + "\n" + line + "\n" + text[insert_at:]


def migrate_text(text: str, kind: str) -> tuple[str, list[str]]:
    """Pure transform. Returns (new_text, notes); notes empty ⇒ no change."""
    text, notes = _migrate_status(text, kind)
    if kind == "implementation_brief":
        if _REVIEW_GRANDFATHERED.search(text):
            text = _REVIEW_GRANDFATHERED.sub("", text)
            notes.append("removed retired `Review grandfathered` line")
        if not _AUTHORITY.search(text):
            m = _META_STATUS.search(text)
            if m:
                newline = text.find("\n", m.end())
                end = len(text) if newline == -1 else newline + 1
                text = text[:end] + "**Authority policy:** legacy\n" + text[end:]
                text = append_amendment_row(text, _row(
                    "Authority policy stamped `legacy` (ADR-055): authored under ADR-049, so Files to Modify "
                    "stays an allowlist and Constraints & Decisions stay binding until this IB is adopted."))
                notes.append("stamped authority policy legacy")
    if kind == "intent" and _BEADS_BEFORE_ACCEPT.search(text):
        text = _BEADS_BEFORE_ACCEPT.sub("", text)
        text = append_amendment_row(text, _row("Removed `Beads before accept` (ADR-056: no code beads)."))
        notes.append("removed retired `Beads before accept` line")
    return text, notes


def _step(kind: str):
    def apply(path: Path, text: str) -> MarkdownMigrationResult:  # noqa: ARG001
        new, notes = migrate_text(text, kind)
        return MarkdownMigrationResult(new_text=new if notes else None, notes=notes)
    return apply


for _kind in ("implementation_brief", "intent", "mission", "adr", "architecture_element", "working_spec",
              "interface_contract", "system_vision", "constitution", "security_profile"):
    markdown_default_registry.register(MarkdownMigration(
        artifact_type=_kind,
        library_from_version=LIBRARY_FROM,
        library_to_version=LIBRARY_TO,
        apply=_step(_kind),
        description="disciplined delegation: retired statuses, explicit IB authority policy, retired bead fields",
    ))
