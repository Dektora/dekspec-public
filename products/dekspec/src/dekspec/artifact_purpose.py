"""Installed artifact purposes, validated before any entry is exposed.

The record is library policy, independent of consumer files and the IR registry.
Item IDs are stable references: released IDs must never be renamed or reused.
"""

import re as _re
from importlib.resources import files as _files
from pathlib import Path as _Path

import yaml as _yaml
from jsonschema import Draft202012Validator as _Validator

__all__ = [
    "PurposeRecordError",
    "UnknownArtifactTypeError",
    "load_purpose_record",
    "purpose_entry",
    "record_path",
    "validate_purpose_record",
]

_TYPES = (
    "system-vision", "constitution", "mission", "intent", "architecture-element",
    "adr", "interface-contract", "behavior-spec", "implementation-brief",
    "security-profile", "domain-glossary",
)


class PurposeRecordError(ValueError):
    """The purpose record fails its schema or cross-reference rules."""


class UnknownArtifactTypeError(LookupError):
    """No artifact type matches the given name."""


def record_path() -> _Path:
    """Return the absolute path of the installed library's record."""
    return _Path(str(_files("dekspec.schemas").joinpath("artifact-purpose.yaml"))).resolve()


def _read_yaml(path):
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, _yaml.YAMLError) as exc:
        raise PurposeRecordError(f"{path}: cannot read purpose resource: {exc}") from exc


def load_purpose_record() -> dict:
    """Read and validate a fresh record on every call; no consumer overrides."""
    record = _read_yaml(record_path())
    validate_purpose_record(record)
    return record


def _error_owner(record, path):
    """Find the nearest item or type even when its child has an invalid shape."""
    owner = "purpose record"
    current = record
    for key in [*path, None]:
        if isinstance(current, dict):
            owner = current.get("id", current.get("type", owner))
        if key is None:
            break
        current = current[key]
    return owner


def validate_purpose_record(record: dict) -> None:
    """Validate shape, complete type inventory, item identity and destinations."""
    schemas = _files("dekspec.schemas")
    schema = _read_yaml(schemas.joinpath("artifact-purpose.schema.yaml"))
    error = next(_Validator(schema).iter_errors(record), None)
    if error is not None:
        owner = _error_owner(record, error.absolute_path)
        raise PurposeRecordError(f"{owner}: {error.message}")

    seen_types = set()
    for entry in record["types"]:
        kind = entry["type"]
        if kind not in _TYPES or kind in seen_types:
            raise PurposeRecordError(f"{kind}: unknown or repeated artifact type")
        seen_types.add(kind)
    missing = set(_TYPES) - seen_types
    if missing:
        raise PurposeRecordError(f"{', '.join(sorted(missing))}: missing artifact type")

    homes = set(_TYPES)
    for home in record["other_destinations"]:
        if home["id"] in homes:
            raise PurposeRecordError(f"{home['id']}: repeated destination")
        homes.add(home["id"])
    if "execution-record" not in homes:
        raise PurposeRecordError("execution-record: missing destination")
    subtypes = _read_yaml(schemas.joinpath("architecture-element.schema.yaml"))[
        "properties"
    ]["subtype"]["enum"]
    seen_items = set()
    names = {}
    for entry in record["types"]:
        kind = entry["type"]
        for name in [kind, entry["name"], *entry["aliases"]]:
            normalized = _normalize(name)
            if normalized in names and names[normalized] != kind:
                raise PurposeRecordError(f"{kind}: ambiguous artifact name {name!r}")
            names[normalized] = kind
        for field, segment in (("holds", "holds"), ("does_not_hold", "not")):
            for item in entry[field]:
                identifier = item["id"]
                if not _re.fullmatch(rf"{kind}\.{segment}\.[a-z0-9-]+", identifier):
                    raise PurposeRecordError(f"{identifier}: malformed item id for {kind}")
                if identifier in seen_items:
                    raise PurposeRecordError(f"{identifier}: repeated item id")
                seen_items.add(identifier)
                if field == "holds":
                    continue
                destination = item["destination"]
                if destination not in homes or destination == kind:
                    raise PurposeRecordError(f"{identifier}: invalid destination {destination!r}")
                if "subtype" in item and (
                    destination != "architecture-element" or item["subtype"] not in subtypes
                ):
                    raise PurposeRecordError(f"{identifier}: invalid subtype {item['subtype']!r}")


def _normalize(name):
    return _re.sub(r"[\s_]+", "-", name.casefold())


def purpose_entry(name: str) -> dict:
    """Match a type ID, display name or alias, ignoring case and separators."""
    record = load_purpose_record()
    normalized = _normalize(name)
    for entry in record["types"]:
        if any(normalized == _normalize(term)
               for term in [entry["type"], entry["name"], *entry["aliases"]]):
            return entry
    raise UnknownArtifactTypeError(
        f"Unknown artifact type {name!r}; choose from: {', '.join(_TYPES)}"
    )
