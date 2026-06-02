"""IR schemas shipped with dekspec.

Schemas are JSON Schema Draft 2020-12 written in YAML for review readability.
Loaded via `importlib.resources` so they ship as wheel-installable package data.

Today every schema is at `ir_schema_version: "0.1.0"` and lives in the package
root (flat layout). When the first schema evolution lands (e.g., the ds-zuy
Mission rigor calibration → v0.2.0 schema), retired versions move to
`schemas/archive/v0.1.0/<name>.schema.yaml` and the loader picks the right
file by `(artifact_type, ir_schema_version)`.

## Public API

```python
from dekspec.schemas import (
    SCHEMA_FILENAMES,
    LATEST_VERSIONS,
    list_schemas,
    load_schema,
)

# Load the latest schema for an artifact type
schema = load_schema("mission")

# Or pin to a specific version (today only 0.1.0 exists; future
# versions will resolve from the archive)
schema = load_schema("mission", version="0.1.0")

# List every (artifact_type, version) the library knows about
for artifact_type, version in list_schemas():
    print(artifact_type, version)
```

## Versioned-file layout

When v0.2.0 schemas land, the layout becomes:

```
schemas/
  mission.schema.yaml              # latest (v0.2.0)
  archive/
    v0.1.0/
      mission.schema.yaml          # retired v0.1.0
  __init__.py
```

`load_schema("mission")` returns the latest (`mission.schema.yaml`);
`load_schema("mission", version="0.1.0")` returns the archived copy.
`load_schema("mission", version="0.99.0")` raises `SchemaNotFoundError`.

The parser modules use `load_schema(artifact_type)` (latest) internally so
schema loads centralize through one code path. Consumers writing custom
validators do the same.
"""
from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml


class SchemaNotFoundError(Exception):
    """Raised when a requested (artifact_type, version) schema doesn't exist
    in the shipped package data."""


# Canonical map from artifact_type → schema filename (flat / latest).
# When new artifact types ship, add a row here.
SCHEMA_FILENAMES: dict[str, str] = {
    "adr": "adr.schema.yaml",
    "architecture_element": "architecture-element.schema.yaml",
    "working_spec": "working-spec.schema.yaml",
    "interface_contract": "interface-contract.schema.yaml",
    "implementation_brief": "implementation-brief.schema.yaml",
    "intent": "intent.schema.yaml",
    "mission": "mission.schema.yaml",
    "domain_glossary": "domain-glossary.schema.yaml",
    "security_profile": "security-profile.schema.yaml",
    "system_vision": "system-vision.schema.yaml",
    "constitution": "constitution.schema.yaml",
    "registry": "registry.schema.yaml",
    "team_profile": "team-profile.schema.yaml",
    "dekspec_config": "dekspec-config.schema.yaml",
}

# Latest published version per artifact type. Today every schema is at
# 0.1.0. When a schema evolves, bump the corresponding entry here.
LATEST_VERSIONS: dict[str, str] = {
    # adr, working_spec, interface_contract, implementation_brief, intent
    # all bumped 0.1.0 → 0.2.0 at IB-023 (severity vocabulary
    # unification — see ADR-013): `open_issues[*].severity` enum
    # narrowed from legacy `{blocking, non_blocking}` /
    # `{blocking_pre_ib, blocking_pre_code, non_blocking}` to canonical
    # `{P0, P1, P2, P3}`. Persisted v0.1.0 IR JSON migrates forward via
    # `tooling/dekspec/migrations/severity_unification.py`.
    # architecture_element bumped 0.1.0 → 0.2.0 at IB-044 (INT-034 /
    # ADR-015 — derive backlinks from forward links): the stored
    # `related_*s` backlink projections under `linked_artifacts` are
    # retired — backlinks are derived from the union of forward links and
    # emitted by `dekspec relink`, not schema-validated input. Persisted
    # v0.1.0 AE IR JSON migrates forward via the IB-045 migration module.
    "adr": "0.2.0",
    "architecture_element": "0.2.0",
    "working_spec": "0.2.0",
    "interface_contract": "0.2.0",
    "implementation_brief": "0.3.0",  # INT-102 IU-1 (ds-2zoj)
    "intent": "0.3.0",  # INT-104 IU-1 (ds-xoah)
    "mission": "0.2.0",
    "domain_glossary": "0.1.0",
    "security_profile": "0.1.0",
    "system_vision": "0.1.0",
    "constitution": "0.1.0",
    # registry (INT-020) — the append-only ID-allocation ledger.
    "registry": "0.1.0",
    # team_profile (INT-021) — the `team` audit-profile config schema:
    # validates the `approval_gates` block on profile manifests. Config
    # schema, not a parsed artifact IR.
    "team_profile": "0.1.0",
    # dekspec_config — the per-repo `.dekspec/config.yaml` schema. Declares
    # the `methodology_profile` axis (lite / team / full). The `executor`
    # axis introduced in INT-018 was retired by MSN-016 / ADR-024 (2026-05-28
    # — no-factory in-process-only execution model).
    "dekspec_config": "0.1.0",
}


@lru_cache(maxsize=64)
def load_schema(artifact_type: str, version: str | None = None) -> dict[str, Any]:
    """Load the schema for `artifact_type` at `version`.

    Args:
      artifact_type: one of `SCHEMA_FILENAMES.keys()` — underscore form.
      version: semver string. Defaults to the latest published version
        for the artifact type.

    Returns: the parsed schema dict.

    Raises:
      KeyError: artifact_type is not in SCHEMA_FILENAMES.
      SchemaNotFoundError: the (artifact_type, version) pair is not
        shipped with this library.
    """
    if artifact_type not in SCHEMA_FILENAMES:
        raise KeyError(
            f"Unknown artifact_type {artifact_type!r}. "
            f"Valid: {sorted(SCHEMA_FILENAMES.keys())}"
        )
    target_version = version or LATEST_VERSIONS[artifact_type]
    filename = SCHEMA_FILENAMES[artifact_type]

    if target_version == LATEST_VERSIONS[artifact_type]:
        # Latest lives at the flat root.
        return _read_yaml(("dekspec.schemas",), filename)

    # Retired versions live under archive/v<X.Y.Z>/.
    try:
        return _read_yaml(("dekspec.schemas", "archive", f"v{target_version}"), filename)
    except FileNotFoundError as e:
        raise SchemaNotFoundError(
            f"No schema for {artifact_type} at version {target_version}. "
            f"Latest is {LATEST_VERSIONS[artifact_type]}; archived versions "
            f"live under schemas/archive/v<X.Y.Z>/."
        ) from e


def _read_yaml(parts: tuple[str, ...], filename: str) -> dict[str, Any]:
    """Read a YAML resource via importlib.resources. Walks the package
    chain in `parts` to support nested directories like archive/v0.1.0/."""
    base = files(parts[0])
    for p in parts[1:]:
        base = base / p
    path = base / filename
    if not path.is_file():
        raise FileNotFoundError(f"Schema not found at {path}")
    with path.open("rb") as f:
        return yaml.safe_load(f)


def list_schemas() -> list[tuple[str, str]]:
    """List every (artifact_type, version) pair the library ships.

    Includes both the latest version per artifact type (always present)
    and any archived prior versions found under `archive/v<X.Y.Z>/`.

    Returns a list of (artifact_type, version) tuples sorted by
    (artifact_type, version).
    """
    seen: set[tuple[str, str]] = set()
    # Latest versions
    for artifact_type, version in LATEST_VERSIONS.items():
        seen.add((artifact_type, version))
    # Archive directory (if any)
    try:
        archive = files("dekspec.schemas") / "archive"
        if archive.is_dir():
            for version_dir in archive.iterdir():
                if not version_dir.is_dir() or not version_dir.name.startswith("v"):
                    continue
                version = version_dir.name[1:]  # strip leading 'v'
                for filename in SCHEMA_FILENAMES.values():
                    if (version_dir / filename).is_file():
                        artifact_type = _filename_to_artifact_type(filename)
                        seen.add((artifact_type, version))
    except (AttributeError, FileNotFoundError):
        # importlib.resources may not expose iterdir on all backends
        # for nested package paths; degrade gracefully.
        pass
    return sorted(seen)


def _filename_to_artifact_type(filename: str) -> str:
    for artifact_type, fn in SCHEMA_FILENAMES.items():
        if fn == filename:
            return artifact_type
    raise KeyError(f"Unknown schema filename: {filename}")


__all__ = [
    "SCHEMA_FILENAMES",
    "LATEST_VERSIONS",
    "SchemaNotFoundError",
    "list_schemas",
    "load_schema",
]
