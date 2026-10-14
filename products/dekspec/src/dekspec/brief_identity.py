"""Brief grammar, declarations and lookup (ADR-078, WS-038).

Numbered lookup never reads configuration. Named lookup validates only the
requested declaration, so a broken sibling cannot hide a healthy brief.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .dekspec_config import DekspecConfigError, load_config
from .draft_ids import is_draft_filename, is_draft_id
from .provisional_ids import is_provisional_id, provisional_id_or_none

__all__ = ["BriefIdentityError", "BriefRef", "list_briefs", "resolve_brief"]

_NUMBERED_ID = re.compile(r"^IB-\d{3,}$")
_NUMBERED_FILE = re.compile(r"^(IB-\d{3,})-.+\.md$")
_NAMED = r"IB-(?!DRAFT$)[A-Z][A-Z0-9]{0,15}"
_NAMED_ID = re.compile(rf"^{_NAMED}$")
_NAMED_FILE = re.compile(r"^(IB-(?!DRAFT(?:-|\.))[A-Z][A-Z0-9]{0,15})(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?\.md$")
_DEPENDENCY = re.compile(r"\b(IB-(?:\d{3,}|(?!DRAFT\b)[A-Z][A-Z0-9]{0,15}))\b")
# Compatibility export for the CLI's historical _IB_PREFIX name.
IB_PREFIX = re.compile(r"^IB-\d{3,}-")


@dataclass(frozen=True)
class BriefRef:
    """One brief, with its absolute file path and no synthetic number."""

    id: str
    path: Path
    declared: bool


@dataclass(frozen=True)
class BriefListing:
    """Independent successes and diagnostics from enumerating briefs."""

    briefs: tuple[BriefRef, ...]
    problems: tuple[BriefIdentityError, ...]


class BriefIdentityError(Exception):
    """A refusal; pre-existing lookup failures have no named rule."""

    def __init__(self, rule: str | None, message: str) -> None:
        super().__init__(f"{rule}: {message}" if rule else message)
        self.rule = rule


def is_brief_id(value: str) -> bool:
    """Whether a session binding has numbered or declared identity form."""
    return bool(_NUMBERED_ID.fullmatch(value) or _NAMED_ID.fullmatch(value))


def dependency_ids(text: str) -> list[str]:
    """Read whole-word dependencies without resolving or requiring declarations."""
    return list(dict.fromkeys(m.group(1) for m in _DEPENDENCY.finditer(text)))


def is_brief_filename(name: str, *, migration: bool = False) -> bool:
    """Classify a name only; parsing subsequently checks declarations.

    Keep the historical numbered prefix classifier, including its treatment
    of incomplete names, separate from the parser's full filename check.
    """
    if migration:
        bare = name[2:] if name.startswith("P-") else name
        bare = re.sub(r"^IB-provisional-", "IB-000-", bare)
        if bare != name:
            return bool(IB_PREFIX.match(bare))
    return bool(IB_PREFIX.match(name) or _NAMED_FILE.fullmatch(name))


def _malformed(value: str) -> BriefIdentityError:
    reserved = " DRAFT is reserved for DRAFT-slug files." if value in ("IB-DRAFT", "IB-DRAFT.md") else ""
    return BriefIdentityError(
        "named-brief-malformed-id",
        f"{value!r}: use IB- followed by one uppercase ASCII letter and up to 15 "
        f"more uppercase ASCII letters or digits (16 total), with no hyphen or P- prefix.{reserved} "
        "Correct the id and file name, then update named_briefs in .dekspec/config.yaml.",
    )


def check_brief_filename(name: str) -> None:
    """Diagnose malformed brief-like markdown names; leave other kinds alone."""
    if (not name.endswith(".md") or not name.startswith(("IB-", "P-IB-"))
            or _NUMBERED_FILE.fullmatch(name) or _NAMED_FILE.fullmatch(name)
            or is_draft_filename(name) or provisional_id_or_none(name)):
        return
    raise _malformed(name)


def _repository_for(path: Path) -> Path:
    """Find a parser input's declaration root without crossing a Git boundary."""
    for parent in path.resolve().parents:
        if (parent / ".dekspec" / "config.yaml").exists() or (parent / ".git").exists():
            return parent
    return path.resolve().parent


def brief_id_from_path(path: Path) -> str:
    """Resolve a parser input, hiding declaration-root discovery from readers."""
    brief_id = _filename_id(path.name)
    if not _NAMED_ID.fullmatch(brief_id):
        # Numbered and provisional parsing never needed a project root or
        # configuration; retain that independent, inexpensive path.
        return brief_id
    return resolve_brief(_repository_for(path), path.resolve()).id


def _filename_id(name: str) -> str:
    for pattern in (_NUMBERED_FILE, _NAMED_FILE):
        match = pattern.fullmatch(name)
        if match:
            return match.group(1)
    provisional = provisional_id_or_none(name)
    if provisional is not None:
        return provisional
    if is_draft_filename(name):
        # Lookup historically accepts this path; the parser owns the unchanged
        # DraftArtifactError requiring allocation before parsing.
        return name.removesuffix(".md")
    check_brief_filename(name)
    raise BriefIdentityError(None, f"Filename does not match IB-NNN-*.md pattern: {name}")


def _entries(root: Path) -> tuple[list[dict[str, str]], str | None]:
    try:
        return load_config(root).get("named_briefs", []), None
    except (DekspecConfigError, OSError, UnicodeError) as exc:
        return [], str(exc)


def _undeclared(brief_id: str, path: Path | None = None, detail: str = "") -> BriefIdentityError:
    return BriefIdentityError(
        "named-brief-undeclared",
        f"{brief_id} ({path or 'no declared path'}): add an entry with this file's path "
        f"under named_briefs in .dekspec/config.yaml. {detail}".rstrip(),
    )


def _declaration(root: Path, brief_id: str, entries: list[dict[str, str]], error: str | None) -> BriefRef:
    if not _NAMED_ID.fullmatch(brief_id):
        raise _malformed(brief_id)
    matches = [entry for entry in entries if entry["id"] == brief_id]
    if not matches:
        raise _undeclared(brief_id, detail=error or "")
    if len(matches) > 1:
        paths = ", ".join(entry["path"] for entry in matches)
        raise BriefIdentityError("named-brief-declared-twice", f"{brief_id}: {paths}; keep exactly one entry in named_briefs.")
    relative = matches[0]["path"]
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or "\\" in relative or not path.is_relative_to(root.resolve()):
        raise _undeclared(brief_id, path, "Use a POSIX path relative to the repository root, inside the repository.")
    if not path.is_file():
        raise BriefIdentityError("named-brief-file-missing", f"{brief_id}: {relative} is not a file; create the file or correct its named_briefs path.")
    try:
        actual = _filename_id(path.name)
    except BriefIdentityError as exc:
        if exc.rule is not None:
            raise
        raise BriefIdentityError(
            "named-brief-id-mismatch",
            f"{brief_id}: {relative} has no brief id; rename the file to "
            f"{brief_id}.md or {brief_id}-<slug>.md and update its named_briefs path.",
        ) from exc
    if actual != brief_id:
        raise BriefIdentityError("named-brief-id-mismatch", f"{brief_id}: {relative} is named for {actual}; rename the file for {brief_id} or correct the declaration.")
    return BriefRef(brief_id, path, True)


def resolve_brief(repo_root: str | Path, ref: str | Path, *, spec_root: str = "dekspec") -> BriefRef:
    """Resolve an id or path, preserving the legacy numbered lookup diagnostics."""
    root = Path(repo_root)
    value = str(ref)
    candidate = Path(ref)
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.suffix == ".md":
        check_brief_filename(candidate.name)
        if candidate.is_file() or _NAMED_FILE.fullmatch(candidate.name):
            brief_id = _filename_id(candidate.name)
            if not _NAMED_ID.fullmatch(brief_id):
                return BriefRef(brief_id, candidate.resolve(), False)
            entries, error = _entries(root)
            result = _declaration(root, brief_id, entries, error)
            if candidate.resolve() != result.path:
                raise _undeclared(brief_id, candidate, f"The declared path is {result.path}.")
            return result
    if _NUMBERED_ID.fullmatch(value):
        base = root / spec_root / "impl-briefs"
        matches = sorted(base.rglob(f"{value}-*.md")) if base.is_dir() else []
        if not matches:
            raise BriefIdentityError(None, f"no IB file for {value} under {base}")
        if len(matches) > 1:
            listing = ", ".join(str(m.relative_to(root)) for m in matches)
            raise BriefIdentityError(None, f"{value} is ambiguous ({listing}); pass the IB path instead")
        return BriefRef(value, matches[0].resolve(), False)
    if _NAMED_ID.fullmatch(value):
        entries, error = _entries(root)
        return _declaration(root, value, entries, error)
    # Markdown names were checked above; an absent file is a legacy lookup
    # failure, not a malformed id just because the bare filename starts IB-.
    if (candidate.suffix != ".md" and value.startswith(("IB-", "P-IB-"))
            and not is_provisional_id(value) and not is_draft_id(value)):
        raise _malformed(value)
    raise BriefIdentityError(None, f"{value!r} is neither an IB id (IB-NNN) nor an existing IB file")


def list_briefs(repo_root: str | Path, *, spec_root: str = "dekspec") -> BriefListing:
    """Enumerate all numbered files and declarations without hiding good siblings."""
    root = Path(repo_root)
    entries, error = _entries(root)
    briefs: dict[Path, BriefRef] = {}
    problems: dict[tuple[str | None, str], BriefIdentityError] = {}
    for brief_id in dict.fromkeys(entry["id"] for entry in entries):
        try:
            brief = _declaration(root, brief_id, entries, error)
            briefs[brief.path] = brief
        except BriefIdentityError as exc:
            problems[exc.rule, str(exc)] = exc
    base = root / spec_root / "impl-briefs"
    for path in sorted(base.rglob("*.md")) if base.is_dir() else []:
        if (not path.is_file() or not path.name.startswith(("IB-", "P-IB-"))
                or is_draft_filename(path.name)):
            continue
        if provisional_id_or_none(path.name):
            continue
        try:
            brief = resolve_brief(root, path.resolve(), spec_root=spec_root)
            briefs[brief.path] = brief
        except BriefIdentityError as exc:
            problems[exc.rule, str(exc)] = exc
    return BriefListing(tuple(sorted(briefs.values(), key=lambda b: (b.id, str(b.path)))), tuple(problems.values()))
