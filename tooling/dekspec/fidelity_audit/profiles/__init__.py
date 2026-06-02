"""Audit profile registry — F-3 phase 2.

A profile is a named, versioned bundle of audit-rule codes + parameter
overrides. Today's audit engine (`linkage.py`) implements 50 rule codes;
the v1 profile (`profiles/v1.yaml`) enumerates every one of them and is
the default for any artifact whose `audit_profile` field is absent or
equals "v1".

Future profiles (v2, v3, ...) inherit from a parent and may add/remove
rule codes or override parameters. Profile selection mechanics:

1. CLI `--profile <name>` flag overrides everything.
2. Otherwise, an artifact's `audit_profile` IR field is consulted.
3. Otherwise, `v1` is the fallback.

Public API (re-exported via `dekspec.api`):
  - `load_profile(name)`        -> AuditProfile dataclass
  - `list_profiles()`           -> list[str]
  - `AuditProfile`              dataclass with `rules: frozenset[str]`,
                                `parameters: dict[str, dict[str, Any]]`, and
                                `approval_gates` (INT-021 — team profile)
  - `ProfileNotFoundError`      raised by load_profile for unknown names
  - `ProfileLoadError`          raised on malformed manifests

Stable as of v0.39.0 (F-3 phase 2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml


class ProfileNotFoundError(KeyError):
    """Raised when a requested profile name has no matching manifest."""


class ProfileLoadError(ValueError):
    """Raised when a profile manifest is structurally malformed."""


@dataclass(frozen=True)
class AuditProfile:
    """A resolved audit profile.

    `rules` is the fully-composed set of rule codes (after inheritance walk).
    `parameters` is the fully-composed parameter map.
    `approval_gates` is the fully-composed per-artifact-kind, per-transition
    approval-gate policy (INT-021). Empty for profiles that declare no gates
    (e.g. v1); populated by the `team` profile. Read by the `T-APPROVAL-GATE`
    audit rule, which yields nothing when this map is empty — so the rule is
    silent under v1 and active under team.
    `chain` is the inheritance path from root to this profile, useful for
    debuggability and chain-walk audits.
    """
    name: str
    rules: frozenset[str]
    parameters: dict[str, dict[str, Any]]
    chain: tuple[str, ...]
    approval_gates: dict[str, dict[str, dict[str, Any]]] = field(
        default_factory=dict
    )

    def has_rule(self, rule_code: str) -> bool:
        """Convenience predicate for runtime rule gating."""
        return rule_code in self.rules

    def param(self, rule_code: str, key: str, default: Any = None) -> Any:
        """Read a parameter for `rule_code`. Falls back to `default` if unset."""
        return self.parameters.get(rule_code, {}).get(key, default)

    def gate(self, kind: str, transition: str) -> dict[str, Any] | None:
        """Return the approval gate for `(kind, transition)`, or None if the
        active profile declares no gate for that artifact-kind / transition.

        `kind` is the artifact-kind key (ADR / AE / WS / IC / Intent / Mission
        / Constitution / SecurityProfile); `transition` is `FROM_to_TO`."""
        return self.approval_gates.get(kind, {}).get(transition)


def _load_raw(name: str) -> dict[str, Any]:
    """Load a profile manifest YAML by name. Returns the raw dict."""
    if not name or not name.replace("v", "").replace(".", "").isdigit() and not name.replace("_", "").replace("-", "").replace("v", "").isalnum():
        raise ProfileNotFoundError(f"invalid profile name: {name!r}")
    package = "dekspec.fidelity_audit.profiles"
    try:
        text = resources.files(package).joinpath(f"{name}.yaml").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise ProfileNotFoundError(
            f"no audit profile named {name!r} under tooling/dekspec/fidelity_audit/profiles/"
        ) from exc
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ProfileLoadError(f"profile {name!r} is malformed YAML: {exc}") from exc


@lru_cache(maxsize=None)
def load_profile(name: str = "v1") -> AuditProfile:
    """Load + fully resolve an audit profile by name.

    Walks the `inherits:` chain from root to leaf, composing rules + parameters.
    Cached because profile content is package-data and doesn't change at runtime.
    """
    chain: list[str] = []
    rules: set[str] = set()
    params: dict[str, dict[str, Any]] = {}
    gates: dict[str, dict[str, dict[str, Any]]] = {}

    # Walk inheritance chain root-to-leaf
    cursor: str | None = name
    visited: set[str] = set()
    walked: list[tuple[str, dict[str, Any]]] = []
    while cursor is not None:
        if cursor in visited:
            raise ProfileLoadError(
                f"profile inheritance cycle detected at {cursor!r} "
                f"(chain so far: {' -> '.join(chain)})"
            )
        visited.add(cursor)
        raw = _load_raw(cursor)
        if not isinstance(raw, dict):
            raise ProfileLoadError(f"profile {cursor!r} is not a YAML mapping")
        declared_name = raw.get("profile")
        if declared_name != cursor:
            raise ProfileLoadError(
                f"profile {cursor!r} has `profile: {declared_name!r}` in manifest; "
                f"must match filename stem"
            )
        chain.append(cursor)
        walked.append((cursor, raw))
        parent = raw.get("inherits")
        if parent is not None and not isinstance(parent, str):
            raise ProfileLoadError(
                f"profile {cursor!r} has non-string `inherits:` value {parent!r}"
            )
        cursor = parent

    # Compose root-to-leaf so leaves override parents
    for prof_name, raw in reversed(walked):
        raw_rules = raw.get("rules", [])
        if not isinstance(raw_rules, list) or not all(isinstance(r, str) for r in raw_rules):
            raise ProfileLoadError(
                f"profile {prof_name!r} has malformed `rules:` (expected list of strings)"
            )
        rules.update(raw_rules)
        # Optional `remove:` key — for future use; reserved + accepted but currently unused.
        for to_remove in raw.get("remove", []) or []:
            rules.discard(to_remove)
        raw_params = raw.get("parameters", {}) or {}
        if not isinstance(raw_params, dict):
            raise ProfileLoadError(
                f"profile {prof_name!r} has malformed `parameters:` (expected mapping)"
            )
        for rule_code, rule_params in raw_params.items():
            if not isinstance(rule_params, dict):
                raise ProfileLoadError(
                    f"profile {prof_name!r} parameters for {rule_code!r} "
                    f"must be a mapping, got {type(rule_params).__name__}"
                )
            params.setdefault(rule_code, {}).update(rule_params)
        # Optional `approval_gates:` block (INT-021) — composed per
        # artifact-kind, per-transition. Leaves override parents at the
        # (kind, transition) granularity.
        raw_gates = raw.get("approval_gates", {}) or {}
        if not isinstance(raw_gates, dict):
            raise ProfileLoadError(
                f"profile {prof_name!r} has malformed `approval_gates:` "
                f"(expected mapping)"
            )
        for kind, transitions in raw_gates.items():
            if not isinstance(transitions, dict):
                raise ProfileLoadError(
                    f"profile {prof_name!r} approval_gates for {kind!r} "
                    f"must be a mapping, got {type(transitions).__name__}"
                )
            for transition, gate in transitions.items():
                if not isinstance(gate, dict):
                    raise ProfileLoadError(
                        f"profile {prof_name!r} approval_gates "
                        f"{kind!r}/{transition!r} must be a mapping, got "
                        f"{type(gate).__name__}"
                    )
                gates.setdefault(kind, {})[transition] = dict(gate)

    return AuditProfile(
        name=name,
        rules=frozenset(rules),
        parameters=params,
        chain=tuple(reversed(chain)),
        approval_gates=gates,
    )


def list_profiles() -> list[str]:
    """Return sorted list of profile manifest names available in the package."""
    package = "dekspec.fidelity_audit.profiles"
    out: list[str] = []
    for entry in resources.files(package).iterdir():
        n = entry.name
        if n.endswith(".yaml"):
            out.append(n[:-5])
    return sorted(out)


__all__ = [
    "AuditProfile",
    "ProfileNotFoundError",
    "ProfileLoadError",
    "load_profile",
    "list_profiles",
]
