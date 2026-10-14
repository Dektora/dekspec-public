"""Shared skill-header parsing, validation and source classification (ADR-074)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

__all__ = [
    "SkillHeaderError", "SkillHeaderWarning", "read_header", "split_header",
    "header_problems", "tree_problems", "split_tree_problems",
    "frozen_release_tree", "other_product_skills",
]


class SkillHeaderError(ValueError):
    """A skill header cannot be read or fails the header rules."""


class SkillHeaderWarning(UserWarning):
    """A sibling-product or frozen-release header has a reported problem."""


_FIELD_TYPES = {
    "name": str,
    "description": str,
    "mode": str,
    "model": str,
    "reasoning_effort": str,
    "allowed-tools": str,
    "argument-hint": str,
    "interaction": str,
    "disable-model-invocation": bool,
    "related_skills": list,
}


def split_header(text: str, skill_md: Path) -> tuple[str, str]:
    """Return fenced YAML and the unchanged remaining text, or a named error."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise SkillHeaderError(f"{skill_md}: YAML opening --- fence missing at line 1")
    for end in range(1, len(lines)):
        if lines[end].rstrip("\r\n") == "---":
            return "".join(lines[1:end]), "".join(lines[end + 1:])
    raise SkillHeaderError(f"{skill_md}: YAML closing --- fence missing")


def read_header(skill_md: Path, *, text: str | None = None) -> tuple[dict, str]:
    """Decode file or supplied text and return its body, without validating fields."""
    try:
        if text is None:
            text = skill_md.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise SkillHeaderError(f"{skill_md}: cannot read YAML header: {exc}") from exc
    header, body = split_header(text, skill_md)
    try:
        data = yaml.safe_load(header)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 2}" if mark is not None else ""
        # One line per problem also keeps installer warning lines unambiguous.
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        raise SkillHeaderError(f"{skill_md}: YAML error{location}: {problem}") from exc
    if not isinstance(data, dict):
        raise SkillHeaderError(f"{skill_md}: YAML header must be a mapping")
    return data, body


def header_problems(skill_md: Path, *, text: str | None = None) -> list[str]:
    """Return every field problem, or the parse error, without changing bytes."""
    try:
        data, _ = read_header(skill_md, text=text)
    except SkillHeaderError as exc:
        return [str(exc)]
    problems = []
    for key in ("name", "description"):
        if key not in data:
            problems.append(f"{skill_md}: missing required {key} field")
    for key, value in data.items():
        expected = _FIELD_TYPES.get(key)
        if expected is None:
            problems.append(f"{skill_md}: unknown field {key!r}")
        elif not isinstance(value, expected):
            problems.append(f"{skill_md}: {key} must be {expected.__name__}")
        elif key == "related_skills" and not all(isinstance(v, str) for v in value):
            problems.append(f"{skill_md}: related_skills must be a list of strings")
    if isinstance(data.get("name"), str) and data["name"] != skill_md.parent.name:
        problems.append(f"{skill_md}: name must match folder {skill_md.parent.name!r}")
    description = data.get("description")
    if isinstance(description, str) and not 1 <= len(description) <= 1024:
        problems.append(f"{skill_md}: description must contain 1 to 1024 characters (got {len(description)})")
    return problems


def _skill_files(skills_dir: Path) -> list[Path]:
    return [p for p in sorted(skills_dir.glob("*/SKILL.md"))
            if not p.parent.name.startswith(("_", ".")) and p.is_file()]


def tree_problems(skills_dir: Path) -> list[str]:
    """Check every skill in path order, irrespective of ownership or provenance."""
    return [problem for path in _skill_files(skills_dir) for problem in header_problems(path)]


def other_product_skills() -> frozenset[str]:
    """Names shipped by siblings of the running source package; none in wheels."""
    here = Path(__file__).resolve()
    if not (here.parents[1].name == "src" and here.parents[2].name == "dekspec"
            and here.parents[3].name == "products"):
        return frozenset()
    return frozenset(
        skill.parent.name
        for product in here.parents[3].iterdir()
        if product.is_dir() and product.name != "dekspec"
        for skill in _skill_files(product / "plugins" / product.name / "skills")
    )


def split_tree_problems(skills_dir: Path) -> tuple[list[str], list[str]]:
    """Partition the shared check's problems into refused and reported lists."""
    refused: list[str] = []
    reported: list[str] = []
    others = other_product_skills()
    for path in _skill_files(skills_dir):
        problems = reported if path.parent.name in others else refused
        problems.extend(header_problems(path))
    return refused, reported


def frozen_release_tree(skills_dir: Path) -> bool:
    """Recognize only provenance records matching every current skill's bytes."""
    parent = skills_dir.parent
    record = parent / "provenance.json"
    if not record.exists() and parent.name == "dekspec" and parent.parent.name == "plugins":
        record = parent.parent.parent / "provenance.json"
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or not isinstance(data.get("base"), str)
                or not data["base"] or not isinstance(data.get("files"), list)):
            return False
        hashes = {}
        for entry in data["files"]:
            if not isinstance(entry, dict):
                return False
            path = entry.get("fixture", entry.get("source"))
            digest = entry.get("sha256")
            if not isinstance(path, str) or not isinstance(digest, str):
                return False
            hashes[path] = digest
        return all(
            hashes.get(path.relative_to(record.parent).as_posix())
            == hashlib.sha256(path.read_bytes()).hexdigest()
            for path in _skill_files(skills_dir)
        )
    except (OSError, UnicodeError, ValueError):
        return False
