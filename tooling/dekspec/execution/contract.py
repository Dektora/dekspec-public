"""Hides policy, binding and switch rules; load_contract(root, ref) returns IBContract with is_lean/is_executable, risk, design_intent and contract_hash().
contract_problems(*, settings=None) returns all named structural problems; optional ExecutionSettings adds execution-policy problems, including "lean is switched off", without hiding structural faults or changing other policies.
Only this question combines policy and switch; callers never parse either, and may supply base-loaded settings or omit settings for configuration-free reads; queries have no effects.
Missing/unknown policy becomes legacy with a warning; lean defects are problems, while unreadable briefs remain ContractError.
Alternatives: raw IR/caller checks, policy subclasses or a separate enabled predicate; the existing contract view wins by answering structure and execution together without new types or caller policy."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dekspec.brief_identity import BriefIdentityError, resolve_brief
from dekspec.constraint_compiler.parser import IBParseError, parse_ib

__all__ = [
    "AcceptanceCondition",
    "ContractError",
    "IBContract",
    "find_ib_path",
    "load_contract",
    "pytest_node_file",
]

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
    test_files: tuple[str, ...] | None = None

    @classmethod
    def from_ir(cls, raw: dict[str, Any]) -> AcceptanceCondition:
        verify = raw["verify"]
        if "pytest" in verify:
            return cls(raw["id"], raw["condition"], "pytest", nodes=tuple(verify["pytest"]),
                       timeout=raw.get("timeout"))
        if "command" in verify:
            return cls(raw["id"], raw["condition"], "command", command=verify["command"],
                       timeout=raw.get("timeout"),
                       test_files=tuple(verify["test_files"]) if "test_files" in verify else None)
        return cls(raw["id"], raw["condition"], "review", review=verify["review"])

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "condition": self.condition, "kind": self.kind}
        if self.nodes:
            out["nodes"] = list(self.nodes)
        if self.command:
            out["command"] = self.command
        if self.test_files is not None:
            out["test_files"] = list(self.test_files)
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

    @property
    def is_lean(self) -> bool:
        """Whether this contract uses lean authority."""
        return self.authority_policy == "lean"

    @property
    def is_executable(self) -> bool:
        """Whether this contract uses an executable authority policy."""
        return self.is_delegated or self.is_lean

    @property
    def risk(self) -> str | None:
        """The lean Risk line, absent when not supplied."""
        return self.ir.get("risk")

    @property
    def design_intent(self) -> str:
        """Lean Design intent text, unchanged."""
        return self.ir.get("design_intent", "")

    def acceptance_asset_paths(self) -> list[str]:
        files = {pytest_node_file(n) for c in self.acceptance for n in c.nodes}
        files.update(self.declared_assets)
        files.update(p for c in self.acceptance for p in (c.test_files or ()))
        return sorted(files)

    def binding_view(self) -> dict[str, Any]:
        """The content whose change is a contract change (hashed)."""
        ir = self.ir
        if self.is_executable:
            keys = ("authority_policy", "outcome", "scope", "out_of_scope", "obligations",
                    "protected_surfaces", "acceptance", "acceptance_assets", "depends_on",
                    "spec_impact")
        else:
            keys = ("authority_policy", "goal", "files_to_modify", "do_not_touch",
                    "constraints_and_decisions", "domain_constraints", "done_when",
                    "out_of_scope", "depends_on")
        if self.is_lean:
            keys += ("risk", "design_intent")
        view = {k: ir.get(k) for k in keys if ir.get(k) not in (None, [], "")}
        if not self.is_executable and self.protected:
            view["protected"] = list(self.protected)
        return view

    def contract_hash(self) -> str:
        blob = json.dumps(self.binding_view(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def contract_problems(self, *, settings=None) -> list[str]:
        """Why this IB cannot be executed under the delegated policy (empty = usable)."""
        problems: list[str] = []
        if not self.is_executable:
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
        if self.is_lean:
            if settings is not None and not settings.lean:
                problems.append("lean is switched off")
            if self.risk != "normal":
                problems.append("Risk must be normal; high, missing and unknown Risk are not supported")
            if not self.design_intent.strip():
                problems.append("§Design intent is missing or blank")
            if not any(c.kind == "pytest" for c in self.acceptance):
                problems.append("lean acceptance needs a pytest condition")
            integration = " ".join((settings.integration_command or "").split()) if settings else ""
            for condition in self.acceptance:
                for node in condition.nodes:
                    if not pytest_node_file(node).endswith(".py"):
                        problems.append(f"{condition.id}: pytest node must name a .py file: {node}")
                command = " ".join((condition.command or "").split())
                if command and ("check-product.py" in command or (integration and integration in command)):
                    problems.append(f"{condition.id}: whole-suite command is not a lean acceptance condition")
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
    try:
        return resolve_brief(repo_root, ref, spec_root=spec_root).path
    except BriefIdentityError as exc:
        raise ContractError(str(exc)) from exc


def load_contract(repo_root: Path, ref: str, *, spec_root: str = "dekspec") -> IBContract:
    repo_root = Path(repo_root).resolve()
    path = find_ib_path(repo_root, ref, spec_root=spec_root)
    try:
        ir = parse_ib(path)
    except IBParseError as exc:
        raise ContractError(f"{path.name}: {exc}") from exc
    text = path.read_text(encoding="utf-8")
    delegated = ir.get("authority_policy") in ("delegated", "lean")
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
