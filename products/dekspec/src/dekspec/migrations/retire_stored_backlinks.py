"""Retire the stored `related_*s` backlink fields from persisted IR (ADR-015 / INT-034 / IB-045).

ADR-015 (derive backlinks from forward links + add a deterministic
`dekspec relink` command) retired the hand-maintained, stored
`related_*s` backlink projections. IB-044 removed those field
declarations from the architecture-element (AE) IR schema and from the
parser projection, and bumped the AE schema's `ir_schema_version` from
`0.1.0` → `0.2.0`. This module is IB-044's consumer-side counterpart:
it ships the migration that drops the now-retired stored backlink keys
from any persisted IR JSON a consumer repo upgrades, so a pre-retirement
corpus migrates cleanly across IB-044's `ir_schema_version` delta.

After this migration runs, backlinks are derived from the union of
forward links and rendered by `dekspec relink` — the stale stored
`Related *` IR fields are gone, and `dekspec relink` is the sole
source of the rendered `Related *` lines (ADR-015 §Open Issue P2).

## Affected field set

The retired stored backlink keys, both at the IR top level and nested
under `linked_artifacts` (the parser projected them under
`linked_artifacts`):

- `related_adrs`
- `related_wss`
- `related_ics`
- `related_ibs`
- `related_aes`
- `related_intents`

`linked_artifacts.owners` — author-maintained ownership metadata, not a
backlink — is preserved untouched.

## Affected artifact types

IB-044 modified only the architecture-element (AE) schema; the other
artifact schemas (ADR / Working Spec / IC / IB / Intent) were not
touched and stay at their current `ir_schema_version`. This module
therefore registers exactly one `Migration`, for `architecture_element`,
carrying the IR `0.1.0` → `0.2.0`. A future schema revision touching a
different artifact type registers its own migration sub-module.

## Invariants

- Idempotent: `migrate(migrate(ir)) == migrate(ir)` byte-equal modulo
  `ir_schema_version` (which is set to `to_version` on the first run
  and remains constant on the second). Deleting an already-absent key
  is a no-op; re-setting `ir_schema_version` to the value it already
  holds is a no-op.
- Clean no-op on an already-current IR: an IR that already lacks the
  retired fields (e.g., produced by a post-IB-044 parser, or already
  migrated) passes through unchanged except the `ir_schema_version`
  advance — no error, so a partially-migrated or already-current
  consumer corpus is safe to `dekspec migrate-ir`.
- Pure: does not mutate the input dict; does no filesystem I/O. File
  reading/writing is the `dekspec migrate-ir` CLI verb's concern.
- Deterministic: transforms identically across runs.
"""
from __future__ import annotations

from typing import Any

from . import Migration, default_registry

# The stored backlink keys retired by ADR-015 / IB-044. Deleting a key
# that is already absent is a no-op, so this set is safe to apply to a
# partially-migrated or already-current IR.
RETIRED_BACKLINK_KEYS: tuple[str, ...] = (
    "related_adrs",
    "related_wss",
    "related_ics",
    "related_ibs",
    "related_aes",
    "related_intents",
)

# Per-artifact (artifact_type, from_version, to_version) bumps. IB-044
# modified only the AE schema, so this module registers one migration.
# A type IB-044 did not modify gets no migration.
_ARTIFACT_VERSION_BUMPS: tuple[tuple[str, str, str], ...] = (
    ("architecture_element", "0.1.0", "0.2.0"),
)


def _strip_retired_keys(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `mapping` with every retired backlink key removed.

    Deleting an already-absent key is a no-op, so this is safe on a
    mapping that never carried the retired keys.
    """
    out = dict(mapping)
    for key in RETIRED_BACKLINK_KEYS:
        out.pop(key, None)
    return out


def _make_migrate(to_version: str):
    """Build the per-artifact migrate callable bound to the artifact's
    `to_version`."""

    def _migrate(ir: dict[str, Any]) -> dict[str, Any]:
        out = _strip_retired_keys(ir)
        # The parser projected the retired backlink fields under
        # `linked_artifacts`; strip them there too. `linked_artifacts`
        # may also be absent (older/partial IR) — guard the type.
        linked = out.get("linked_artifacts")
        if isinstance(linked, dict):
            out["linked_artifacts"] = _strip_retired_keys(linked)
        out["ir_schema_version"] = to_version
        return out

    return _migrate


for _artifact_type, _from_version, _to_version in _ARTIFACT_VERSION_BUMPS:
    default_registry.register(Migration(
        artifact_type=_artifact_type,
        from_version=_from_version,
        to_version=_to_version,
        migrate=_make_migrate(_to_version),
        description=(
            f"IB-045: drop the retired stored `related_*s` backlink fields "
            f"from {_artifact_type} IR (top level + nested under "
            "linked_artifacts) per ADR-015 / INT-034; backlinks are now "
            "derived from forward links and emitted by `dekspec relink`."
        ),
    ))


__all__ = ["RETIRED_BACKLINK_KEYS"]
