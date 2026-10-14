"""Project canonical skill headers using ADR-074's per-host field table."""
from __future__ import annotations

from pathlib import Path

import yaml

from .skill_headers import SkillHeaderError, header_problems, read_header

__all__ = ["EXPLICIT_REQUEST_SUFFIX", "SkillMetadataError", "project_skill_md"]

EXPLICIT_REQUEST_SUFFIX = " Run only when the engineer explicitly asks for this skill by name."

# Columns: Claude, Codex, Antigravity, Cursor, Copilot, pi, Amp.
# Keep every field for existing hosts, including unknown historical fields:
# their installer retains IB-192's validation and frozen-tree exceptions.
_HOSTS = ("claude", "codex", "antigravity", "cursor", "copilot", "pi", "amp")
_FIELD_TABLE = {
    "name":                     ("keep", "keep", "keep", "keep", "keep", "keep", "keep"),
    "description":              ("keep", "keep", "keep", "keep", "keep", "keep", "description"),
    "mode":                     ("keep", "keep", "keep", "keep", "keep", "keep", "omit"),
    "model":                    ("keep", "keep", "keep", "keep", "keep", "keep", "omit"),
    "reasoning_effort":          ("keep", "keep", "keep", "keep", "keep", "keep", "omit"),
    "allowed-tools":             ("keep", "keep", "keep", "keep", "keep", "keep", "omit"),
    "disable-model-invocation":  ("keep", "keep", "keep", "keep", "keep", "keep", "omit"),
    "argument-hint":            ("keep", "keep", "keep", "keep", "keep", "keep", "keep"),
    "related_skills":           ("keep", "keep", "keep", "keep", "keep", "keep", "keep"),
    "interaction":              ("keep", "keep", "keep", "keep", "keep", "keep", "keep"),
}


class SkillMetadataError(ValueError):
    """A named skill cannot be projected under the host's field policy."""


def project_skill_md(skill_md: Path, host: str) -> str:
    """Return a host's complete skill text, preserving every canonical body byte.

    Existing hosts pass through unchanged; their validation stays with the
    installer. A translating row validates both headers through the shared
    checker and fails before returning any text. Nothing is written.
    """
    if host not in _HOSTS:
        raise SkillMetadataError(f"{skill_md}: unknown host {host!r}")
    column = _HOSTS.index(host)
    row = {key: actions[column] for key, actions in _FIELD_TABLE.items()}
    try:
        raw = skill_md.read_bytes()
        if all(action == "keep" for action in row.values()):
            return raw.decode("utf-8", errors="surrogateescape")
        text = raw.decode("utf-8")
        problems = header_problems(skill_md, text=text)
        if problems:
            raise SkillMetadataError("\n".join(problems))
        canonical, body = read_header(skill_md, text=text)
        projected = {}
        for key, value in canonical.items():
            action = row.get(key)
            if action is None:
                raise SkillMetadataError(f"{skill_md}: uncovered field {key!r}")
            if action == "omit":
                continue
            if action == "description" and canonical.get("disable-model-invocation") is True:
                value += EXPLICIT_REQUEST_SUFFIX
            projected[key] = value
        result = "---\n" + yaml.safe_dump(
            projected, sort_keys=False, allow_unicode=True, width=10**6,
        ) + "---\n" + body
        problems = header_problems(skill_md, text=result)
        if problems:
            raise SkillMetadataError("\n".join(problems))
        return result
    except (OSError, UnicodeError, SkillHeaderError) as exc:
        raise SkillMetadataError(f"{skill_md}: {exc}") from exc
