"""Canonical severity vocabulary for DekSpec.

Single source of truth for the `P0 / P1 / P2 / P3` ladder adopted in
ADR-013 ("Severity Vocabulary Unification"). Both the constraint
compiler (parser-side `open_issues[*].severity` normalization, IB-023)
and the fidelity audit engine (audit-side `Finding.severity`
normalization, IB-024) import from this module so the two surfaces
share one canonical type without coupling to each other.

This module is a *leaf*: it MUST NOT import from
`dekspec.constraint_compiler` or `dekspec.fidelity_audit`. The one-way
dependency keeps the canonical-vocabulary contract portable to any
future severity-aware surface without dragging in parser or audit
implementation details.

## Canonical ladder

`P0` (highest) > `P1` > `P2` > `P3` (lowest). Mirrors `br` priority
exactly, so cross-tool dashboards sort on one axis.

## Public API

```python
from dekspec.severity import (
    Severity,           # typing.Literal["P0", "P1", "P2", "P3"]
    P0, P1, P2, P3,     # canonical string constants
    CANONICAL_VALUES,   # ("P0", "P1", "P2", "P3") — tuple, ordered highest→lowest
    is_canonical,       # predicate; case-sensitive, exact-match
    ARTIFACT_SEVERITY_ALIAS_MAP,  # legacy → canonical alias map (parser-side)
)
```

The representation is `typing.Literal` (not `enum.Enum`) because the
rest of the IR is plain `dict[str, Any]` — an `enum.Enum` member would
force `.value` conversion at every JSON-serialization site. With
`Literal`, the IR field is a plain `str` and tooling like `mypy`
narrows naturally.
"""
from __future__ import annotations

from typing import Final, Literal

# Canonical values, importable individually. The four string constants
# below MUST match the `CANONICAL_VALUES` tuple element-for-element.
P0: Final[Literal["P0"]] = "P0"
P1: Final[Literal["P1"]] = "P1"
P2: Final[Literal["P2"]] = "P2"
P3: Final[Literal["P3"]] = "P3"

# Type alias for IR / function signatures that want to pin to one of the
# four canonical values at the type-checker level. Equivalent to
# `Literal["P0", "P1", "P2", "P3"]`.
Severity = Literal["P0", "P1", "P2", "P3"]

# Canonical tuple ordered highest-priority first (P0 → P3). Used by
# schema-validation tests, doctor output sorting, and any caller that
# needs to enumerate the ladder.
CANONICAL_VALUES: Final[tuple[str, ...]] = ("P0", "P1", "P2", "P3")


def is_canonical(s: str) -> bool:
    """Return True iff `s` is exactly one of the four canonical values.

    Case-sensitive, exact-match — `"p0"`, `"P0 "`, and `"P00"` all
    return False. Alias normalization (case-folding, alias map lookup)
    is the caller's responsibility; this predicate answers "is the
    string already canonical?".
    """
    return s in CANONICAL_VALUES


# Parser-side legacy → canonical alias map. Mirrors ADR-013's
# *artifact-side* alias rows row-for-row (audit-side aliases like
# `critical / important / minor` are owned by IB-024 and live in
# `dekspec.fidelity_audit`, NOT here). Keys are lowercased + stripped
# legacy inputs; values are canonical `P0..P3`. A change to any row
# requires an ADR-013 amendment first — the per-row unit tests under
# `tests/test_severity_normalization.py` lock the mapping.
#
# Locked rows (per ADR-013):
#   blocking_pre_ib         → P1   (WS legacy; IB cannot be authored until resolved)
#   blocking_pre_code       → P2   (WS legacy; IBs OK; beads cannot start)
#   blocking                → P1   (IB/ADR/IC/Intent legacy; approval-blocking)
#   non_blocking            → P3   (all artifact surfaces; tracked concern)
#
# Variant spellings the existing `_normalize_ws_severity` helper
# accepted historically (preserved so no in-the-wild authored content
# breaks after the parser tightens):
#   "blocking (pre-ib)"     → P1
#   "blocking (pre-code)"   → P2
#   "pre-ib"                → P1
#   "pre-code"              → P2
#   "non-blocking"          → P3   (hyphen variant; the canonical key uses underscore)
ARTIFACT_SEVERITY_ALIAS_MAP: Final[dict[str, str]] = {
    # Canonical legacy keys (per ADR-013).
    "blocking_pre_ib": P1,
    "blocking_pre_code": P2,
    "blocking": P1,
    "non_blocking": P3,
    # Variant spellings preserved from the historical
    # `_normalize_ws_severity` helper.
    "blocking (pre-ib)": P1,
    "blocking (pre-code)": P2,
    "pre-ib": P1,
    "pre-code": P2,
    "non-blocking": P3,
}


__all__ = [
    "ARTIFACT_SEVERITY_ALIAS_MAP",
    "CANONICAL_VALUES",
    "P0",
    "P1",
    "P2",
    "P3",
    "Severity",
    "is_canonical",
]
