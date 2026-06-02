"""Profile-aware skill-catalog discovery filter — MSN-006 / INT-066 / IB-114.

Every plugin-delivered skill at ``plugins/dekspec/skills/*/SKILL.md`` carries a
``mode:`` YAML frontmatter key valued ``lite`` or ``full``. This module reads
that frontmatter and narrows *default* skill discovery according to the active
methodology profile:

- Under the ``lite`` profile, default discovery omits ``mode: full`` skills
  (the heavy-ceremony authoring skills ``write-mission`` / ``write-ws`` /
  ``write-ic`` / ``write-ibs``).
- Under the ``full`` profile (the backwards-compatible default), every skill
  surfaces in default discovery exactly as before.

CRITICAL INVARIANT — the filter narrows DEFAULT discovery only; it never
deregisters or disables a skill. Every skill — including the four hidden under
``lite`` — remains fully resolvable on explicit invocation and under
``<skill> --help`` regardless of profile. ``resolve_skill`` and
``is_resolvable`` are profile-blind by design.

The active profile is read via INT-024's :func:`dekspec.dekspec_config.get_profile`
— the single load-bearing profile read point. This module does not invent its
own profile-detection path.

Public API:

- :data:`SKILLS_SUBDIR` — the repo-relative skills directory.
- :class:`SkillCatalogError` — raised on a malformed / missing ``SKILL.md``.
- :class:`SkillEntry` — one parsed skill (``name``, ``mode``, ``path``).
- :func:`skills_root(repo_root)` — the ``plugins/dekspec/skills`` directory.
- :func:`load_catalog(repo_root)` — parse every ``SKILL.md`` into entries.
- :func:`discover_skills(repo_root, *, profile=None)` — the default-discovery
  list, narrowed per the active (or supplied) profile.
- :func:`resolve_skill(repo_root, name)` — resolve one skill by name,
  profile-blind (the ``--help`` / explicit-invocation escape hatch).
- :func:`is_resolvable(repo_root, name)` — whether a skill resolves at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .dekspec_config import get_profile

__all__ = [
    "SKILLS_SUBDIR",
    "SKILL_MODES",
    "SkillCatalogError",
    "SkillEntry",
    "discover_skills",
    "is_resolvable",
    "load_catalog",
    "resolve_skill",
    "skills_root",
]

# Repo-relative location of the plugin-delivered skills (post-commit 67a5801,
# skills moved under the Claude Code plugin marketplace layout).
SKILLS_SUBDIR = Path("plugins") / "dekspec" / "skills"

# The valid `mode:` frontmatter values.
SKILL_MODES: tuple[str, ...] = ("lite", "full")


class SkillCatalogError(Exception):
    """Raised on a missing skills directory or a malformed ``SKILL.md``."""


@dataclass(frozen=True)
class SkillEntry:
    """One plugin-delivered skill parsed from its ``SKILL.md`` frontmatter."""

    name: str
    mode: str
    path: Path


def skills_root(repo_root: str | Path) -> Path:
    """Return the ``<repo_root>/plugins/dekspec/skills`` directory path."""
    return Path(repo_root) / SKILLS_SUBDIR


def _parse_frontmatter(skill_md: Path) -> dict:
    """Parse the leading ``---``-fenced frontmatter block of ``skill_md``.

    Reads the top-level ``key: value`` pairs of the frontmatter block. A plain
    line-scan is used rather than a strict YAML parse because Claude Code
    ``SKILL.md`` frontmatter (e.g. the ``argument-hint:`` line) carries
    unquoted bracket characters that a strict YAML loader rejects — and IB-114
    forbids reformatting any existing frontmatter line. Only the simple scalar
    keys this catalog needs (``name``, ``mode``) are consumed downstream.

    Raises :class:`SkillCatalogError` if the file has no closed frontmatter
    fence.
    """
    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise SkillCatalogError(
            f"{skill_md} has no leading '---' YAML frontmatter fence."
        )
    try:
        end = lines.index("---", 1)
    except ValueError as err:
        raise SkillCatalogError(
            f"{skill_md} frontmatter fence is not closed by a second '---'."
        ) from err
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip() != line:
            # Skip blank lines and any indented continuation (nested keys are
            # not used by the catalog).
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        data[key.strip()] = value.strip()
    return data


def _entry_from_skill_md(skill_md: Path) -> SkillEntry:
    """Build a :class:`SkillEntry` from one ``SKILL.md`` file."""
    frontmatter = _parse_frontmatter(skill_md)
    name = frontmatter.get("name") or skill_md.parent.name
    mode = frontmatter.get("mode")
    if mode is None:
        raise SkillCatalogError(
            f"{skill_md} frontmatter is missing the required 'mode:' key "
            f"(expected one of {', '.join(SKILL_MODES)})."
        )
    mode = str(mode)
    if mode not in SKILL_MODES:
        raise SkillCatalogError(
            f"{skill_md} frontmatter 'mode: {mode}' is out of range "
            f"(expected one of {', '.join(SKILL_MODES)})."
        )
    return SkillEntry(name=str(name), mode=mode, path=skill_md)


def load_catalog(repo_root: str | Path) -> list[SkillEntry]:
    """Parse every plugin-delivered ``SKILL.md`` into a sorted list of entries.

    Returns the entries sorted by ``name``. Raises :class:`SkillCatalogError`
    if the skills directory is absent or any ``SKILL.md`` is malformed.
    """
    root = skills_root(repo_root)
    if not root.is_dir():
        raise SkillCatalogError(f"No plugin skills directory at {root}.")
    entries = [
        _entry_from_skill_md(skill_md)
        for skill_md in sorted(root.glob("*/SKILL.md"))
    ]
    return sorted(entries, key=lambda e: e.name)


def discover_skills(
    repo_root: str | Path,
    *,
    profile: Optional[str] = None,
) -> list[SkillEntry]:
    """Return the default-discovery skill list, narrowed per the active profile.

    Under the ``lite`` profile, ``mode: full`` skills are omitted from default
    discovery. Under ``full`` (the default) every skill is surfaced. ``profile``
    may be passed explicitly; when ``None`` it is resolved via INT-024's
    :func:`get_profile` — the single load-bearing profile read point.

    This narrows DEFAULT discovery only — it never deregisters a skill. Use
    :func:`resolve_skill` for the profile-blind, explicit-invocation /
    ``--help`` escape hatch.
    """
    if profile is None:
        profile = get_profile(repo_root)
    catalog = load_catalog(repo_root)
    if profile == "lite":
        return [entry for entry in catalog if entry.mode != "full"]
    return catalog


def resolve_skill(repo_root: str | Path, name: str) -> Optional[SkillEntry]:
    """Resolve a skill by ``name``, profile-blind.

    This is the ``<skill> --help`` / explicit-invocation escape hatch: it
    resolves EVERY plugin-delivered skill regardless of the active profile,
    including the ``mode: full`` skills that :func:`discover_skills` hides
    under ``lite``. Returns ``None`` if no skill of that name exists.
    """
    for entry in load_catalog(repo_root):
        if entry.name == name:
            return entry
    return None


def is_resolvable(repo_root: str | Path, name: str) -> bool:
    """Return whether a skill named ``name`` resolves at all (profile-blind)."""
    return resolve_skill(repo_root, name) is not None
