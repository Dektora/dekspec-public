"""The append-only ID-allocation registry (INT-020).

`dekspec/registry.yaml` is a grow-only ledger of every canonical artifact ID
that has been claimed. `dekspec id allocate` consults it to compute the next
free ID per kind and appends one entry per newly-allocated artifact.

The file is OPTIONAL. When `dekspec/registry.yaml` is absent every function
here treats it as an empty registry — `load_registry` returns the empty shape
and no audit rule fires. This repo (the DekSpec library itself) deliberately
leaves the file absent so the new audit rules no-op on its own self-spec.

## Public API

```python
from dekspec.registry import (
    RegistryEntry,
    RegistryError,
    registry_path,
    load_registry,
    validate_registry,
    next_canonical_id,
    append_entries,
    iter_entries,
)
```
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml

from jsonschema import Draft202012Validator

from .schemas import load_schema

# The registry's own format version. Bumped independently of the IR schemas.
REGISTRY_SCHEMA_VERSION = "0.1.0"


class RegistryError(Exception):
    """Raised on a malformed registry file or a failed schema validation."""


@dataclass
class RegistryEntry:
    """One allocated-ID row in the registry ledger.

    `parent_ws_id` is populated only for IB entries (IB IDs are unique only
    within their parent Working Spec, mirroring the SpecGraph composite key);
    it stays None for every other kind.
    """

    kind: str
    id: str
    slug: str
    allocated: str  # ISO date string
    allocated_by: str = "git-conflict"
    parent_ws_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the registry's on-disk dict shape.

        `parent_ws_id` is omitted entirely when None so canonical (non-IB)
        entries stay terse and schema-clean.
        """
        d: dict[str, Any] = {
            "kind": self.kind,
            "id": self.id,
            "slug": self.slug,
            "allocated": self.allocated,
            "allocated_by": self.allocated_by,
        }
        if self.parent_ws_id is not None:
            d["parent_ws_id"] = self.parent_ws_id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RegistryEntry:
        return cls(
            kind=d["kind"],
            id=d["id"],
            slug=d["slug"],
            allocated=d["allocated"],
            allocated_by=d.get("allocated_by", "git-conflict"),
            parent_ws_id=d.get("parent_ws_id"),
        )


def _empty_registry() -> dict[str, Any]:
    """The shape returned for an absent / never-created registry."""
    return {"schema_version": REGISTRY_SCHEMA_VERSION, "entries": []}


def registry_path(repo_root: str | Path, dekspec_root: str = "dekspec") -> Path:
    """Return the path to `dekspec/registry.yaml` under `repo_root`.

    The file need not exist — this is purely a path join.
    """
    return Path(repo_root).resolve() / dekspec_root / "registry.yaml"


def load_registry(
    repo_root: str | Path, dekspec_root: str = "dekspec"
) -> dict[str, Any]:
    """Load the registry as a dict.

    Returns the empty registry shape (`{"schema_version": ..., "entries": []}`)
    when the file is absent. Raises RegistryError on a malformed file.
    """
    path = registry_path(repo_root, dekspec_root)
    if not path.exists():
        return _empty_registry()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise RegistryError(f"Registry file is not valid YAML: {path}\n{e}") from e
    if raw is None:
        # An empty file is treated as an empty registry.
        return _empty_registry()
    if not isinstance(raw, dict):
        raise RegistryError(
            f"Registry file must be a YAML mapping, got {type(raw).__name__}: {path}"
        )
    raw.setdefault("schema_version", REGISTRY_SCHEMA_VERSION)
    raw.setdefault("entries", [])
    return raw


def validate_registry(data: dict[str, Any]) -> None:
    """JSON-schema validate a registry dict against the `registry` schema.

    Raises RegistryError with all errors collected when validation fails.
    """
    schema = load_schema("registry")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise RegistryError(
            "Registry failed schema validation:\n" + "\n".join(msgs)
        )


def iter_entries(registry: dict[str, Any]) -> Iterator[RegistryEntry]:
    """Iterate the registry's entries as RegistryEntry objects."""
    for row in registry.get("entries", []):
        yield RegistryEntry.from_dict(row)


def next_canonical_id(
    kind: str, registry: dict[str, Any], corpus_ids: list[str]
) -> str:
    """Compute the next free canonical ID for `kind`.

    Takes the max numeric suffix across both the registry's entries for that
    kind and `corpus_ids` (canonical IDs already present on disk), adds one,
    and zero-pads to 3 digits. Returns e.g. `ADR-014`.

    `corpus_ids` may contain IDs of any kind / DRAFT IDs — only IDs whose
    prefix matches `kind` and whose suffix is numeric are considered.
    """
    prefix = f"{kind}-"
    highest = 0
    for entry in iter_entries(registry):
        if entry.kind == kind:
            num = _id_number(entry.id, prefix)
            if num is not None and num > highest:
                highest = num
    for cid in corpus_ids:
        num = _id_number(cid, prefix)
        if num is not None and num > highest:
            highest = num
    return f"{kind}-{highest + 1:03d}"


def _id_number(artifact_id: str, prefix: str) -> Optional[int]:
    """Extract the numeric suffix of `artifact_id` if it has `prefix` and is
    a canonical (all-digit-suffix) ID. Returns None for DRAFT / foreign IDs."""
    if not artifact_id.startswith(prefix):
        return None
    suffix = artifact_id[len(prefix):]
    if suffix.isdigit():
        return int(suffix)
    return None


def append_entries(
    repo_root: str | Path,
    new_entries: list[RegistryEntry],
    dekspec_root: str = "dekspec",
) -> dict[str, Any]:
    """Append `new_entries` to the registry and write it back atomically.

    Existing entries are never rewritten or removed — the file is grow-only.
    Creates `dekspec/registry.yaml` if it does not yet exist. The resulting
    registry is schema-validated before the write; a validation failure
    raises RegistryError and leaves the file untouched.

    Returns the post-append registry dict.
    """
    registry = load_registry(repo_root, dekspec_root)
    registry["entries"].extend(e.to_dict() for e in new_entries)
    validate_registry(registry)

    path = registry_path(repo_root, dekspec_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_yaml(path, registry)
    return registry


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write `data` as YAML to `path` atomically (temp file + rename)."""
    text = (
        "# DekSpec ID-allocation registry (INT-020) — append-only.\n"
        "# Managed by `dekspec id allocate` / `dekspec id reconcile`.\n"
        "# Audited by the L-REGISTRY-APPEND-ONLY linkage rule. Do not edit\n"
        "# existing entries by hand.\n"
        + yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    )
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".registry-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


__all__ = [
    "REGISTRY_SCHEMA_VERSION",
    "RegistryEntry",
    "RegistryError",
    "registry_path",
    "load_registry",
    "validate_registry",
    "next_canonical_id",
    "append_entries",
    "iter_entries",
]
