"""Severity vocabulary unification migration (ADR-013 / IB-023 / WS-013).

Re-keys `open_issues[*].severity` in persisted IR JSON from the
artifact-side legacy aliases (`blocking_pre_ib`, `blocking_pre_code`,
`blocking`, `non_blocking`, plus the variant spellings the historical
`_normalize_ws_severity` helper accepted) to the canonical `P0..P3`
ladder. Registers one `Migration` per artifact type
(`working_spec`, `implementation_brief`, `adr`, `interface_contract`,
`intent`) on `default_registry`, each carrying the IR forward from
`0.1.0` → `0.2.0`.

The alias map is sourced from `dekspec.severity` (the leaf module
shared with `constraint_compiler/parser.py`'s
`_normalize_severity_alias`) so the migration and the parser stay in
lockstep — a future change to ADR-013's alias rows lands in one place
(`severity.ARTIFACT_SEVERITY_ALIAS_MAP`) and both surfaces pick it up.

Audit-side aliases (`critical / important / minor`) are NOT in scope
here — they are owned by IB-024 in `dekspec.fidelity_audit`. Passing
one into this migration raises `MigrationError`.

## Invariants

- Idempotent: `migrate(migrate(ir)) == migrate(ir)` byte-equal modulo
  `ir_schema_version` (which is set to `to_version` on the first run
  and remains constant on the second).
- Pure: does not mutate the input dict.
- Fail-fast: unmapped non-canonical severity strings raise
  `MigrationError` with the offending value + the four canonical
  valid values + the literal `"see ADR-013 for the legacy alias map"`
  pointer in the message.
"""
from __future__ import annotations

from typing import Any

from ..severity import (
    ARTIFACT_SEVERITY_ALIAS_MAP,
    CANONICAL_VALUES,
    is_canonical,
)
from . import Migration, MigrationError, default_registry

# Per-artifact (from_version, to_version) pairs. Mirrors the schema
# `const` bump that landed alongside this migration in IB-023; today
# every artifact type below was at `0.1.0`, so the bump is `0.1.0 →
# 0.2.0` uniformly. A future severity-vocabulary revision would
# register its own migration sub-module bumping `0.2.0 → 0.3.0`.
_ARTIFACT_VERSION_BUMPS: tuple[tuple[str, str, str], ...] = (
    ("working_spec", "0.1.0", "0.2.0"),
    ("implementation_brief", "0.1.0", "0.2.0"),
    ("adr", "0.1.0", "0.2.0"),
    ("interface_contract", "0.1.0", "0.2.0"),
    ("intent", "0.1.0", "0.2.0"),
)


def _normalize_severity_field(value: Any, artifact_type: str) -> str:
    """Translate a single `severity` value to canonical.

    Canonical inputs are returned unchanged. Legacy aliases are
    looked up in `ARTIFACT_SEVERITY_ALIAS_MAP` (case-folded). Any
    other value raises `MigrationError` with a message naming the
    artifact type, the offending value, the four canonical valid
    values, and the literal `"see ADR-013 for the legacy alias map"`
    pointer.
    """
    if isinstance(value, str):
        if is_canonical(value):
            return value
        mapped = ARTIFACT_SEVERITY_ALIAS_MAP.get(value.strip().lower())
        if mapped is not None:
            return mapped
    valid = ", ".join(repr(v) for v in CANONICAL_VALUES)
    raise MigrationError(
        f"{artifact_type}: unmapped severity {value!r} in "
        f"open_issues — expected one of {valid} "
        f"(see ADR-013 for the legacy alias map)."
    )


def _make_migrate(artifact_type: str, to_version: str):
    """Build the per-artifact migrate callable bound to the artifact's
    `to_version`. Closes over `artifact_type` so error messages name
    the failing artifact type."""

    def _migrate(ir: dict[str, Any]) -> dict[str, Any]:
        out = dict(ir)
        raw_issues = ir.get("open_issues")
        if isinstance(raw_issues, list):
            new_issues: list[dict[str, Any]] = []
            for row in raw_issues:
                if not isinstance(row, dict):
                    # Preserve non-dict rows verbatim — the schema's
                    # structural check will surface them as a
                    # validation error downstream; the migration is
                    # not the place to gate shape.
                    new_issues.append(row)
                    continue
                new_row = dict(row)
                if "severity" in new_row:
                    new_row["severity"] = _normalize_severity_field(
                        new_row["severity"], artifact_type
                    )
                new_issues.append(new_row)
            out["open_issues"] = new_issues
        out["ir_schema_version"] = to_version
        return out

    return _migrate


for _artifact_type, _from_version, _to_version in _ARTIFACT_VERSION_BUMPS:
    default_registry.register(Migration(
        artifact_type=_artifact_type,
        from_version=_from_version,
        to_version=_to_version,
        migrate=_make_migrate(_artifact_type, _to_version),
        description=(
            f"IB-023: re-key {_artifact_type} open_issues[*].severity from "
            "legacy artifact-side aliases (blocking_pre_ib, blocking_pre_code, "
            "blocking, non_blocking) to canonical P0..P3 per ADR-013."
        ),
    ))


__all__ = ["_normalize_severity_field"]
