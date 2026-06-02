"""Fidelity audit — Python implementation of the artifact-graph consistency checks.

v0.3.0 first cut: linkage integrity (L-series) checks. Other check
families (T-series template, D-series drift, E-series extraction-landing)
remain in the `/fidelity-audit` skill until they're ported.

Public API:
  - audit_linkage(repo_root) -> list[Finding]
  - Finding (dataclass)
"""

from .linkage import (
    Finding,
    Fix,
    apply_fixes,
    apply_status_fixes,
    audit_linkage,
    propose_fixes,
)

__all__ = [
    "Finding",
    "Fix",
    "audit_linkage",
    "propose_fixes",
    "apply_fixes",
    "apply_status_fixes",
]
