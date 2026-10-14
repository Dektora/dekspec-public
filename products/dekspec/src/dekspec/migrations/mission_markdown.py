"""Source-markdown migration for Mission v0.1.0 → v0.2.0 (ds-zuy).

The IR migration in `mission.py` is mechanical: legacy prose is wrapped
in sentinel cmd entries so the new schema validates and consumers fail
loud. But the *source markdown* still carries the prose form — turning
that prose into authored, executable cmd predicates is judgement work
that humans (or LLM authoring skills) must do.

This module emits one `AdvisoryItem` per legacy-shaped Mission file so
the `/dekspec:migrate --walker-only` orchestrator can walk them. No automatic
edits to the markdown.
"""
from __future__ import annotations

import re
from pathlib import Path

from .markdown import (
    AdvisoryItem,
    MarkdownMigration,
    MarkdownMigrationResult,
    markdown_default_registry,
)


_H3_ROLLBACK_RE = re.compile(
    r"^###\s+Rollback plan\s*$(?P<body>.*?)(?=^###\s|^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_H3_KILL_RE = re.compile(
    r"^###\s+Kill criteria\s*$(?P<body>.*?)(?=^###\s|^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_FENCED_YAML_RE = re.compile(r"```(?:yaml)?\s*\n.*?\n```", re.DOTALL)


def _has_structured_block(section_body: str) -> bool:
    """True iff the section already carries a fenced yaml cmd-check list."""
    m = _FENCED_YAML_RE.search(section_body)
    if not m:
        return False
    return "name:" in m.group(0) and "cmd:" in m.group(0)


def _apply(path: Path, text: str) -> MarkdownMigrationResult:
    """Inspect a Mission .md; if Rollback plan or Kill criteria are still
    in legacy prose form, emit an advisory. Never edits the file."""
    legacy_fields: list[str] = []

    rollback_m = _H3_ROLLBACK_RE.search(text)
    if rollback_m and not _has_structured_block(rollback_m.group("body")):
        legacy_fields.append("Rollback plan")

    kill_m = _H3_KILL_RE.search(text)
    if kill_m and not _has_structured_block(kill_m.group("body")):
        legacy_fields.append("Kill criteria")

    if not legacy_fields:
        return MarkdownMigrationResult()

    return MarkdownMigrationResult(
        advisory=AdvisoryItem(
            artifact_path="",
            artifact_type="mission",
            library_from_version="",
            library_to_version="",
            change_type="section_split",
            description=(
                "Mission v0.2.0 (ds-zuy) reshapes "
                f"{' + '.join(legacy_fields)} from prose to named "
                "cmd-check list parallel to Mission Verification. Author "
                "an executable cmd predicate for each rollback step / "
                "kill condition, or accept the parser's "
                "`_legacy_prose` sentinel — runners will skip those."
            ),
            suggested_transform=(
                "Replace prose with a fenced yaml block:\n"
                "```yaml\n"
                "- name: <observable-condition>\n"
                "  cmd: <command that exits non-zero when the condition holds>\n"
                "```\n"
                "Use the existing §Mission Verification block as a template."
            ),
            context={"legacy_fields": legacy_fields},
        ),
    )


markdown_default_registry.register(MarkdownMigration(
    artifact_type="mission",
    library_from_version="0.43.5",
    library_to_version="0.44.0",
    apply=_apply,
    description=(
        "ds-zuy: advise on Mission §Rollback plan + §Kill criteria when "
        "still in legacy prose form."
    ),
))


__all__ = ["_apply"]
