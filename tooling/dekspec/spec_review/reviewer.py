"""Role-keyed spec-review dispatcher (IC-016 / INT-140 / MSN-019).

This package is a brand-new top-level sibling under ``tooling/dekspec/``
(ADR-011 Option B): it references NOTHING in the LOCKED MSN-017
``tooling/dekspec/review/`` SQLite review-flywheel substrate. The two
packages are independent.

``Reviewer`` is the IO-free dispatcher pinned by IC-016 §Interface
Definition. The review kind is NOT a constructor/parameter argument: it is
resolved at dispatch time from ``context_spec["role_identity"]`` against the
six canonical role identities. ``Reviewer<ArtifactType>`` is a conceptual
parameterization realized by role-keyed dispatch, not a Python generic type
argument.

This module is the bead-1 RED skeleton: the signature surface is complete,
but ``dispatch`` is intentionally non-functional (raises
``NotImplementedError``) so the strong-TDD outcome test lands RED. The
functional route-or-raise body + per-kind stub bodies land in bead 2
(ds-r8d1); the error/boundary semantics land in bead 3.
"""

from __future__ import annotations

from typing import Callable

# Finding shape reused VERBATIM (IC-016 §Shared Conventions; ADR-011 Option
# B additive read-only): consume the LOCKED record, never define a parallel
# spec-review finding type.
from dekspec.fidelity_audit.linkage import Finding

# Canonical Severity literal (severity.py:53; ADR-013). Imported for the
# DEFAULT_SEVERITY annotation only — consumed read-only.
from dekspec.severity import Severity

# Default emit severity for spec-review findings (IC-016 §Shared
# Conventions; ADR-013). Per-kind stub bodies (bead 2) construct Findings at
# this severity unless a rule pins otherwise.
DEFAULT_SEVERITY: Severity = "P2"

# The six canonical role identities the dispatcher routes on. Mirrors the
# six dekspec/context-specs/role-*.md instances (daughter A / INT-139).
CANONICAL_ROLE_IDENTITIES: frozenset[str] = frozenset(
    {
        "specifier",
        "spec-reviewer",
        "implementer",
        "code-reviewer",
        "verifier",
        "auditor",
    }
)


class UnknownReviewerRoleError(Exception):
    """Raised when ``context_spec["role_identity"]`` names no known reviewer.

    Defined here (IC-016 §Error Semantics) so the signature surface is
    complete; the route-or-raise body that actually raises it lands in bead
    3. Re-exported from the package ``__init__``.
    """


# ---------------------------------------------------------------------------
# Per-kind reviewer stubs (bead 2 / ds-r8d1).
#
# IB-125 scope is the *abstraction*: these per-kind reviewers are MINIMAL
# STUBS, not the rich per-role review-rule bodies (those extend the registry
# later — daughter C + future per-kind rules). Each stub takes the same
# ``(context_spec, artifact)`` shape and returns a correctly-typed
# ``list[Finding]``. The ``code-reviewer`` stub constructs ≥1 real ``Finding``
# at ``DEFAULT_SEVERITY`` so the strong-TDD outcome test asserts a non-empty
# finding-shape on a real return path; the other stubs return empty lists
# (still correctly typed) until their rule bodies land.
# ---------------------------------------------------------------------------


def _artifact_id_of(context_spec: dict) -> str:
    """Best-effort artifact id for a stub Finding (IO-free).

    The artifact-under-review is opaque to the abstraction-only stubs, so we
    derive a stable id from the ContextSpec dict. ``id`` (the ``CS-NNN``
    ContextSpec id) is always present on a ``parse_context_spec`` result.
    """
    return str(context_spec.get("id") or context_spec.get("role_identity", "unknown"))


def _review_code_reviewer(context_spec: dict, artifact) -> list[Finding]:
    """Minimal ``code-reviewer`` stub: emit one real ``P2`` Finding.

    Abstraction-only (IB-125): the real code-review rules land later. This
    stub proves the dispatch return path constructs a genuine AE-003
    ``Finding`` at the dispatcher's default emit severity (IC-016 §Shared
    Conventions).
    """
    return [
        Finding(
            severity=DEFAULT_SEVERITY,
            rule="spec-review/code-reviewer/stub",
            artifact_id=_artifact_id_of(context_spec),
            message=(
                "code-reviewer dispatch stub: per-role review rules not yet "
                "implemented (IB-125 abstraction-only; rule bodies land later)."
            ),
        )
    ]


def _review_empty(context_spec: dict, artifact) -> list[Finding]:
    """Minimal stub for the remaining roles: correctly-typed empty result.

    Abstraction-only (IB-125): these roles' review-rule bodies are not in
    scope for INT-140. The stub returns an empty ``list[Finding]`` on the real
    return path so the registry is uniformly shaped + extensible.
    """
    return []


# Registry (IC-016 §Open Issues — settled here as a dict registry): a
# module-level mapping keyed by the six canonical role identities. Extended in
# place by daughter C + future per-kind rules; ``dispatch`` routes on
# ``context_spec["role_identity"]`` through this table.
_REVIEWER_REGISTRY: dict[str, Callable[[dict, object], list[Finding]]] = {
    "code-reviewer": _review_code_reviewer,
    "specifier": _review_empty,
    "spec-reviewer": _review_empty,
    "implementer": _review_empty,
    "verifier": _review_empty,
    "auditor": _review_empty,
}


class Reviewer:
    """Role-keyed, IO-free spec-review dispatcher (IC-016 §Interface Definition).

    ``Reviewer<ArtifactType>`` conceptually; the runtime selector is
    ``context_spec["role_identity"]``, not a ``typing.Generic`` argument.
    """

    def dispatch(self, context_spec: dict, artifact) -> list[Finding]:
        """Route ``artifact`` to the role-keyed reviewer (IC-016 §Interface Definition).

        Pinned signature: ``(self, context_spec: dict, artifact) -> list[Finding]``.
        There is NO ``artifact_kind`` parameter — the review kind is resolved
        from ``context_spec["role_identity"]``. IO-free: performs no file IO;
        both inputs arrive already loaded.

        Routes on ``context_spec["role_identity"]`` to a per-role reviewer in
        ``_REVIEWER_REGISTRY`` and returns its ``list[Finding]`` unchanged. A
        ``role_identity`` with no registered reviewer raises
        ``UnknownReviewerRoleError`` (IC-016 §Error Semantics — an unrouted
        review is a defect, never a silent empty list).
        """
        role_identity = context_spec["role_identity"]
        reviewer = _REVIEWER_REGISTRY.get(role_identity)
        if reviewer is None:
            raise UnknownReviewerRoleError(
                f"No reviewer registered for role_identity {role_identity!r}; "
                f"known roles: {sorted(_REVIEWER_REGISTRY)}."
            )
        return reviewer(context_spec, artifact)
