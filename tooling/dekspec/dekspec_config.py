"""Per-repo `.dekspec/config.yaml` loader / writer.

`.dekspec/config.yaml` is the per-repo, committed declaration of the
methodology profile (`full` / `team`; how much DekSpec ceremony
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

Recognised dotted keys: `schema_version`, `methodology_profile`, `repo.scope`,
the setup-dekspec fields (INT-174) `issue_tracker`, `ephemeral_scratch_dir`,
`glossary_path`, `triage_labels.hitl`, `triage_labels.afk`,
`triage_labels.buckets`, and the DekTools enabled-set (ADR-047)
`dektools.enabled`.
"""
from __future__ import annotations

import json
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
    "dektools_catalog_path",
    "enabled_dektools_tools",
    "known_dektools_tools",
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
    # setup-dekspec fields (INT-174). `set_key` auto-vivifies the nested
    # `triage_labels` object, so the dotted sub-keys need no extra machinery.
    "issue_tracker",
    "ephemeral_scratch_dir",
    "glossary_path",
    "triage_labels.hitl",
    "triage_labels.afk",
    "triage_labels.buckets",
    # DekTools a-la-carte enabled-set (ADR-047). Array-valued: see
    # `DEKSPEC_CONFIG_ARRAY_KEYS`.
    "dektools.enabled",
)

# Dotted keys whose value is a LIST. The CLI hands `set_key` a raw string, so
# these are split on commas there; the Python API takes a real list either way.
DEKSPEC_CONFIG_ARRAY_KEYS: frozenset[str] = frozenset(
    {"dektools.enabled", "triage_labels.buckets"}
)


# Convenience aliases `get_key` / `set_key` accept and normalise to a canonical
# key before validation. `profile` is the short, ergonomic spelling of
# `methodology_profile` — `dekspec config get profile` / `set profile team`
# resolve to the same field (MSN-006 / INT-024 / IB-112; the MSN-006 Mission
# Verification predicate runs `dekspec config get profile`).
DEKSPEC_CONFIG_KEY_ALIASES: dict[str, str] = {
    "profile": "methodology_profile",
}

# Maps a `methodology_profile` value to the audit-profile manifest that
# `dekspec audit linkage` / `dekspec doctor` resolve when no explicit
# `--profile` flag is passed. `full` resolves to the `v1` baseline manifest;
# `team` resolves to its like-named manifest.
#
# `full` is the default lane's legacy spelling, not a lane name (ADR-050 §5):
# the default carries no user-facing name, and `v1` is a rule-set version.
_AUDIT_PROFILE_BY_METHODOLOGY: dict[str, str] = {
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


DEKTOOLS_RENAMES = {'prj-mgr': 'project-board', 'write-issue-beads': 'project-board', 'diagnose-bug': 'debug', 'debug-testfail': 'debug', 'analyze-module-depth': 'audit-codebase', 'orchestrate-module-deepening': 'deepen', 'deepen-until-dry': 'deepen', 'brownfield-ingest': 'ingest-docs', 'archeology': 'recover-specs', 'rotation-handoff': 'handoff', 'coding-session-forensics': 'diagnose-session'}


def migrate_dektools_names(names: list[str]) -> list[str]:
    # Setup is always available and never selectable (ADR-060); an older
    # selector accepted it, so drop it on read and the next write persists that.
    renamed = (DEKTOOLS_RENAMES.get(n, n) for n in names)
    return list(dict.fromkeys(n for n in renamed if n != "setup-dektools"))


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
    toolkit = raw.get("dektools")
    selection = toolkit.get("enabled") if isinstance(toolkit, dict) else None
    if isinstance(selection, list) and all(isinstance(n, str) for n in selection):
        raw["dektools"]["enabled"] = migrate_dektools_names(selection)
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
    if dotted_key == "dektools.enabled":
        return config.get("dektools", {}).get("enabled", [])
    node: Any = config
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise DekspecConfigError(
                f"Config key {dotted_key!r} is not set in "
                f"{config_path(repo_root)}."
            )
        node = node[part]
    return node


def dektools_catalog_path(start: Path | None = None) -> Path | None:
    """Locate `plugins/dektools/tool-catalog.json`, or None if unreachable.

    None is the normal answer for a pip/pipx-installed engine: the plugin
    trees are not bundled in the wheel (AE-008 / ADR-009), so the catalog
    simply is not there. Callers must treat that as "cannot know", never as
    "no tools exist".
    """
    use_bundled = start is None
    start = (start or Path(__file__)).resolve()
    for parent in start.parents:
        candidate = parent / "plugins" / "dektools" / "tool-catalog.json"
        if candidate.is_file():
            return candidate
    bundled = Path(__file__).parent / "_vendored/dektools/tool-catalog.json"
    return bundled if use_bundled and bundled.is_file() else None


def known_dektools_tools(catalog_path: Path | None = None) -> set[str]:
    """Tool names declared in the DekTools catalog.

    Returns an empty set when the catalog cannot be found or read — which
    disables name validation rather than rejecting every name (see
    `_validate_dektools_selection`).
    """
    path = catalog_path or dektools_catalog_path()
    if path is None:
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {t["name"] for t in payload.get("tools", []) if "name" in t}


def enabled_dektools_tools(repo_root: str | Path) -> list[str]:
    """The repo's DekTools enabled-set, or `[]` when unset.

    ADR-047 forces nothing on, so absent and empty mean the same thing and
    neither is an error — unlike `get_key`, which raises on an unset key.
    """
    try:
        config = load_config(repo_root)
    except DekspecConfigError:
        return []
    value = config.get("dektools", {}).get("enabled", [])
    return list(value) if isinstance(value, list) else []


def _validate_dektools_selection(value: Any) -> None:
    """Reject names absent from the catalog (ADR-047: the catalog is the list
    of known tools).

    Skipped entirely when the catalog is unresolvable. Refusing every name
    because the plugin tree is not checked out would make the key unusable on
    a pip-installed engine, and core must not depend on DekTools being
    present at all.
    """
    if isinstance(value, list) and "setup-dektools" in value:
        raise DekspecConfigError(
            "'setup-dektools' is always available and is not selectable (ADR-060)."
        )
    known = known_dektools_tools()
    if not known or not isinstance(value, list):
        return
    unknown = [v for v in value if v not in known]
    if unknown:
        raise DekspecConfigError(
            f"{', '.join(repr(u) for u in unknown)} "
            f"{'is' if len(unknown) == 1 else 'are'} not a DekTools tool. "
            f"Valid tools: {', '.join(sorted(known - {'setup-dektools'}))}"
        )


def set_key(repo_root: str | Path, dotted_key: str, value: Any) -> Path:
    """Set `dotted_key` to `value`, re-validate, and atomically rewrite.

    Raises `DekspecConfigError` if the key is unrecognised, the config file
    is absent, the value names an unknown DekTools tool, or the resulting
    document fails schema validation.
    """
    dotted_key = DEKSPEC_CONFIG_KEY_ALIASES.get(dotted_key, dotted_key)
    if dotted_key not in DEKSPEC_CONFIG_KEYS:
        raise DekspecConfigError(
            f"Unknown config key {dotted_key!r}. "
            f"Valid keys: {', '.join(DEKSPEC_CONFIG_KEYS)}"
        )
    if dotted_key == "dektools.enabled":
        _validate_dektools_selection(value)
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
    is the single load-bearing profile read point — the CLI audit-profile
    resolution consults it (MSN-006 / INT-024 / IB-112).

    Returns `"full"` — the backwards-compatible default — when
    `.dekspec/config.yaml` is absent or present but omits the
    `methodology_profile` field. Raises `DekspecConfigError` when the file
    exists but is malformed or carries an out-of-enum value (the schema
    enum is `full | team`).
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

    `full` resolves to the `v1` baseline manifest; `team` resolves to its
    like-named manifest. An unrecognised value falls back to `v1`
    (the schema enum keeps this path unreachable for a validated config).
    """
    return _AUDIT_PROFILE_BY_METHODOLOGY.get(methodology_profile, "v1")
