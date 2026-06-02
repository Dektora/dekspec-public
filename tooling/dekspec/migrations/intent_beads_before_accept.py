"""Source-markdown migration: stamp pre-Path-A Intents with beads_before_accept=false (INT-104 IU-2 / ds-vqca).

MSN-017 introduces the Path-A / Path-B accept-gate taxonomy for Intents.
IU-1 (ds-xoah) bumped the Intent IR schema 0.2.0 -> 0.3.0, adding an
optional ``beads_before_accept: bool`` field (default true for new Intents)
and the parser extraction for the ``**Beads before accept:**`` meta-line.

This module is IU-1's consumer-side counterpart.  Every Intent authored
before Path-A was defined follows the legacy lifecycle where beads are
filed *before* the Intent is accepted (Path B).  The migration walks
every Intent markdown file under ``<repo>/dekspec/intents/...``, and
inserts ``**Beads before accept:** false`` when:

    1. The Intent does not already carry a ``**Beads before accept:**``
       meta-line (idempotency -- a second run produces no change).

All statuses are eligible: SUPERSEDED Intents (like INT-103) are
pre-Path-A by definition and receive the stamp.

The stamp is inserted after ``## Risk Tier`` if present, otherwise
after ``## Status``, right before the next ``##`` heading -- matching
the template field order defined in ``templates/intent-template.md``.

Schema-version bridge: this migration registers as a ``MarkdownMigration``
spanning ``library_from_version=0.2.0`` -> ``library_to_version=0.3.0``,
matching the Intent IR schema bump in IU-1.  ``dekspec repo migrate-artifacts``
already dispatches to ``markdown_default_registry``; no CLI wiring needed.

## Invariants

- **Idempotent**: a second run on the same file is a no-op.  We check for
  an existing ``**Beads before accept:**`` meta-line (case-insensitive on
  the label, anywhere in the file) before inserting.
- **Status-agnostic**: every pre-Path-A Intent receives the stamp regardless
  of its current status.  SUPERSEDED Intents are pre-Path-A by definition.
- **Pure-mechanical**: the transform is deterministic text editing.  No
  advisories are emitted by this migration.
- **Insert site**: the new meta-line is inserted after the ``## Risk Tier``
  section (if present) or after the ``## Status`` section, before the next
  ``##`` heading, preserving the surrounding heading structure.
"""
from __future__ import annotations

import re
from pathlib import Path

from .markdown import (
    MarkdownMigration,
    MarkdownMigrationResult,
    markdown_default_registry,
)

# Detect an existing beads-before-accept meta-line (case-insensitive on
# the label) anywhere in the file -- guards idempotency.  The value is
# not inspected; presence alone signals "already migrated".
_EXISTING_BBA_RE = re.compile(
    r"^\*\*Beads before accept:\*\*", re.MULTILINE | re.IGNORECASE,
)

# Match `## Risk Tier` heading (the preferred anchor point).
_RISK_TIER_HEADING_RE = re.compile(
    r"^## Risk Tier\s*$", re.MULTILINE,
)

# Match `## Status` heading (fallback anchor when Risk Tier is absent).
_STATUS_HEADING_RE = re.compile(
    r"^## Status\s*$", re.MULTILINE,
)

# Match any `## <Heading>` line (used to locate the end of a section).
_SECTION_HEADING_RE = re.compile(
    r"^## ", re.MULTILINE,
)


def _find_section_end(text: str, section_start: int) -> int:
    """Return the character offset of the next ``## `` heading after
    ``section_start``, or ``len(text)`` if no further heading exists.

    ``section_start`` should point to the beginning of the ``## ``
    heading line that opens the section.
    """
    # Skip past the heading line itself before searching for the next one.
    after_heading = text.find("\n", section_start)
    if after_heading == -1:
        return len(text)
    m = _SECTION_HEADING_RE.search(text, after_heading + 1)
    if m is None:
        return len(text)
    return m.start()


def _apply(path: Path, text: str) -> MarkdownMigrationResult:
    """Stamp ``**Beads before accept:** false`` after the Risk Tier or
    Status section when the Intent does not already carry the meta-line.

    Returns a ``MarkdownMigrationResult`` with ``new_text`` set when a
    change applies; otherwise an empty result so the orchestrator records
    the file as unchanged.
    """
    # Idempotency guard.
    if _EXISTING_BBA_RE.search(text):
        return MarkdownMigrationResult()

    # Determine insertion anchor: prefer ## Risk Tier, fall back to ## Status.
    anchor_match = _RISK_TIER_HEADING_RE.search(text)
    if anchor_match is None:
        anchor_match = _STATUS_HEADING_RE.search(text)
    if anchor_match is None:
        # No Status heading -- malformed or non-Intent file.  Skip silently.
        return MarkdownMigrationResult()

    # Find the end of the anchor section (position of the next ## heading).
    insert_pos = _find_section_end(text, anchor_match.start())

    # Insert the stamp line.  We place it on its own line with a blank
    # line before it and preserve the blank line before the next heading.
    # The text at insert_pos is the start of the next `## ` heading.
    stamp = "**Beads before accept:** false\n\n"
    new_text = text[:insert_pos] + stamp + text[insert_pos:]

    return MarkdownMigrationResult(
        new_text=new_text,
        notes=[f"stamped beads_before_accept=false on {path.name}"],
    )


markdown_default_registry.register(MarkdownMigration(
    artifact_type="intent",
    library_from_version="0.2.0",
    library_to_version="0.3.0",
    apply=_apply,
    description=(
        "ds-vqca (INT-104 IU-2): stamp `**Beads before accept:** false` on "
        "pre-Path-A Intents so the accept-gate orchestration routes them "
        "through Path B.  Idempotent; status-agnostic."
    ),
))


__all__ = ["_apply"]
