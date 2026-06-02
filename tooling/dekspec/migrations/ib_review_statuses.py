"""Source-markdown migration: stamp pre-existing IBs as review-grandfathered (INT-102 IU-2 / ds-20su).

MSN-017 introduces a two-tier non-sycophantic review pipeline. IU-1 (ds-2zoj)
bumped the IB IR schema 0.2.0 → 0.3.0, extending the `status` enum with five
review-pipeline states (`REVIEW_IB`, `REVIEW_IB_FAIL`, `REVIEW_PR`,
`REVIEW_PR_FAIL`, `TESTFAIL`) and adding an optional
`review_grandfathered: bool` field (default false).

This module is IU-1's consumer-side counterpart. Every IB authored before
MSN-017 went through the legacy non-reviewed lifecycle and must be flagged
as such so the new review-pipeline orchestration skills do not retroactively
route them through review states. The migration walks every IB markdown file
under `<repo>/dekspec/impl-briefs/...`, inspects the `**Status:** <token>`
meta-line, and inserts `**Review grandfathered:** true` immediately after it
when:

    1. The IB's Status is one of `ACCEPTED` or `TESTPASS` — the only two
       pre-MSN-017 statuses from which a real IB has been merged or is in
       active implementation. Other statuses (DRAFT / PROPOSED / TODO /
       LOCKED / QUEUED / ACTIVE / COMPLETED) are explicitly skipped —
       they either represent un-merged authoring states or terminal states
       whose `review_grandfathered` flag carries no operational meaning.
    2. The IB does not already carry a `**Review grandfathered:**` meta-line
       (idempotency — a second run produces no change).

Schema-version bridge: this migration registers as a `MarkdownMigration`
spanning `library_from_version=0.2.0` → `library_to_version=0.3.0`,
matching the IB IR schema bump in IU-1. `dekspec repo migrate-artifacts`
(now folded into `dekspec migrate`) already dispatches to
`markdown_default_registry`; no CLI wiring is needed here.

## Invariants

- **Idempotent**: a second run on the same file is a no-op. We check for an
  existing `**Review grandfathered:**` meta-line (case-insensitive on the
  label, anywhere in the file) before inserting.
- **Status-scoped**: only ACCEPTED and TESTPASS receive the stamp. All
  other statuses are skipped — no advisory, no edit.
- **Pure-mechanical**: the transform is deterministic text editing. No
  advisories are emitted by this migration (every change is an automatic
  insertion).
- **Insert site**: the new meta-line is inserted on the line immediately
  after the `**Status:** <token>` line, preserving the surrounding blank
  line / heading structure exactly.
"""
from __future__ import annotations

import re
from pathlib import Path

from .markdown import (
    MarkdownMigration,
    MarkdownMigrationResult,
    markdown_default_registry,
)

# Pre-MSN-017 statuses whose IBs are grandfathered out of the review
# pipeline. ACCEPTED IBs are mid-implementation; TESTPASS IBs have been
# implemented and tested under the legacy non-reviewed flow. Any IB still
# in DRAFT / PROPOSED / TODO / LOCKED / QUEUED / ACTIVE / COMPLETED is
# either un-authored, awaiting acceptance, locked-after-merge, or a
# transient queue state — none of those carry a meaningful retroactive
# review-grandfather semantic.
_GRANDFATHER_STATUSES: frozenset[str] = frozenset({"ACCEPTED", "TESTPASS"})

# Match the first `**Status:** <token>` meta-line. The token may carry a
# trailing prose annotation (e.g. `LOCKED — implementation merged …`); we
# only key off the first whitespace-bounded uppercase token after the
# colon to decide whether to stamp.
_STATUS_LINE_RE = re.compile(
    r"^(?P<full>\*\*Status:\*\*\s+(?P<token>[A-Z_]+).*)$",
    re.MULTILINE,
)

# Detect an existing review-grandfathered meta-line (case-insensitive on
# the label) anywhere in the file — guards idempotency. The value is not
# inspected; presence alone signals "already migrated".
_EXISTING_GRANDFATHER_RE = re.compile(
    r"^\*\*Review grandfathered:\*\*", re.MULTILINE | re.IGNORECASE,
)


def _apply(path: Path, text: str) -> MarkdownMigrationResult:
    """Stamp `**Review grandfathered:** true` after the Status meta-line
    when the IB is ACCEPTED or TESTPASS and not already stamped.

    Returns a `MarkdownMigrationResult` with `new_text` set when a change
    applies; otherwise an empty result (no advisory, no notes) so the
    orchestrator records the file as unchanged.
    """
    # Idempotency guard: if any review-grandfathered meta-line already
    # exists, do nothing. The check runs before the status lookup so a
    # legitimately-stamped IB whose status has since moved on (e.g.,
    # ACCEPTED → TESTPASS) is not double-stamped.
    if _EXISTING_GRANDFATHER_RE.search(text):
        return MarkdownMigrationResult()

    status_match = _STATUS_LINE_RE.search(text)
    if status_match is None:
        # No Status meta-line — almost certainly a malformed or non-IB
        # file that slipped through artifact-type detection. Skip
        # silently; the parser will surface its own warning on the next
        # parse cycle.
        return MarkdownMigrationResult()

    token = status_match.group("token")
    if token not in _GRANDFATHER_STATUSES:
        return MarkdownMigrationResult()

    # Insert the new meta-line on the line immediately after the Status
    # line. `re.sub` with count=1 ensures only the first Status line is
    # touched (defensive — IB markdown should never carry two).
    insertion = status_match.group("full") + "\n**Review grandfathered:** true"
    new_text = text[: status_match.start()] + insertion + text[status_match.end():]

    return MarkdownMigrationResult(
        new_text=new_text,
        notes=[f"stamped review_grandfathered=true on {path.name} (status={token})"],
    )


markdown_default_registry.register(MarkdownMigration(
    artifact_type="implementation_brief",
    library_from_version="0.2.0",
    library_to_version="0.3.0",
    apply=_apply,
    description=(
        "ds-20su (INT-102 IU-2): stamp `**Review grandfathered:** true` on "
        "pre-MSN-017 ACCEPTED / TESTPASS IBs so the two-tier review pipeline "
        "skips them. Idempotent; status-scoped."
    ),
))


__all__ = ["_apply"]
