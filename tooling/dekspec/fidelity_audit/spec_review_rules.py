"""SPEC-REVIEW reviewer-dispatch audit-rule family (INT-141 / IB-126 / MSN-019 daughter C).

This module is the additive sibling family (ADR-011 Option B) that routes the
spec-reviewer review path into the fidelity-audit surface. It mirrors the
``prose_shape.prose_shape_rules(graph, profile)`` family entrypoint
(``prose_shape.py:494``): a single ``spec_review_rules(graph, profile)``
function that ``audit_linkage`` extends, returning a ``list[Finding]`` built
from the LOCKED AE-003 ``Finding`` dataclass (consumed verbatim — no parallel
record).

Provenance + scope:

  - It loads the ``spec-reviewer`` ContextSpec once
    (``dekspec/context-specs/role-spec-reviewer.md``, CS-002) via the LOCKED
    ``parse_context_spec`` reader (daughter A / INT-139) and invokes the LOCKED
    ``Reviewer().dispatch`` dispatcher (daughter B / INT-140, per IC-016) to
    demonstrate the wiring — but daughter B's ``spec-reviewer`` registry entry
    is a minimal inert stub that returns ``[]`` (it ships the abstraction, not
    rich per-role rules). Per IB-126 Open Issue (a), the actual
    finding-detection logic therefore lives HERE, in the family C owns: this
    module translates a concrete ``role-spec-reviewer.md`` §Escalation Triggers
    condition (the *missing-derivation-source* trigger — "the spec claims to
    derive from an Architecture Element or ADR absent from review scope") into a
    ``SPEC-REVIEW`` P2 ``Finding``.

  - Detection: for each in-scope spec artifact in the graph (WSes + ICs — the
    Spec-Reviewer's `Artifact Path Scope`), the family reads the artifact's
    declared governing Architecture Elements and emits one finding per
    referenced AE id that is absent from the spec graph (the spec derives from
    an AE not in review scope). This is the deterministic in-scope signal the
    registered family surfaces; it fires on the acceptance fixture's intentional
    ambiguity (a spec referencing an absent AE) without extending B's stub.

  - Severity: ALL ``SPEC-REVIEW`` findings emit at ``P2`` — the IC-016 default
    (forging decision (d): no per-rule promotion/demotion). ``profile``, when
    passed, is honored exactly as ``prose_shape_rules`` honors it (the
    ``audit_linkage`` profile-filter decides whether a consumer sees the
    findings; the rule itself emits unconditionally at the default).

  - Retro-scope: findings fire on the artifacts present in the audited graph —
    the family does NOT retro-sweep a LOCKED corpus on its own; per INT-141
    §Desired Outcome the audit surface is exercised at ``--analyze`` /
    ``audit doctor`` time over newly-authored / unlock-revised artifacts.
"""
from __future__ import annotations

from typing import Any

from ..constraint_compiler.graph import SpecGraph
from ..constraint_compiler.parser import parse_context_spec
from ..severity import P2, Severity
from .linkage import Finding

# The single family rule code the profiles register (mirrors the
# T-PROSE-* family's public code list). Sub-codes below are namespaced under
# this prefix and all stay at P2 (forging decision (d)).
SPEC_REVIEW_RULE_CODE: str = "SPEC-REVIEW"
SPEC_REVIEW_MISSING_DERIVATION_RULE: str = "SPEC-REVIEW/MISSING-DERIVATION-SOURCE"

# Every SPEC-REVIEW rule emits at the IC-016 default severity.
SPEC_REVIEW_SEVERITY: Severity = P2

# The spec-reviewer ContextSpec instance (CS-002) the family loads to honor
# the IC-016 dispatch path. Relative to ``graph.dekspec_dir``.
_SPEC_REVIEWER_CONTEXT_SPEC_RELPATH = ("context-specs", "role-spec-reviewer.md")


def _load_spec_reviewer_context_spec(graph: SpecGraph) -> dict[str, Any] | None:
    """Load the spec-reviewer ContextSpec (CS-002) via the LOCKED parser.

    Returns the parsed ``context_spec`` dict (``role_identity == "spec-reviewer"``)
    or ``None`` if the instance is not present in the audited tree (the family
    then still runs its own deterministic detection — the ContextSpec load is
    the IC-016 wiring demonstration, not a precondition for the finding).
    """
    dekspec_dir = getattr(graph, "dekspec_dir", None)
    if dekspec_dir is None:
        return None
    cs_path = dekspec_dir.joinpath(*_SPEC_REVIEWER_CONTEXT_SPEC_RELPATH)
    if not cs_path.exists():
        return None
    try:
        return parse_context_spec(cs_path)
    except Exception:
        # The ContextSpec load is best-effort wiring; a parse failure must not
        # crash the audit. Detection below is independent of the load result.
        return None


def _governing_aes(graph: SpecGraph, artifact: dict[str, Any]) -> list[str]:
    """Return the AE ids an in-scope spec artifact declares it derives from."""
    artifact_id = artifact.get("id", "")
    if artifact_id.startswith("WS-"):
        return graph.aes_of_ws(artifact_id)
    if artifact_id.startswith("IC-"):
        return graph.aes_of_ic(artifact_id)
    return []


def _spec_review_missing_derivation(graph: SpecGraph) -> list[Finding]:
    """Emit SPEC-REVIEW findings for the missing-derivation-source trigger.

    Mirrors the ``role-spec-reviewer.md`` §Escalation Triggers condition:
    "the spec claims to derive from an Architecture Element or ADR absent from
    review scope | action: escalate the missing-derivation-source condition".

    For each in-scope spec artifact (WS / IC) that declares a governing AE id
    not present in the spec graph, emit one ``SPEC-REVIEW`` P2 ``Finding``.
    """
    findings: list[Finding] = []
    in_scope: list[dict[str, Any]] = [*graph.wses(), *graph.ics()]
    for artifact in in_scope:
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
    """Run the SPEC-REVIEW reviewer-dispatch family against ``graph``.

    The single entrypoint ``audit_linkage`` calls (sibling to
    ``prose_shape.prose_shape_rules`` at ``linkage.py:159``). Signature mirrors
    ``prose_shape_rules(graph, profile)`` (``prose_shape.py:494``).

    Wiring (IC-016 / Open Issue (a)): loads the ``spec-reviewer`` ContextSpec
    (CS-002) via the LOCKED ``parse_context_spec`` and invokes the LOCKED
    ``Reviewer().dispatch(context_spec, artifact)`` to route the spec-reviewer
    review path. Daughter B's ``spec-reviewer`` registry stub is inert
    (returns ``[]``), so the deterministic finding-detection logic — translating
    a ``role-spec-reviewer.md`` §Escalation Triggers condition into a P2
    ``Finding`` — lives in this family (the new code C owns).

    All findings emit at ``P2`` (forging decision (d)). ``profile`` is accepted
    for signature parity with ``prose_shape_rules``; the ``audit_linkage``
    profile-filter governs visibility, exactly as for every other family.
    """
    findings: list[Finding] = []

    # IC-016 wiring demonstration: load the spec-reviewer ContextSpec and route
    # each in-scope artifact through Reviewer.dispatch. The dispatcher's
    # spec-reviewer stub is inert (returns []), so this contributes no findings
    # today — but it exercises the LOCKED dispatch path the family is built on.
    context_spec = _load_spec_reviewer_context_spec(graph)
    if context_spec is not None and context_spec.get("role_identity") == "spec-reviewer":
        # Lazy import keeps the fidelity_audit package importable even if the
        # spec_review package is absent in a stripped-down tree.
        from dekspec.spec_review.reviewer import Reviewer

        reviewer = Reviewer()
        for artifact in (*graph.wses(), *graph.ics()):
            dispatched = reviewer.dispatch(context_spec, artifact)
            # Normalize any dispatched finding to the SPEC-REVIEW family code +
            # P2 (the family code the profile registers). Inert today.
            for f in dispatched:
                findings.append(
                    Finding(
                        severity=SPEC_REVIEW_SEVERITY,
                        rule=SPEC_REVIEW_RULE_CODE,
                        artifact_id=f.artifact_id,
                        message=f.message,
                        fix_kind=f.fix_kind,
                        file_path=f.file_path,
                    )
                )

    # The deterministic in-scope detection the registered family owns: the
    # missing-derivation-source escalation trigger (Open Issue (a)).
    findings.extend(_spec_review_missing_derivation(graph))

    return findings


__all__ = [
    "SPEC_REVIEW_RULE_CODE",
    "SPEC_REVIEW_MISSING_DERIVATION_RULE",
    "SPEC_REVIEW_SEVERITY",
    "spec_review_rules",
]
