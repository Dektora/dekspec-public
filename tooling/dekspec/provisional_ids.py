"""Unified `P-<KIND>-NNN` provisional-ID helpers (ADR-043).

DekSpec artifacts normally use canonical ``<KIND>-NNN-<slug>.md`` filenames
with ``<KIND>-NNN`` IDs. An artifact may instead *incubate* under
``dekspec/provisional/<slug>/`` before ratification. ADR-043 gives every
kind one provisional form: ``P-<KIND>-<NNN>-<slug>.md`` with a
``P-<KIND>-<NNN>`` ID.

Two properties the ``P-`` prefix buys:

* **Non-binding number.** ``NNN`` is the next-available canonical number at
  authoring time — a hint only. Promotion re-derives the real next-free
  number, which may differ.
* **Self-exclusion from canonical numbering.** A ``P-`` filename never
  matches the canonical ``<KIND>-NNN-`` shape, so a provisional artifact is
  never counted when computing the next canonical id. This retires the
  legacy ``>=900`` sentinel workaround.

Provisional state is detected purely by filename / ID *pattern*. This module
is the single home for that pattern logic so the parser, the promotion
walker, the audit rules, and the CLI all import from one place. It mirrors
the DRAFT-slug convention in :mod:`dekspec.draft_ids`.
"""
from __future__ import annotations

import re

# Artifact kinds that participate in the provisional convention (same set as
# the DRAFT-slug / registry convention).
KINDS: tuple[str, ...] = ("ADR", "AE", "WS", "IC", "IB", "INT", "MSN", "SP")

# A slug is one-or-more lowercase-alnum segments joined by single hyphens.
_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"

# `P-<KIND>-<NNN>-<slug>.md` — the provisional filename grammar. Anchored so a
# canonical `ADR-042-foo.md` never matches.
PROVISIONAL_FILENAME_RE = re.compile(
    r"^P-(?P<kind>" + "|".join(KINDS) + r")-(?P<num>\d{3,})-(?P<slug>" + _SLUG + r")\.md$"
)

# `P-<KIND>-<NNN>` — the provisional in-file ID grammar (no slug, no `.md`).
PROVISIONAL_ID_RE = re.compile(
    r"^P-(?P<kind>" + "|".join(KINDS) + r")-(?P<num>\d{3,})$"
)


def is_provisional_filename(name: str) -> bool:
    """True if ``name`` (a bare filename) matches the provisional grammar."""
    return PROVISIONAL_FILENAME_RE.match(name) is not None


def is_provisional_id(s: str) -> bool:
    """True if ``s`` is a ``P-<KIND>-<NNN>`` artifact ID."""
    return PROVISIONAL_ID_RE.match(s) is not None


def parse_provisional_filename(name: str) -> tuple[str, str, str]:
    """Return ``(kind, num, slug)`` for a provisional filename.

    ``num`` is returned as the raw zero-padded string. Raises ValueError if
    ``name`` is not a provisional filename.
    """
    m = PROVISIONAL_FILENAME_RE.match(name)
    if not m:
        raise ValueError(
            f"Not a provisional filename (expected P-<KIND>-<NNN>-<slug>.md): {name!r}"
        )
    return m.group("kind"), m.group("num"), m.group("slug")


def provisional_id(kind: str, number: int | str) -> str:
    """Build a ``P-<KIND>-<NNN>`` artifact ID (number zero-padded to >=3)."""
    if isinstance(number, str):
        number = int(number)
    return f"P-{kind}-{number:03d}"


def provisional_filename(kind: str, number: int | str, slug: str) -> str:
    """Build a ``P-<KIND>-<NNN>-<slug>.md`` provisional filename."""
    if isinstance(number, str):
        number = int(number)
    return f"P-{kind}-{number:03d}-{slug}.md"


def provisional_id_or_none(filename: str) -> str | None:
    """Return the ``P-<KIND>-<NNN>`` ID if ``filename`` is a provisional
    filename, else None. The single seam the per-kind ``_extract_*_id``
    parser helpers consult before raising their canonical-mismatch error."""
    m = PROVISIONAL_FILENAME_RE.match(filename)
    if not m:
        return None
    return f"P-{m.group('kind')}-{m.group('num')}"


__all__ = [
    "KINDS",
    "PROVISIONAL_FILENAME_RE",
    "PROVISIONAL_ID_RE",
    "is_provisional_filename",
    "is_provisional_id",
    "parse_provisional_filename",
    "provisional_id",
    "provisional_filename",
    "provisional_id_or_none",
]
