"""SPEC-REVIEW audit-rule family (INT-141 / IB-126; revised by ADR-061).

A single family entrypoint, ``spec_review_rules(graph, profile)``, that
``audit_linkage`` extends, mirroring ``prose_shape.prose_shape_rules``. It
returns LOCKED AE-003 ``Finding`` records, all at ``P2`` (IC-016's default
emit severity, kept).

Detection is deterministic: for each Working Spec and Interface Contract in the
graph, one finding per governing Architecture Element id that the graph does
not contain — the spec claims to derive from an AE absent from review scope.
That is the spec-reviewer role's missing-derivation-source escalation, which a
rule can detect without an agent.

What changed with ADR-061: the family used to load the spec-reviewer Context
Specification on a best-effort basis and route every artifact through the
IC-016 ``Reviewer.dispatch`` placeholder, whose spec-reviewer handler returned
nothing. That wiring decided nothing and is gone. Judgment-based spec review is
a dispatched agent composed from the spec-reviewer Agent Role Specification
(``dekspec.roles``); this deterministic audit consumes no role definition, so
it runs whether or not one could be read.

Retro-scope: findings fire on the artifacts present in the audited graph; the
family does not retro-sweep a LOCKED corpus on its own (INT-141 §Desired
Outcome).
"""
from __future__ import annotations

from typing import Any

from ..constraint_compiler.graph import SpecGraph
from ..severity import P2, Severity
from .linkage import Finding

# The single family rule code the profiles register. Sub-codes are namespaced
# under it and all stay at P2.
SPEC_REVIEW_RULE_CODE: str = "SPEC-REVIEW"
SPEC_REVIEW_MISSING_DERIVATION_RULE: str = "SPEC-REVIEW/MISSING-DERIVATION-SOURCE"

# Every SPEC-REVIEW rule emits at the IC-016 default severity.
SPEC_REVIEW_SEVERITY: Severity = P2


def _governing_aes(graph: SpecGraph, artifact: dict[str, Any]) -> list[str]:
    """Return the AE ids an in-scope spec artifact declares it derives from."""
    artifact_id = artifact.get("id", "")
    if artifact_id.startswith("WS-"):
        return graph.aes_of_ws(artifact_id)
    if artifact_id.startswith("IC-"):
        return graph.aes_of_ic(artifact_id)
    return []


def _spec_review_missing_derivation(graph: SpecGraph) -> list[Finding]:
    """One P2 finding per (WS or IC, governing AE absent from the graph)."""
    findings: list[Finding] = []
    for artifact in (*graph.wses(), *graph.ics()):
        artifact_id = artifact.get("id", "")
        for ae_id in _governing_aes(graph, artifact):
            if not graph.has(ae_id):
                findings.append(
                    Finding(
                        severity=SPEC_REVIEW_SEVERITY,
                        rule=SPEC_REVIEW_RULE_CODE,
                        artifact_id=artifact_id,
                        message=(
                            f"Spec-Reviewer escalation "
                            f"[{SPEC_REVIEW_MISSING_DERIVATION_RULE}]: "
                            f"{artifact_id} claims to derive from {ae_id}, which "
                            "is absent from review scope. Escalate the "
                            "missing-derivation-source condition rather than "
                            "approving on assumption."
                        ),
                        fix_kind="semantic",
                    )
                )
    return findings


def spec_review_rules(graph: SpecGraph, profile: Any = None) -> list[Finding]:
    """Run the SPEC-REVIEW family against ``graph``.

    ``profile`` is accepted for signature parity with ``prose_shape_rules``; the
    ``audit_linkage`` profile filter governs visibility, as for every family.
    """
    return _spec_review_missing_derivation(graph)


__all__ = [
    "SPEC_REVIEW_RULE_CODE",
    "SPEC_REVIEW_MISSING_DERIVATION_RULE",
    "SPEC_REVIEW_SEVERITY",
    "spec_review_rules",
]
