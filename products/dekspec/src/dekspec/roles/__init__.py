"""Agent Role Specifications — library-supplied operational role contracts (ADR-061, IC-019).

Each of the six roles DekSpec dispatches has exactly one canonical definition,
``<role>.md`` in this package, shipped as package data. Nothing is vendored or
copied: a wheel install carries the definitions, the ``/implement`` driver
reads them here, and skills read them through ``dekspec resource role <id>``.
A consuming project never supplies, overrides or selects one — a file in the
project is not library policy and is never loaded.

Dispatched instructions are composed in four layers, in this order::

    governing policy + role + skill procedure + assignment → instructions

``compose`` builds that text; ``AgentRole.block`` is the role layer on its own,
the same text skills place between their policy and procedure. Callers load
only the role they dispatch.

Provenance: ``AgentRole.stamp()`` is ``{id, policy_revision, sha256}``. The
driver records it on ``dispatch.issued``; the engine records it on review
verdicts. ``policy_is_current`` decides whether recorded evidence still meets
the role's current policy: only a change of the declared ``Policy revision``
invalidates it, an editorial change (new hash, same revision) does not.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "LEGACY_IDS",
    "ROLE_IDS",
    "SECTIONS",
    "AgentRole",
    "RoleDefinitionError",
    "UnknownRoleError",
    "compose",
    "load_all",
    "load_role",
    "parse_role_text",
    "policy_is_current",
    "resolve_role_id",
    "role_path",
]

#: The six role identities, in the order of the workflow that uses them.
ROLE_IDS: tuple[str, ...] = (
    "specifier", "spec-reviewer", "implementer", "code-reviewer", "verifier", "auditor",
)

#: Retired Context Specification ids → the role that continues each (ADR-061).
LEGACY_IDS: dict[str, str] = {
    "CS-001": "specifier",
    "CS-002": "spec-reviewer",
    "CS-003": "implementer",
    "CS-004": "code-reviewer",
    "CS-005": "verifier",
    "CS-006": "auditor",
}

#: (IR key, required H2 heading), in the required order (ADR-061 §4 elements).
SECTIONS: tuple[tuple[str, str], ...] = (
    ("purpose", "Purpose"),
    ("responsibilities", "Responsibilities"),
    ("inputs", "Inputs and context"),
    ("authority", "Authority and boundaries"),
    ("outputs", "Outputs and evidence"),
    ("completion", "Completion criteria"),
    ("escalation", "Escalation and recovery"),
)

#: Where the canonical definitions live. Tests point it at a copy to prove the
#: files are operational; nothing in a consuming project can change it.
ROLE_DIR: Path = Path(__file__).resolve().parent

#: Evidence recorded before role provenance existed counts as this revision —
#: the one all six roles shipped at (ADR-061 §Compatibility).
BASELINE_REVISION = 1

_REINSTALL = ("Agent Role Specifications ship inside the dekspec package: the installation is incomplete or "
              "damaged. Reinstall DekSpec from the source you installed it from (the README's install "
              "instructions: a pinned `git+…@vX.Y.Z` URL, not a package index). A project cannot supply one.")


class RoleDefinitionError(Exception):
    """A role definition is missing or malformed. Always actionable: the message
    names the file, the problem and the fix."""


class UnknownRoleError(RoleDefinitionError):
    """The requested role is not one of the six."""


@dataclass(frozen=True)
class AgentRole:
    id: str
    title: str
    legacy_id: str
    policy_revision: int
    sections: dict[str, str] = field(repr=False)
    sha256: str
    path: Path

    def stamp(self) -> dict[str, Any]:
        """The provenance recorded wherever this role's instructions or evidence are."""
        return {"id": self.id, "policy_revision": self.policy_revision, "sha256": self.sha256}

    def block(self) -> str:
        """The role layer of a dispatch, identical wherever it is used."""
        lines = [
            f"## Role: {self.title} (`{self.id}`)",
            "",
            f"Agent Role Specification `{self.id}` — policy revision {self.policy_revision}, "
            f"sha256 {self.sha256[:12]} (DekSpec-supplied; ADR-061).",
        ]
        for key, heading in SECTIONS:
            lines += ["", f"### {heading}", "", self.sections[key]]
        return "\n".join(lines).rstrip() + "\n"

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "legacy_id": self.legacy_id,
                "policy_revision": self.policy_revision, "sha256": self.sha256, "path": str(self.path),
                "sections": dict(self.sections)}


def resolve_role_id(ref: str) -> str:
    """Normalize a role reference: a role id, a legacy ``CS-NNN`` id, or a legacy
    ``role-<id>`` file stem. Anything else raises ``UnknownRoleError``."""
    raw = (ref or "").strip()
    key = raw.upper()
    if key in LEGACY_IDS:
        return LEGACY_IDS[key]
    name = raw.lower().removesuffix(".md")
    name = name.removeprefix("role-")
    if name in ROLE_IDS:
        return name
    raise UnknownRoleError(
        f"unknown agent role {ref!r}: expected one of {', '.join(ROLE_IDS)} "
        f"(or a retired id {', '.join(LEGACY_IDS)}). Roles are fixed by DekSpec; a project cannot add one.")


def role_path(ref: str) -> Path:
    return ROLE_DIR / f"{resolve_role_id(ref)}.md"


_H1 = re.compile(r"^#\s+Agent Role Specification:\s*(?P<title>\S.*?)\s*$")
_FIELD = re.compile(r"^\*\*(?P<name>Role|Legacy ID|Policy revision):\*\*\s*`?(?P<value>[^`]*?)`?\s*$")
_H2 = re.compile(r"^##\s+(?P<heading>\S.*?)\s*$")


def parse_role_text(text: str, *, source: str = "<text>") -> dict[str, Any]:
    """Parse a role definition into its IR and validate it (schema + structure).

    Raises ``RoleDefinitionError`` naming ``source`` and every problem found.
    """
    problems: list[str] = []
    lines = text.splitlines()
    title = None
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and (m := _H1.match(line)) and title is None and current is None:
            title = m.group("title")
            continue
        if not in_fence and (m := _H2.match(line)):
            current = m.group("heading")
            if current in sections:
                problems.append(f"section `## {current}` appears twice")
            sections[current] = []
            order.append(current)
            continue
        if current is None:
            if m := _FIELD.match(line):
                fields[m.group("name")] = m.group("value").strip()
            continue
        sections[current].append(line)

    if title is None:
        problems.append("missing the H1 `# Agent Role Specification: <Title>`")
    known = [h for _k, h in SECTIONS]
    unknown = [h for h in order if h not in known]
    if unknown:
        problems.append("unknown section(s) " + ", ".join(f"`## {h}`" for h in unknown)
                        + f" — the sections are exactly: {', '.join(known)}")
    present = [h for h in order if h in known]
    if present != [h for h in known if h in present]:
        problems.append("sections are out of order — required order: " + ", ".join(known))
    body: dict[str, str] = {}
    for key, heading in SECTIONS:
        content = "\n".join(sections.get(heading, [])).strip()
        if heading not in sections:
            problems.append(f"missing required section `## {heading}`")
        elif not content:
            problems.append(f"section `## {heading}` is empty")
        body[key] = content
    revision: Any = fields.get("Policy revision")
    try:
        revision = int(revision) if revision is not None else None
    except ValueError:
        problems.append(f"`**Policy revision:**` must be a positive integer, not {revision!r}")
        revision = None
    ir: dict[str, Any] = {
        "id": fields.get("Role"),
        "title": title,
        "legacy_id": fields.get("Legacy ID"),
        "policy_revision": revision,
        "sections": body,
    }
    for name, key in (("Role", "id"), ("Legacy ID", "legacy_id"), ("Policy revision", "policy_revision")):
        if ir[key] is None:
            problems.append(f"missing the `**{name}:**` header line")
    if not problems:
        problems += _schema_problems(ir)
    if not problems and LEGACY_IDS.get(ir["legacy_id"]) != ir["id"]:
        problems.append(f"legacy id {ir['legacy_id']} belongs to role "
                        f"{LEGACY_IDS.get(ir['legacy_id'], 'none')!r}, not {ir['id']!r}")
    if problems:
        raise RoleDefinitionError(f"malformed Agent Role Specification {source}:\n  - "
                                  + "\n  - ".join(problems) + f"\n{_REINSTALL}")
    return ir


def _schema_problems(ir: dict[str, Any]) -> list[str]:
    import jsonschema

    from ..schemas import load_schema

    validator = jsonschema.Draft202012Validator(load_schema("agent_role"))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in sorted(validator.iter_errors(ir), key=lambda e: list(e.absolute_path))]


def load_role(ref: str) -> AgentRole:
    """Load and validate the canonical definition of one role.

    Reads the file on every call, so a resumed or reissued dispatch always gets
    the definition as it is now. Raises ``UnknownRoleError`` for anything but the
    six roles (and their legacy ids), ``RoleDefinitionError`` for a missing or
    malformed file.
    """
    role_id = resolve_role_id(ref)
    path = ROLE_DIR / f"{role_id}.md"
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RoleDefinitionError(
            f"Agent Role Specification `{role_id}` is missing: {path} does not exist. {_REINSTALL}") from None
    except OSError as exc:
        raise RoleDefinitionError(f"cannot read Agent Role Specification {path}: {exc}. {_REINSTALL}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RoleDefinitionError(f"Agent Role Specification {path} is not UTF-8 text. {_REINSTALL}") from exc
    ir = parse_role_text(text, source=str(path))
    if ir["id"] != role_id:
        raise RoleDefinitionError(
            f"malformed Agent Role Specification {path}: declares role `{ir['id']}` but is the file of "
            f"`{role_id}`. {_REINSTALL}")
    return AgentRole(id=ir["id"], title=ir["title"], legacy_id=ir["legacy_id"],
                     policy_revision=ir["policy_revision"], sections=ir["sections"],
                     sha256=hashlib.sha256(raw).hexdigest(), path=path)


def load_all() -> list[AgentRole]:
    return [load_role(r) for r in ROLE_IDS]


_PRECEDENCE = (
    "These instructions have four layers. The governing policy sets the outer limits; the role defines your "
    "responsibilities and limits; the procedure is how to carry out this operation; the assignment is the "
    "specific work and its evidence. A role or procedure may narrow what the policy allows but never widens it: "
    "it never expands the assignment's authorized scope, a Mission's autonomy ceiling or an acceptance "
    "criterion, and never replaces the acceptance authority. Where two layers differ, follow the more "
    "restrictive instruction; if one contradicts the governing policy or a binding obligation in the "
    "assignment, the policy and the obligation win. Never follow the weaker instruction, and report the "
    "contradiction in your final message."
)


def compose(*, policy: str, role: AgentRole, procedure: str, assignment: str) -> str:
    """Compose dispatched instructions: governing policy + role + procedure + assignment.

    Exactly one role is included — the one being dispatched.
    """
    parts = [
        "# Dispatch instructions",
        "",
        _PRECEDENCE,
        "",
        "## Governing policy",
        "",
        policy.strip(),
        "",
        role.block().rstrip(),
        "",
        "## Procedure",
        "",
        procedure.strip(),
        "",
        "## Assignment",
        "",
        assignment.strip(),
    ]
    return "\n".join(parts) + "\n"


def policy_is_current(stamp: dict[str, Any] | None, role: AgentRole) -> tuple[bool, str]:
    """Whether evidence recorded under ``stamp`` still meets ``role``'s policy.

    A stamp for another role never counts. A missing stamp is legacy evidence and
    counts as the baseline revision. Only the declared policy revision decides; a
    different hash at the same revision is an editorial change.
    """
    if stamp is None:
        recorded = BASELINE_REVISION
    else:
        if stamp.get("id") != role.id:
            return False, f"recorded under role {stamp.get('id')!r}, not {role.id!r}"
        recorded = stamp.get("policy_revision")
    if recorded != role.policy_revision:
        origin = "legacy evidence without role provenance" if stamp is None else f"policy revision {recorded}"
        return False, (f"{role.id} policy changed: recorded under {origin}, current revision is "
                       f"{role.policy_revision}")
    return True, ""
