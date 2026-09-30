"""The IB as a work contract (ADR-055 / ADR-056).

Wraps the Constraint Compiler's IB IR — the single parsing path — in the
view the execution engine needs: which content is binding, what acceptance
requires, which surfaces are protected, and a *contract hash* over exactly
the binding and acceptance content. The implementation hypothesis, open
issues and lifecycle bookkeeping are deliberately outside the hash: revising
a guess, or recording completion, must not invalidate evidence.

Legacy IBs (authored under ADR-049) keep their restrictive meaning here:
Files to Modify is the allowed scope (exact paths, not globs), Do Not Touch
is protected, and there is no executable acceptance contract — a legacy IB
must be adopted before it can complete through the evidence gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dekspec.constraint_compiler.parser import IBParseError, parse_ib

__all__ = [
    "AcceptanceCondition",
    "ContractError",
    "IBContract",
    "find_ib_path",
    "load_contract",
    "pytest_node_file",
]

_IB_ID = re.compile(r"^IB-\d{3,}$")
_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")


class ContractError(RuntimeError):
    """The IB cannot be located, parsed, or used as an execution contract."""


@dataclass(frozen=True)
class AcceptanceCondition:
    id: str
    condition: str
    kind: str  # pytest | command | review
    nodes: tuple[str, ...] = ()
    command: str | None = None
    review: str | None = None
    timeout: int | None = None

    @classmethod
    def from_ir(cls, raw: dict[str, Any]) -> AcceptanceCondition:
        verify = raw["verify"]
        if "pytest" in verify:
            return cls(raw["id"], raw["condition"], "pytest", nodes=tuple(verify["pytest"]),
                       timeout=raw.get("timeout"))
        if "command" in verify:
            return cls(raw["id"], raw["condition"], "command", command=verify["command"],
                       timeout=raw.get("timeout"))
        return cls(raw["id"], raw["condition"], "review", review=verify["review"])

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "condition": self.condition, "kind": self.kind}
        if self.nodes:
            out["nodes"] = list(self.nodes)
        if self.command:
            out["command"] = self.command
        if self.review:
            out["review"] = self.review
        return out


def pytest_node_file(node: str) -> str:
    """`tests/test_x.py::TestA::test_b[p]` → `tests/test_x.py`."""
    return node.split("::", 1)[0]


@dataclass(frozen=True)
class IBContract:
    ib_id: str
    path: Path
    rel_path: str
    name: str
    status: str
    authority_policy: str
    parent: str | None
    depends_on: tuple[str, ...]
    spec_impact: tuple[str, ...]
    scope: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    obligations: tuple[dict[str, Any], ...]
    protected: tuple[str, ...]
    acceptance: tuple[AcceptanceCondition, ...]
    declared_assets: tuple[str, ...]
    hypothesis: tuple[str, ...]
    prerequisites: tuple[dict[str, Any], ...]
    parse_warnings: tuple[dict[str, Any], ...]
    ir: dict[str, Any] = field(repr=False)

    @property
    def is_delegated(self) -> bool:
        return self.authority_policy == "delegated"

    def acceptance_asset_paths(self) -> list[str]:
        files = {pytest_node_file(n) for c in self.acceptance for n in c.nodes}
        files.update(self.declared_assets)
        return sorted(files)

    def binding_view(self) -> dict[str, Any]:
        """The content whose change is a contract change (hashed)."""
        ir = self.ir
        if self.is_delegated:
            keys = ("authority_policy", "outcome", "scope", "out_of_scope", "obligations",
                    "protected_surfaces", "acceptance", "acceptance_assets", "depends_on",
                    "spec_impact")
        else:
            keys = ("authority_policy", "goal", "files_to_modify", "do_not_touch",
                    "constraints_and_decisions", "domain_constraints", "done_when",
                    "out_of_scope", "depends_on")
        view = {k: ir.get(k) for k in keys if ir.get(k) not in (None, [], "")}
        if not self.is_delegated and self.protected:
            view["protected"] = list(self.protected)
        return view

    def contract_hash(self) -> str:
        blob = json.dumps(self.binding_view(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def contract_problems(self) -> list[str]:
        """Why this IB cannot be executed under the delegated policy (empty = usable)."""
        problems: list[str] = []
        if not self.is_delegated:
            problems.append(
                "legacy authority policy — adopt the IB (ADR-055) before evidence-backed execution"
            )
            return problems
        if not self.ir.get("outcome"):
            problems.append("§Outcome is empty")
        if not self.scope:
            problems.append("§Scope names no allowed globs")
        if not self.acceptance:
            problems.append("§Acceptance has no valid acceptance conditions")
        for w in self.parse_warnings:
            if w.get("severity") == "warning":
                problems.append(f"{w.get('field')}: {w.get('reason')}")
        return problems


def _legacy_protected(text: str) -> list[str]:
    """Do Not Touch in legacy IBs is usually a `| Function/File | Reason |` table."""
    m = re.search(r"^## Do Not Touch\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    out: list[str] = []
    seen_sep = False
    for line in m.group(1).splitlines():
        row = _TABLE_ROW.match(line.strip())
        if not row:
            continue
        cells = [c.strip() for c in row.group(1).split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            seen_sep = True
            continue
        if not seen_sep or not cells or not cells[0]:
            continue
        token = re.findall(r"`([^`]+)`", cells[0])
        out.extend(token or [cells[0]])
    return out


def find_ib_path(repo_root: Path, ref: str, *, spec_root: str = "dekspec") -> Path:
    """Resolve an IB id or path. Ambiguous ids (duplicated across Working
    Specs in legacy trees) must be given as a path."""
    candidate = Path(ref)
    if not candidate.is_absolute():
        candidate = Path(repo_root) / ref
    if candidate.suffix == ".md" and candidate.is_file():
        return candidate.resolve()
    if not _IB_ID.match(ref):
        raise ContractError(f"{ref!r} is neither an IB id (IB-NNN) nor an existing IB file")
    base = Path(repo_root) / spec_root / "impl-briefs"
    matches = sorted(base.rglob(f"{ref}-*.md")) if base.is_dir() else []
    if not matches:
        raise ContractError(f"no IB file for {ref} under {base}")
    if len(matches) > 1:
        listing = ", ".join(str(m.relative_to(repo_root)) for m in matches)
        raise ContractError(f"{ref} is ambiguous ({listing}); pass the IB path instead")
    return matches[0].resolve()


def load_contract(repo_root: Path, ref: str, *, spec_root: str = "dekspec") -> IBContract:
    repo_root = Path(repo_root).resolve()
    path = find_ib_path(repo_root, ref, spec_root=spec_root)
    try:
        ir = parse_ib(path)
    except IBParseError as exc:
        raise ContractError(f"{path.name}: {exc}") from exc
    text = path.read_text(encoding="utf-8")
    delegated = ir.get("authority_policy") == "delegated"
    if delegated:
        scope = tuple(s["glob"] for s in ir.get("scope", []))
        protected = tuple(s["surface"] for s in ir.get("protected_surfaces", []))
    else:
        scope = tuple(
            f["file"].strip("`") for f in ir.get("files_to_modify", []) if f.get("file")
        )
        protected = tuple(ir.get("do_not_touch") or _legacy_protected(text))
    parent = (ir.get("parent") or {}).get("id")
    if not parent:
        parent = (ir.get("intent") or {}).get("id") or (ir.get("spec") or {}).get("id")
    return IBContract(
        ib_id=ir["id"],
        path=path,
        rel_path=str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path),
        name=ir["name"],
        status=ir["status"],
        authority_policy=ir.get("authority_policy", "legacy"),
        parent=parent,
        depends_on=tuple(ir.get("depends_on", [])),
        spec_impact=tuple(ir.get("spec_impact", [])),
        scope=scope,
        out_of_scope=tuple(ir.get("out_of_scope", [])),
        obligations=tuple(ir.get("obligations", [])),
        protected=protected,
        acceptance=tuple(AcceptanceCondition.from_ir(a) for a in ir.get("acceptance", [])),
        declared_assets=tuple(ir.get("acceptance_assets", [])),
        hypothesis=tuple(ir.get("implementation_hypothesis", [])),
        prerequisites=tuple(ir.get("environment_prerequisites", [])),
        parse_warnings=tuple(ir.get("parse_warnings", [])),
        ir=ir,
    )
