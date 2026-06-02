"""IR schema migrations.

When an artifact's schema evolves (e.g., a field is added, renamed, split,
or collapsed across two schema versions), each change is captured here as
a **Migration** function that transforms an IR from the old shape to the
new shape.

The migration registry composes these into chains: to go from v0.1.0 to
v0.3.0, the registry walks the linked migrations v0.1.0 → v0.2.0 → v0.3.0
in order. Every IR produced by an older parser version can be brought
forward to the current schema without manual editing.

Today's state: every IR is at `0.1.0` and the registry is empty. The
infrastructure exists so the *first* real schema change is a small
incremental PR (define the schema delta + author one migration function +
add one test) rather than a coordinated cross-file rewrite.

## Public API

```python
from dekspec.migrations import (
    Migration,
    MigrationError,
    Registry,
    default_registry,
    migrate_ir,
    target_version_for,
)
```

## Authoring a new migration

When `mission` evolves from `0.1.0` to `0.2.0`:

```python
# In tooling/dekspec/migrations/mission.py:
from . import default_registry, Migration

def _v0_1_0_to_v0_2_0(ir: dict) -> dict:
    \"\"\"Collapse `out_of_scope` + `kill_criteria` into a single
    `negative_scope` list (calibration finding from MSN-001).\"\"\"
    out = dict(ir)
    merged = (ir.get("out_of_scope") or []) + (ir.get("kill_criteria") or [])
    if merged:
        out["negative_scope"] = merged
    out.pop("out_of_scope", None)
    out.pop("kill_criteria", None)
    out["ir_schema_version"] = "0.2.0"
    return out

default_registry.register(Migration(
    artifact_type="mission",
    from_version="0.1.0",
    to_version="0.2.0",
    migrate=_v0_1_0_to_v0_2_0,
))
```

Plus: bump the schema `const: "0.2.0"`, update the parser to emit
`ir_schema_version: "0.2.0"`, add the unit test in
`tests/test_migrations.py`.

## Invariants

- Migrations form a DAG keyed by (artifact_type, from_version, to_version).
- For a single artifact type, the migration chain MUST be linear (one
  migration per version step). Branching is not yet supported.
- Each migration is a pure function: deterministic, no I/O, no mutation
  of the input dict.
- The output IR's `ir_schema_version` field MUST equal `to_version`.
- Migrations are validated by `registry.validate_chains()` on import:
  every reachable target version must have an unbroken chain from each
  earlier version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .markdown import (
    AdvisoryItem,
    MarkdownMigration,
    MarkdownMigrationReport,
    MarkdownMigrationResult,
    MarkdownRegistry,
    advisory_report_path,
    detect_artifact_type,
    iter_markdown_artifacts,
    markdown_default_registry,
    migrate_markdown_artifacts,
    read_advisory_report,
    write_advisory_report,
)


class MigrationError(Exception):
    """Raised when no migration chain exists from an IR's version to the target."""


@dataclass(frozen=True)
class Migration:
    """A single schema-version step transformation.

    Each migration captures one delta: a field add, rename, split, or
    collapse across exactly two adjacent schema versions.

    Attributes:
      artifact_type: identifier matching the schema file name minus
        the `.schema.yaml` suffix. Examples: `adr`, `architecture_element`,
        `working_spec`, `interface_contract`, `implementation_brief`,
        `intent`, `mission`, `domain_glossary`, `system_vision`. Use
        underscores, not hyphens.
      from_version: semver string of the IR shape the migration consumes.
      to_version: semver string of the IR shape the migration produces.
      migrate: pure function from old-shape IR to new-shape IR.
      description: optional one-line summary for migration-chain audits.
    """
    artifact_type: str
    from_version: str
    to_version: str
    migrate: Callable[[dict[str, Any]], dict[str, Any]]
    description: str = ""


class Registry:
    """Compose Migration steps into chains."""

    def __init__(self) -> None:
        # Keyed by (artifact_type, from_version) → Migration
        self._steps: dict[tuple[str, str], Migration] = {}
        # Track the most recent target per artifact (the "latest" pointer).
        self._latest_target: dict[str, str] = {}

    def register(self, migration: Migration) -> None:
        """Add a migration step. Raises if a step for the same
        (artifact_type, from_version) is already registered (chain must
        be linear)."""
        key = (migration.artifact_type, migration.from_version)
        if key in self._steps:
            existing = self._steps[key]
            raise ValueError(
                f"Migration step conflict for {migration.artifact_type}: "
                f"already have {existing.from_version} → {existing.to_version}; "
                f"refusing to register {migration.from_version} → {migration.to_version}"
            )
        self._steps[key] = migration
        # The latest target is the highest to_version observed so far.
        current = self._latest_target.get(migration.artifact_type)
        if current is None or _semver_tuple(migration.to_version) > _semver_tuple(current):
            self._latest_target[migration.artifact_type] = migration.to_version

    def target_version_for(self, artifact_type: str, default: str) -> str:
        """Return the latest known target version for an artifact type,
        or `default` if no migrations have been registered."""
        return self._latest_target.get(artifact_type, default)

    def chain(
        self, artifact_type: str, from_version: str, to_version: str
    ) -> list[Migration]:
        """Return the ordered list of migration steps from `from_version`
        to `to_version` for the given artifact type. Empty list when
        from_version == to_version. Raises MigrationError if no chain exists.
        """
        if from_version == to_version:
            return []
        if _semver_tuple(from_version) > _semver_tuple(to_version):
            raise MigrationError(
                f"Refusing to downgrade {artifact_type} IR: "
                f"requested {from_version} → {to_version}"
            )
        steps: list[Migration] = []
        current = from_version
        while current != to_version:
            step = self._steps.get((artifact_type, current))
            if step is None:
                raise MigrationError(
                    f"No migration registered for {artifact_type} "
                    f"from {current} (needed to reach {to_version})"
                )
            steps.append(step)
            current = step.to_version
            if len(steps) > 100:  # pragma: no cover — cycle guard
                raise MigrationError(
                    f"Migration chain for {artifact_type} exceeded 100 steps; "
                    f"likely a cycle starting at {from_version}"
                )
        return steps

    def apply(
        self, ir: dict[str, Any], to_version: str | None = None,
    ) -> dict[str, Any]:
        """Apply the migration chain to an IR, returning a new dict.

        Inputs:
          ir: must contain an `id` (used to infer artifact_type) and
            `ir_schema_version` (the from_version).
          to_version: target; defaults to the latest registered for the
            artifact type, or the IR's own version if no migrations exist.

        Returns: a new IR dict at to_version. The input dict is not
        mutated.
        """
        from_version = ir.get("ir_schema_version")
        if not from_version:
            raise MigrationError(
                "IR is missing `ir_schema_version` — cannot migrate."
            )
        artifact_type = _artifact_type_from_id(ir.get("id", ""))
        target = to_version or self.target_version_for(artifact_type, from_version)
        chain = self.chain(artifact_type, from_version, target)
        working = dict(ir)
        for step in chain:
            working = step.migrate(working)
            if working.get("ir_schema_version") != step.to_version:
                raise MigrationError(
                    f"Migration {step.artifact_type} {step.from_version} → "
                    f"{step.to_version} returned IR with ir_schema_version="
                    f"{working.get('ir_schema_version')!r}; expected "
                    f"{step.to_version!r}"
                )
        return working

    def validate_chains(self) -> list[str]:
        """Return a list of problems with the current registry, or empty
        when clean. Catches missing intermediate steps so a registry-wide
        check at startup surfaces broken chains."""
        problems: list[str] = []
        per_artifact: dict[str, list[Migration]] = {}
        for m in self._steps.values():
            per_artifact.setdefault(m.artifact_type, []).append(m)
        for artifact_type, steps in per_artifact.items():
            from_versions = {s.from_version for s in steps}
            to_versions = {s.to_version for s in steps}
            # Every to_version that is not the latest target must also
            # appear as a from_version (i.e., a continuation step exists).
            latest = self._latest_target[artifact_type]
            for v in to_versions:
                if v != latest and v not in from_versions:
                    problems.append(
                        f"{artifact_type}: chain stops at {v} (no migration "
                        f"from {v} to the latest {latest})"
                    )
        return problems


def _semver_tuple(version: str) -> tuple[int, int, int]:
    """Parse a `X.Y.Z` semver string into a comparable tuple. Pre-release
    suffixes are stripped — `0.1.0-rc1` → (0, 1, 0)."""
    core = version.split("-", 1)[0].split("+", 1)[0]
    parts = core.split(".")
    if len(parts) != 3:
        raise ValueError(f"Not a semver-shaped version: {version!r}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _artifact_type_from_id(artifact_id: str) -> str:
    """Map an artifact id to the artifact_type used in migration
    registration. ADR-001 → 'adr', AE-014 → 'architecture_element', etc."""
    prefix_map = {
        "ADR-": "adr",
        "AE-": "architecture_element",
        "WS-": "working_spec",
        "IC-": "interface_contract",
        "IB-": "implementation_brief",
        "INT-": "intent",
        "MSN-": "mission",
        "SP-": "security_profile",
        "DOMAIN-GLOSSARY": "domain_glossary",
        "SYSTEM-VISION": "system_vision",
        "CONSTITUTION": "constitution",
    }
    for prefix, name in prefix_map.items():
        if artifact_id.startswith(prefix) or artifact_id == prefix.rstrip("-"):
            return name
    raise MigrationError(
        f"Cannot infer artifact_type from id {artifact_id!r}; "
        f"expected ADR-/AE-/WS-/IC-/IB-/INT-/MSN-/SP- prefix or singleton id "
        f"(DOMAIN-GLOSSARY / SYSTEM-VISION / CONSTITUTION)."
    )


# Module-level default registry. Sub-modules under dekspec.migrations
# register their per-artifact migrations against this instance at import
# time. Today empty (every IR is at 0.1.0); see module docstring for the
# authoring procedure when the first migration lands.
default_registry = Registry()


def migrate_ir(
    ir: dict[str, Any],
    to_version: str | None = None,
    registry: Registry | None = None,
) -> dict[str, Any]:
    """Convenience: migrate an IR through `registry` (default: the module
    default) to `to_version` (default: latest registered)."""
    reg = registry if registry is not None else default_registry
    return reg.apply(ir, to_version=to_version)


def target_version_for(artifact_type: str, default: str) -> str:
    """Convenience: query the default registry for the latest target."""
    return default_registry.target_version_for(artifact_type, default)


__all__ = [
    "AdvisoryItem",
    "MarkdownMigration",
    "MarkdownMigrationReport",
    "MarkdownMigrationResult",
    "MarkdownRegistry",
    "Migration",
    "MigrationError",
    "Registry",
    "advisory_report_path",
    "default_registry",
    "detect_artifact_type",
    "iter_markdown_artifacts",
    "markdown_default_registry",
    "migrate_ir",
    "migrate_markdown_artifacts",
    "read_advisory_report",
    "target_version_for",
    "write_advisory_report",
]


# Per-artifact migration sub-modules import here so their module-level
# `default_registry.register(...)` calls run when the migrations package
# is imported. New sub-modules append to this list.
from . import mission as _mission_migrations  # noqa: E402, F401  (registration side-effect)
from . import mission_markdown as _mission_markdown_migrations  # noqa: E402, F401
from . import severity_unification as _severity_unification_migrations  # noqa: E402, F401
from . import retire_stored_backlinks as _retire_stored_backlinks_migrations  # noqa: E402, F401
from . import ib_review_statuses as _ib_review_statuses_migrations  # noqa: E402, F401
from . import intent_beads_before_accept as _intent_bba_migrations  # noqa: E402, F401
