"""Resolve the product's craft payload from source or an installed wheel."""

from __future__ import annotations

from pathlib import Path


def skills_root() -> Path:
    bundled = Path(__file__).parent / "_resources/skills"
    if bundled.is_dir():
        return bundled
    # Product-local source layout. Never search repository roots or siblings.
    return Path(__file__).resolve().parents[2] / "plugins/dektools/skills"


def skill_dir(name: str) -> Path:
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("a skill name must be one path component")
    return skills_root() / name


def skill_md(name: str) -> Path:
    return skill_dir(name) / "SKILL.md"
