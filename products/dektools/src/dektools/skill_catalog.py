"""Craft payload discovery, with no specification policy or sibling dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .resources import skills_root


@dataclass(frozen=True)
class SkillEntry:
    name: str
    mode: str
    path: Path


def load_catalog(repo_root=None) -> list[SkillEntry]:
    entries = []
    for path in sorted(skills_root().glob("*/SKILL.md")):
        lines = path.read_text().splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            raise ValueError(f"invalid craft frontmatter: {path}")
        fields = {}
        for line in lines[1:lines[1:].index("---") + 1]:
            key, sep, value = line.partition(":")
            if sep:
                fields[key] = value.strip()
        entries.append(SkillEntry(fields.get("name", path.parent.name), fields["mode"], path))
    return sorted(entries, key=lambda entry: entry.name)
