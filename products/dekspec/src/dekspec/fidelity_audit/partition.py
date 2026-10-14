"""The partition rule family: registry, fingerprint and severity ceiling (IB-220).

Surface skeleton (ADR-062), written with IB-220's acceptance tests: the public
interface IB-220 O-20 contracts, with no behavior yet. The registry is empty,
``fingerprint`` returns an empty string, ``resolve_severity`` returns no
severity and ``register`` records nothing. IB-220's implementation replaces the
bodies within the brief's Scope.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["PARTITION_RULES", "fingerprint", "register", "resolve_severity"]

#: Rule id -> registration record (``rule``, ``record_item``, ``action``,
#: ``destination_type``, ``fixing_skill``). Skeleton: no rule registered yet.
PARTITION_RULES: Mapping[str, Any] = {}


def fingerprint(rule: str, artifact: str, subject: str) -> str:
    """The finding fingerprint of WS-035 §Fingerprint (skeleton: empty)."""
    return ""


def resolve_severity(rule: str, profile: Any) -> tuple[str, str | None]:
    """A partition rule's severity under ``profile`` and any warning (skeleton: none)."""
    return ("", None)


def register(rule_record: Any) -> None:
    """Add a rule to the family (skeleton: records nothing)."""
    return None
