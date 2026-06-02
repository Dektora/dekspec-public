"""Per-repo `.dekspec/config.yaml` loader / writer.

`.dekspec/config.yaml` is the per-repo, committed declaration of the
methodology profile (`lite` / `team` / `full`; how much DekSpec ceremony
the team applies). Per ADR-024 (no-factory in-process-only execution
model, 2026-05-28), DekSpec runs in-process inside whichever coding CLI
is loaded; there is no executor abstraction. The `executor.kind` axis
introduced in INT-018 / MSN-004 was retired wholesale by MSN-016.

This module is the single load + write code path for that file. It
JSON-Schema-validates against `dekspec.schemas.load_schema("dekspec_config")`
(`additionalProperties: false` at every level, ADR-006) on both read and
write, and writes atomically via a temp file + `os.replace`.

Public API:

- `DekspecConfigError` — raised on a missing / invalid / un-parseable file.
- `config_path(repo_root)` — `<repo_root>/.dekspec/config.yaml`.
- `config_exists(repo_root)` — `bool`.
- `load_config(repo_root)` — read + schema-validate; returns the dict.
- `write_config(repo_root, data, *, force=False)` — atomic write; refuses
  to clobber an existing file unless `force=True`.
- `get_key(repo_root, dotted_key)` — read one dotted key.
- `set_key(repo_root, dotted_key, value)` — atomic per-key write +
  re-validate.

Recognised dotted keys: `schema_version`, `methodology_profile`, `repo.scope`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .schemas import load_schema

__all__ = [
    "CONFIG_DIRNAME",
    "CONFIG_FILENAME",
    "CONFIG_SCHEMA_VERSION",
    "DEKSPEC_CONFIG_KEYS",
    "DEKSPEC_CONFIG_KEY_ALIASES",
    "DekspecConfigError",
    "config_exists",
    "config_path",
    "get_key",
    "get_profile",
    "load_config",
    "resolve_audit_profile",
    "set_key",
    "write_config",
]

CONFIG_DIRNAME = ".dekspec"
CONFIG_FILENAME = "config.yaml"
CONFIG_SCHEMA_VERSION = "0.1.0"

# Dotted keys `get_key` / `set_key` recognise. Each maps to a JSON-pointer-ish
# path within the config dict.
DEKSPEC_CONFIG_KEYS: tuple[str, ...] = (
    "schema_version",
    "methodology_profile",
    "repo.scope",
)


# Convenience aliases `get_key` / `set_key` accept and normalise to a canonical
# key before validation. `profile` is the short, ergonomic spelling of
# `methodology_profile` — `dekspec config get profile` / `set profile lite`
# resolve to the same field (MSN-006 / INT-024 / IB-112; the MSN-006 Mission
# Verification predicate runs `dekspec config get profile`).
DEKSPEC_CONFIG_KEY_ALIASES: dict[str, str] = {
    "profile": "methodology_profile",
}

# Maps a `methodology_profile` value to the audit-profile manifest that
# `dekspec audit linkage` / `dekspec doctor` resolve when no explicit
# `--profile` flag is passed. `full` resolves to the `v1` baseline manifest;
# `lite` and `team` resolve to their like-named manifests.
_AUDIT_PROFILE_BY_METHODOLOGY: dict[str, str] = {
    "lite": "lite",
    "team": "team",
    "full": "v1",
}


class DekspecConfigError(Exception):
    """Raised on a missing, invalid, or un-parseable `.dekspec/config.yaml`."""


def config_path(repo_root: str | Path) -> Path:
    """Return the `<repo_root>/.dekspec/config.yaml` path (not resolved-existence)."""
    return Path(repo_root) / CONFIG_DIRNAME / CONFIG_FILENAME


def config_exists(repo_root: str | Path) -> bool:
    """Return whether `<repo_root>/.dekspec/config.yaml` exists as a file."""
    return config_path(repo_root).is_file()


def _validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema("dekspec_config"))


def _validate(data: Any, path: Path) -> None:
    """JSON-Schema-validate `data`; raise `DekspecConfigError` on the first error."""
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        loc = "/".join(str(p) for p in errors[0].absolute_path) or "<root>"
        raise DekspecConfigError(
            f"Invalid DekSpec config at {path}: {errors[0].message} (at {loc})"
        )


def load_config(repo_root: str | Path) -> dict[str, Any]:
    """Read + schema-validate `.dekspec/config.yaml`; return the parsed dict.

    Raises `DekspecConfigError` if the file is absent, is not a YAML
    mapping, or fails schema validation.

    Legacy `executor:` blocks (pre-MSN-016) are silently stripped from the
    loaded dict before validation. The on-disk file is not rewritten by
    this read path; consumers can drop the block themselves or run
    `dekspec migrate` (MSN-016 migration) for an idempotent strip.
    """
    path = config_path(repo_root)
    if not path.is_file():
        raise DekspecConfigError(
            f"No DekSpec config at {path}. Run `dekspec init` to create one, "
            "or `dekspec config set <key> <value>` after init."
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise DekspecConfigError(f"Could not parse YAML in {path}: {err}") from err
    if raw is None:
        raise DekspecConfigError(f"DekSpec config at {path} is empty.")
    if not isinstance(raw, dict):
        raise DekspecConfigError(
            f"DekSpec config at {path} did not parse to a YAML mapping."
        )
    # Strip the retired `executor` block in memory so legacy configs load
    # cleanly under the MSN-016 schema. The `auth` block is similarly
    # retired (it only paired with `executor.kind=dekfactory`).
    raw.pop("executor", None)
    raw.pop("auth", None)
    _validate(raw, path)
    return raw


def write_config(
    repo_root: str | Path,
    data: dict[str, Any],
    *,
    force: bool = False,
) -> Path:
    """Atomically write `data` to `.dekspec/config.yaml`; return the path.

    `data` is schema-validated before any byte hits disk. The write is
    atomic (temp file + `os.replace`). An existing file is NOT overwritten
    unless `force=True` — otherwise `DekspecConfigError` is raised.
    """
    path = config_path(repo_root)
    if path.exists() and not force:
        raise DekspecConfigError(
            f"DekSpec config already exists at {path}; pass force=True to overwrite."
        )
    _validate(data, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def get_key(repo_root: str | Path, dotted_key: str) -> Any:
    """Return the value at `dotted_key` from the validated config.

    Raises `DekspecConfigError` if the key is unrecognised or absent.
    """
    dotted_key = DEKSPEC_CONFIG_KEY_ALIASES.get(dotted_key, dotted_key)
    if dotted_key not in DEKSPEC_CONFIG_KEYS:
        raise DekspecConfigError(
            f"Unknown config key {dotted_key!r}. "
            f"Valid keys: {', '.join(DEKSPEC_CONFIG_KEYS)}"
        )
    config = load_config(repo_root)
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise DekspecConfigError(
                f"Config key {dotted_key!r} is not set in "
                f"{config_path(repo_root)}."
            )
        node = node[part]
    return node


def set_key(repo_root: str | Path, dotted_key: str, value: Any) -> Path:
    """Set `dotted_key` to `value`, re-validate, and atomically rewrite.

    Raises `DekspecConfigError` if the key is unrecognised, the config file
    is absent, or the resulting document fails schema validation.
    """
    dotted_key = DEKSPEC_CONFIG_KEY_ALIASES.get(dotted_key, dotted_key)
    if dotted_key not in DEKSPEC_CONFIG_KEYS:
        raise DekspecConfigError(
            f"Unknown config key {dotted_key!r}. "
            f"Valid keys: {', '.join(DEKSPEC_CONFIG_KEYS)}"
        )
    config = load_config(repo_root)
    parts = dotted_key.split(".")
    node: dict[str, Any] = config
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value
    path = config_path(repo_root)
    _validate(config, path)
    return write_config(repo_root, config, force=True)


def get_profile(repo_root: str | Path) -> str:
    """Return the active methodology profile for `repo_root`.

    Reads the `methodology_profile` field from `.dekspec/config.yaml`. This
    is the single load-bearing profile read point — the lite skill-catalog
    filter, the compact AGENTS.md emitter, and the CLI audit-profile
    resolution all consult it (MSN-006 / INT-024 / IB-112).

    Returns `"full"` — the backwards-compatible default — when
    `.dekspec/config.yaml` is absent or present but omits the
    `methodology_profile` field. Raises `DekspecConfigError` when the file
    exists but is malformed or carries an out-of-enum value (the schema
    enum is `lite | team | full`).
    """
    if not config_exists(repo_root):
        return "full"
    config = load_config(repo_root)
    value = config.get("methodology_profile")
    if value is None:
        return "full"
    return str(value)


def resolve_audit_profile(methodology_profile: str) -> str:
    """Map a `methodology_profile` value to its audit-profile manifest name.

    `full` resolves to the `v1` baseline manifest; `lite` and `team` resolve
    to their like-named manifests. An unrecognised value falls back to `v1`
    (the schema enum keeps this path unreachable for a validated config).
    """
    return _AUDIT_PROFILE_BY_METHODOLOGY.get(methodology_profile, "v1")
