"""DRAFT-slug temporary-ID helpers (INT-020).

DekSpec artifacts normally use canonical ``<KIND>-NNN-<slug>.md`` filenames
with ``<KIND>-NNN`` IDs. During concurrent multi-engineer authoring two
engineers collide on the next free number. The mitigation: author in-flight
artifacts as ``<KIND>-DRAFT-<slug>.md`` with ``<KIND>-DRAFT-<slug>`` IDs and
defer canonical-ID assignment to commit time via ``dekspec id allocate``.

DRAFT state is detected purely by filename / ID *pattern* — there is no IR
schema field for it. This module is the single home for that pattern logic so
the parser, the audit rules, and the CLI all import from one place.

## Public API

```python
from dekspec.draft_ids import (
    KINDS,
    DRAFT_FILENAME_RE,
    is_draft_filename,
    is_draft_id,
    parse_draft_filename,
    canonical_filename,
    draft_id,
)
```
"""
from __future__ import annotations

import re

# Artifact kinds that participate in the DRAFT-slug / registry convention.
KINDS: tuple[str, ...] = ("ADR", "AE", "WS", "IC", "IB", "INT", "MSN", "SP")

# A slug is one-or-more lowercase-alnum segments joined by single hyphens.
_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"

# `<KIND>-DRAFT-<slug>.md` — the DRAFT filename grammar. The kind alternation
# is ordered longest-first is unnecessary here (all distinct prefixes), but we
# anchor strictly so a canonical `ADR-007-foo.md` never matches.
DRAFT_FILENAME_RE = re.compile(
    r"^(?P<kind>" + "|".join(KINDS) + r")-DRAFT-(?P<slug>" + _SLUG + r")\.md$"
)

# `<KIND>-DRAFT-<slug>` — the DRAFT in-file ID grammar (no `.md`).
DRAFT_ID_RE = re.compile(
    r"^(?P<kind>" + "|".join(KINDS) + r")-DRAFT-(?P<slug>" + _SLUG + r")$"
)


def is_draft_filename(name: str) -> bool:
    """True if ``name`` (a bare filename) matches the DRAFT filename grammar."""
    return DRAFT_FILENAME_RE.match(name) is not None


def is_draft_id(s: str) -> bool:
    """True if ``s`` is a ``<KIND>-DRAFT-<slug>`` artifact ID."""
    return DRAFT_ID_RE.match(s) is not None


def parse_draft_filename(name: str) -> tuple[str, str]:
    """Return ``(kind, slug)`` for a DRAFT filename.

    Raises ValueError if ``name`` is not a DRAFT filename.
    """
    m = DRAFT_FILENAME_RE.match(name)
    if not m:
        raise ValueError(
            f"Not a DRAFT filename (expected <KIND>-DRAFT-<slug>.md): {name!r}"
        )
    return m.group("kind"), m.group("slug")


def canonical_filename(kind: str, number: int | str, slug: str) -> str:
    """Build a canonical ``<KIND>-NNN-<slug>.md`` filename.

    ``number`` is zero-padded to at least 3 digits.
    """
    if isinstance(number, str):
        number = int(number)
    return f"{kind}-{number:03d}-{slug}.md"


def draft_id(kind: str, slug: str) -> str:
    """Build a ``<KIND>-DRAFT-<slug>`` artifact ID."""
    return f"{kind}-DRAFT-{slug}"


__all__ = [
    "KINDS",
    "DRAFT_FILENAME_RE",
    "DRAFT_ID_RE",
    "is_draft_filename",
    "is_draft_id",
    "parse_draft_filename",
    "canonical_filename",
    "draft_id",
]
