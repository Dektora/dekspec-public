"""Read, compare and atomically record which role notice a project has seen.

Records are disclosure history, never role policy. No command writes them yet.
"""

from __future__ import annotations

import json as _json
import os as _os
import tempfile as _tempfile
from collections.abc import Mapping as _Mapping
from dataclasses import dataclass as _dataclass
from pathlib import Path as _Path

from . import roles as _roles

__all__ = [
    "RECORD_FILENAME",
    "DisclosureDiff",
    "DisclosureRecord",
    "DisclosureRecordError",
    "RoleChange",
    "compare",
    "current_roles",
    "read_record",
    "record_disclosure",
]

RECORD_FILENAME = ".dekspec-role-disclosure.json"


class DisclosureRecordError(Exception):
    """A disclosure record could not be read or does not have the required form."""


@_dataclass(frozen=True)
class DisclosureRecord:
    release: str
    roles: _Mapping[str, int]
    platforms: tuple[str, ...] = ()


@_dataclass(frozen=True)
class RoleChange:
    role: str
    recorded: int | None
    current: int | None


@_dataclass(frozen=True)
class DisclosureDiff:
    reasons: tuple[str, ...] = ()
    role_changes: tuple[RoleChange, ...] = ()

    @property
    def due(self) -> bool:
        return bool(self.reasons)


def current_roles() -> dict[str, int]:
    """Load installed policy revisions afresh, in library role order."""
    return {role.id: role.policy_revision for role in _roles.load_all()}


def _validate(data: object, path: _Path) -> DisclosureRecord:
    problem = None
    if not isinstance(data, dict) or set(data) != {"release", "roles", "platforms"}:
        problem = "expected exactly release, roles and platforms"
    elif not isinstance(data["release"], str) or not data["release"]:
        problem = "release must be a non-empty string"
    elif not isinstance(data["roles"], dict) or any(
        not isinstance(role, str) or not role or type(revision) is not int or revision < 1
        for role, revision in data["roles"].items()
    ):
        problem = "roles must map non-empty role ids to integer revisions of at least 1"
    elif (not isinstance(data["platforms"], list)
          or any(not isinstance(p, str) or not p for p in data["platforms"])
          or data["platforms"] != sorted(set(data["platforms"]))):
        problem = "platforms must be a sorted list of distinct non-empty strings"
    if problem:
        raise DisclosureRecordError(f"Invalid disclosure record {path}: {problem}")
    return DisclosureRecord(data["release"], data["roles"], tuple(data["platforms"]))


def read_record(repo_root: str | _Path) -> DisclosureRecord | None:
    """Return the record, None when absent, or a named error when invalid."""
    path = _Path(repo_root) / RECORD_FILENAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise DisclosureRecordError(f"Could not read {path}: {exc}") from exc
    try:
        data = _json.loads(text)
    except ValueError as exc:
        raise DisclosureRecordError(f"Invalid JSON in {path}: {exc}") from exc
    return _validate(data, path)


def compare(record: DisclosureRecord | None, *, release: str, platform: str | None = None) -> DisclosureDiff:
    """Compare installed state without reading project policy or writing files."""
    if record is None:
        return DisclosureDiff(("no-record",))
    installed = current_roles()
    order = (*_roles.ROLE_IDS, *sorted(set(record.roles) - set(_roles.ROLE_IDS)))
    changes = tuple(
        RoleChange(role, record.roles.get(role), installed.get(role))
        for role in order if record.roles.get(role) != installed.get(role)
    )
    reasons = []
    if record.release != release:
        reasons.append("release-changed")
    if platform is not None and platform not in record.platforms:
        reasons.append("platform-new")
    if changes:
        reasons.append("roles-changed")
    return DisclosureDiff(tuple(reasons), changes)


def record_disclosure(repo_root: str | _Path, *, release: str, platform: str | None = None) -> DisclosureRecord:
    """Record installed revisions, retaining platforms from any valid prior record.

    Invalid history contributes no platforms. Validate before writing and replace
    the whole file atomically; identical records leave the file untouched.
    """
    path = _Path(repo_root) / RECORD_FILENAME
    try:
        previous = read_record(repo_root)
    except DisclosureRecordError:
        previous = None
    platforms = list(previous.platforms) if previous else []
    if platform is not None and platform not in platforms:
        platforms.append(platform)
    data = {"release": release, "roles": current_roles(), "platforms": sorted(platforms)}
    record = _validate(data, path)
    if record == previous:
        return record
    temporary = None
    try:
        with _tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f"{RECORD_FILENAME}.", delete=False) as stream:
            temporary = _Path(stream.name)
            stream.write(_json.dumps(data, indent=2) + "\n")
        _os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return record
