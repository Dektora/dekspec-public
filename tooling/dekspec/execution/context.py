"""Generated execution context for one IB (ADR-055 / ADR-056 §6).

The packet is a *derived snapshot*: the IB contract plus the current text of
every obligation it references, each tagged with source path, status and
content hash, under an explicit precedence order. It is regenerated on every
dispatch and never edited; its manifest hash is recorded with the run and
with every piece of evidence, so a later change to any source is detected as
staleness instead of silently diverging from a copied constraint.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dekspec.execution.contract import IBContract
from dekspec.execution.references import ResolvedObligation, resolve_obligations
from dekspec.specification_policy import ReferencePolicyError

__all__ = ["ContextPacket", "build_context", "manifest_digest"]

PRECEDENCE = (
    "1. Binding obligations (below, with their canonical text) and Protected Surfaces — preserve them.",
    "2. Acceptance conditions — demonstrate them; never weaken, skip or reinterpret them.",
    "3. Implementation hypothesis — a starting guess; investigate the repository and revise it within Scope.",
    "4. Everything else you read (history, drafts, superseded decisions, other IBs) informs but never binds.",
)

ESCALATE_WHEN = (
    "a binding obligation or protected surface would have to change",
    "a change is needed outside Scope (scope expansion)",
    "an acceptance condition looks wrong, unsatisfiable or would need weakening",
    "obligations contradict each other or the existing system in a way the contract does not settle",
    "the outcome or an obligation cannot be determined from the policy-eligible canonical sources (underdefined contract)",
    "a required prerequisite or authority is missing",
)

LEGACY_RULES = (
    "This IB was authored under ADR-049 and keeps that meaning (authority policy: legacy).",
    "Files to Modify is the allowlist: stop and escalate before changing any other file.",
    "Constraints & Decisions and Do Not Touch are binding; resolve residual ambiguity in the IB's Precedence order.",
    "It has no executable acceptance contract; it cannot complete through `dekspec ib complete` until adopted.",
)


def manifest_digest(manifest: list[dict[str, Any]]) -> str:
    blob = json.dumps(sorted(manifest, key=lambda e: e["obligation"]), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class ContextPacket:
    contract: IBContract
    obligations: list[ResolvedObligation]
    policy_error: str | None = None

    @property
    def problems(self) -> list[str]:
        return ([self.policy_error] if self.policy_error else []) + [f"{o.id}: {o.problem}" for o in self.obligations if o.problem]

    @property
    def manifest(self) -> list[dict[str, Any]]:
        return [o.manifest_entry() for o in self.obligations]

    @property
    def manifest_hash(self) -> str:
        return manifest_digest(self.manifest)

    def as_dict(self) -> dict[str, Any]:
        c = self.contract
        result = {
            "ib": c.ib_id,
            "path": c.rel_path,
            "status": c.status,
            "authority_policy": c.authority_policy,
            "contract_hash": c.contract_hash(),
            "manifest_hash": self.manifest_hash,
            "precedence": list(PRECEDENCE) if c.is_delegated else list(LEGACY_RULES),
            "escalate_when": list(ESCALATE_WHEN),
            "outcome": c.ir.get("outcome") or c.ir.get("goal"),
            "rationale": c.ir.get("rationale"),
            "parent": c.parent,
            "scope": list(c.scope),
            "out_of_scope": list(c.out_of_scope),
            "protected_surfaces": list(c.protected),
            "spec_impact": list(c.spec_impact),
            "obligations": [
                {**o.manifest_entry(), "note": o.note, "text": o.text, "problem": o.problem}
                for o in self.obligations
            ],
            "acceptance": [a.as_dict() for a in c.acceptance],
            "acceptance_assets": c.acceptance_asset_paths(),
            "implementation_hypothesis": list(c.hypothesis),
            "environment_prerequisites": list(c.prerequisites),
            "problems": self.problems,
        }
        advisories = [{"obligation": o.id, "ref": o.ref, "status": o.status, "detail": o.advisory}
                      for o in self.obligations if o.advisory]
        if advisories:
            result["advisories"] = advisories
        return result

    def render_markdown(self) -> str:
        d = self.as_dict()
        c = self.contract
        out: list[str] = [
            f"# Execution context — {c.ib_id}: {c.name}",
            "",
            f"Generated from `{c.rel_path}` (status {c.status}, authority policy **{c.authority_policy}**). "
            f"Contract hash `{d['contract_hash'][:12]}`, source manifest `{d['manifest_hash'][:12]}`. "
            "This is a derived snapshot — do not edit it; change the sources and regenerate.",
            "",
            "## Precedence",
            "",
            *d["precedence"],
            "",
            "## Outcome",
            "",
            d["outcome"] or "(none stated)",
        ]
        if d["rationale"]:
            out += ["", "## Rationale", "", d["rationale"]]
        out += ["", "## Scope (allowed change surface)", ""]
        out += [f"- `{g}`" for g in d["scope"]] or ["- (none)"]
        if d["out_of_scope"]:
            out += ["", "Out of scope:", *[f"- {x}" for x in d["out_of_scope"]]]
        out += ["", "## Protected surfaces (never modify, rename or delete)", ""]
        out += [f"- `{p}`" for p in d["protected_surfaces"]] or ["- (none)"]
        if d["spec_impact"]:
            out += ["", "## Governing specifications this change must update", "",
                    *[f"- {s}" for s in d["spec_impact"]]]
        out += ["", "## Binding obligations", ""]
        if not self.obligations:
            out.append("(none referenced)")
        for o in self.obligations:
            src = "local to this IB" if o.ref == "local" else f"{o.ref}{' §' + o.section if o.section else ''} — `{o.path}` ({o.status})"
            out += [f"### {o.id} — {src}", ""]
            if o.problem:
                out += [f"**UNRESOLVED:** {o.problem}", ""]
                continue
            if o.advisory:
                out += [f"**ADVISORY:** {o.advisory}", ""]
            if o.note:
                out += [f"*Applies here:* {o.note}", ""]
            out += [f"<!-- sha256 {o.sha256} -->", o.text, ""]
        out += ["## Acceptance conditions (demonstrate; never weaken)", ""]
        for a in d["acceptance"]:
            how = a.get("nodes") or a.get("command") or f"independent review: {a.get('review')}"
            out.append(f"- **{a['id']}** {a['condition']} — verified by: {how}")
        if d["acceptance_assets"]:
            out += ["", "Protected acceptance assets: " + ", ".join(f"`{p}`" for p in d["acceptance_assets"])]
        out += ["", "## Implementation hypothesis (revisable)", ""]
        out += [f"- {h}" for h in d["implementation_hypothesis"]] or ["- (none — investigate and plan)"]
        out += [
            "",
            "## How to work",
            "",
            "- Investigate first: read the code, contracts and reusable capabilities relevant to the outcome; "
            "record findings with `dekspec ib plan` before committing a plan.",
            "- Revise the hypothesis freely inside Scope; departures are recorded automatically as deviations.",
            "- Record attempts (`dekspec ib attempt <IB> start|end`), run `dekspec ib verify <IB>`, and stop when blocked — "
            "a blocked outcome is truthful, not a failure to hide.",
            "",
            "## Escalate (stop and ask) only when",
            "",
            *[f"- {e}" for e in d["escalate_when"]],
        ]
        if d["problems"]:
            out += ["", "## Problems — dispatch is blocked until fixed", "", *[f"- {p}" for p in d["problems"]]]
        return "\n".join(out) + "\n"


def build_context(repo_root: Path, contract: IBContract, *, spec_root: str = "dekspec") -> ContextPacket:
    try:
        return ContextPacket(contract, resolve_obligations(repo_root, contract, spec_root=spec_root))
    except ReferencePolicyError as exc:
        return ContextPacket(contract, [], policy_error=str(exc))
