"""Skill-catalog discovery — MSN-006 / INT-066 / IB-114.

Every plugin-delivered skill at ``plugins/<plugin>/skills/*/SKILL.md`` carries a
``mode:`` YAML frontmatter key valued ``lite`` or ``full``. The key classifies
a skill's authoring weight and is enforced by the ``T-SKILL-FRONTMATTER-NORMAL``
audit rule; it no longer narrows discovery.

DekSpec runs one lane at full rigor (ADR-050), so discovery is unconditional:
every skill surfaces, and ``resolve_skill`` / ``is_resolvable`` resolve every
skill by name.

Public API:

- :data:`SKILLS_SUBDIR` — the repo-relative skills directory.
- :class:`SkillCatalogError` — raised on a malformed / missing ``SKILL.md``.
- :class:`SkillEntry` — one parsed skill (``name``, ``mode``, ``path``).
- :func:`skills_root(repo_root)` — the ``plugins/dekspec/skills`` directory.
- :func:`skills_roots(repo_root)` — the skills directories that exist (ADR-064:
  one plugin, so at most one).
- :func:`load_catalog(repo_root)` — parse every ``SKILL.md`` into entries.
- :func:`discover_skills(repo_root)` — the default-discovery list: every
  skill, unfiltered (the same entries as :func:`load_catalog`).
- :func:`resolve_skill(repo_root, name)` — resolve one skill by name,
  profile-blind (the ``--help`` / explicit-invocation escape hatch).
- :func:`is_resolvable(repo_root, name)` — whether a skill resolves at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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

#: Every shipped plugin that delivers skills. ADR-064 folded the operator
#: tools into the `dekspec` plugin, so every skill — lifecycle skill or helper
#: tool — lives at ``plugins/dekspec/skills/<name>/``.
SKILL_PLUGIN_NAMES: tuple[str, ...] = ("dekspec",)

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


def skills_roots(repo_root: str | Path) -> list[Path]:
    """Return every plugin skills directory that exists."""
    base = Path(repo_root) / "plugins"
    return [d for d in (base / name / "skills" for name in SKILL_PLUGIN_NAMES) if d.is_dir()]


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
    roots = skills_roots(repo_root)
    if not roots:
        raise SkillCatalogError(
            f"No plugin skills directory under {Path(repo_root) / 'plugins'} "
            f"(looked for {', '.join(SKILL_PLUGIN_NAMES)})."
        )
    seen: set[str] = set()
    entries: list[SkillEntry] = []
    for root in roots:
        for skill_md in sorted(root.glob("*/SKILL.md")):
            entry = _entry_from_skill_md(skill_md)
            if entry.name in seen:
                continue  # first root wins on a name collision
            seen.add(entry.name)
            entries.append(entry)
    return sorted(entries, key=lambda e: e.name)


def discover_skills(repo_root: str | Path) -> list[SkillEntry]:
    """Return every skill the plugin ships — the full catalog, unfiltered.

    Nothing narrows discovery: one lane at full rigor (ADR-050), and every
    tool ships with the plugin (ADR-064), so this is :func:`load_catalog`.
    """
    return load_catalog(repo_root)


def resolve_skill(repo_root: str | Path, name: str) -> Optional[SkillEntry]:
    """Resolve a skill by ``name``.

    Resolves EVERY plugin-delivered skill. Returns ``None`` if no skill of
    that name exists.
    """
    for entry in load_catalog(repo_root):
        if entry.name == name:
            return entry
    return None


def is_resolvable(repo_root: str | Path, name: str) -> bool:
    """Return whether a skill named ``name`` resolves at all."""
    return resolve_skill(repo_root, name) is not None
