"""T-PROSE-* prose-shape heuristic rule family (INT-065 / IB-109).

The T-series rules in `linkage.py` check the *presence* of a prose field
(T20 fires when a Working Spec has no business rules, T40 fires when an
Implementation Brief has no goal). They cannot see whether a field that
*is* present is actually well-formed.

This module adds the orthogonal check: it evaluates the heuristic *shape*
of a prose field against the five PROSE facets borrowed from Delimarsky's
PROSE constraint model and emits an advisory finding when a field in scope
falls below the configured shape threshold.

  - Precision — the prose names a concrete, specific subject (not "the
    system", "things", "errors" in the abstract).
  - Rationale — the prose says *why* (a reason, cause, or driver).
  - Outcome   — the prose states an observable result or behavior.
  - Scope     — the prose bounds what is and is not covered.
  - Example   — the prose includes a concrete instance, value, or case.

The facet detectors are deterministic lexical/structural heuristics —
keyword/marker presence, sentence-shape signals, length and specificity
proxies. They are heuristic, not semantic: false positives and false
negatives are expected and acceptable because the family is advisory-only
and conservatively thresholded.

The family covers exactly five (artifact-kind, field) pairs — one
`T-PROSE-*` rule code each:

  - T-PROSE-WS-BUSINESS-RULE     — WS business_rules[].rule
  - T-PROSE-WS-FAILURE-BEHAVIOR  — WS failure_behavior[].behavior
  - T-PROSE-IB-GOAL              — IB goal
  - T-PROSE-IB-DONE-WHEN         — IB done_when[]
  - T-PROSE-AE-RESPONSIBILITY    — AE responsibilities[]

Every `T-PROSE-*` finding emits at the engine's lowest severity grade
(`P3` — advisory / minor per ADR-013). The family is warning-only at MVP.

Per-repo configurability of the threshold (and on/off / severity) rides
the audit-profile `parameters:` surface — wired in IB-110. This module
ships conservative hardcoded defaults that the profile may override; the
entrypoint accepts an optional `profile` so the rule functions can read
overrides when IB-110 threads it. With no profile passed, the hardcoded
defaults apply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..constraint_compiler.graph import SpecGraph
from ..severity import P3, Severity
from .linkage import Finding

# --------------------------------------------------------------------------- #
# Conservative built-in defaults (IB-109)
#
# These are module-level named constants — IB-110 layers audit-profile
# `parameters:` overrides on top of them, IB-111 calibrates the threshold.
# The rule functions read the threshold off a `_ProseShapeConfig` object so
# there are no magic numbers buried in branch logic.
# --------------------------------------------------------------------------- #

#: The five PROSE facets, in canonical order.
PROSE_FACETS: tuple[str, ...] = ("Precision", "Rationale", "Outcome", "Scope", "Example")

#: Conservative default shape threshold — the minimum number of the five
#: facets a prose item must satisfy to *pass*. A field satisfying fewer than
#: this many facets draws an advisory finding. The default of 1 means only
#: prose satisfying ZERO of the five facets — genuinely contentless prose,
#: the egregious-vagueness case the family targets — draws a finding. This
#: is deliberately conservative: it keeps the family effectively quiet on a
#: methodology-practicing repo (the IB-109 C&D "prefer false-negative" rule).
#: IB-110 makes it profile-overridable; IB-111 calibrates it against the
#: self-spec corpus (measured 2026-05-21: 3 advisory findings at this value).
DEFAULT_SHAPE_THRESHOLD: int = 1

#: Below this character length a prose item carries too little text for the
#: heuristic to read a facet reliably. Such an item is SKIPPED entirely — it
#: draws no finding (a deliberate false-negative). A terse-but-real prose
#: item ("Re-raise; parse aborts.") is not "egregiously vague" — the family
#: is advisory and conservative, so it stays quiet rather than flag length.
_MIN_PROSE_CHARS: int = 28

#: The advisory severity floor for every T-PROSE-* finding (ADR-013 lowest
#: grade). The family is warning-only at MVP — this is never raised here.
DEFAULT_SEVERITY: Severity = P3


@dataclass(frozen=True)
class _ProseShapeConfig:
    """Resolved per-rule config for one T-PROSE-* rule.

    IB-109 ships the conservative defaults; IB-110 layers audit-profile
    `parameters:` overrides on top by constructing this object from the
    active profile's parameter map (the rule functions never read magic
    numbers directly — they read this object).
    """

    threshold: int = DEFAULT_SHAPE_THRESHOLD
    severity: Severity = DEFAULT_SEVERITY
    enabled: bool = True


#: The conservative default config, shared by every T-PROSE-* rule when no
#: profile override is present.
DEFAULT_CONFIG: _ProseShapeConfig = _ProseShapeConfig()


def _resolve_config(rule_code: str, profile: Any) -> _ProseShapeConfig:
    """Resolve the effective config for `rule_code`.

    Profile parameter wins; the hardcoded conservative default is the
    fallback. When `profile` is None (IB-109 standalone) or names no
    override for the rule, `DEFAULT_CONFIG` is returned. This is the
    consumer side of the audit-profile `parameters:` threading wired by
    IB-110 — it mirrors how `L11-MSN-STALE` reads `days_threshold`.

    A profile that omits the entry falls back silently — no crash, no warn.
    """
    if profile is None:
        return DEFAULT_CONFIG
    threshold = profile.param(rule_code, "threshold", DEFAULT_SHAPE_THRESHOLD)
    severity = profile.param(rule_code, "severity", DEFAULT_SEVERITY)
    enabled = profile.param(rule_code, "enabled", True)
    try:
        threshold = int(threshold)
    except (TypeError, ValueError):
        threshold = DEFAULT_SHAPE_THRESHOLD
    if severity not in ("P0", "P1", "P2", "P3"):
        severity = DEFAULT_SEVERITY
    return _ProseShapeConfig(
        threshold=threshold,
        severity=severity,  # type: ignore[arg-type]
        enabled=bool(enabled),
    )


# --------------------------------------------------------------------------- #
# Facet detectors — deterministic lexical / structural heuristics
# --------------------------------------------------------------------------- #

# Vague abstract nouns that, when they are the *only* subject signal, mean the
# prose names nothing concrete. Precision is the absence of these dominating.
_VAGUE_SUBJECTS: frozenset[str] = frozenset({
    "thing", "things", "stuff", "system", "systems", "data", "everything",
    "anything", "something", "it", "code", "the code", "components",
    "feature", "features", "behavior", "behaviors", "functionality",
})

# A concrete-subject signal: a backtick code span, a Title-Case multi-word
# proper noun, an artifact id, a path, or a quoted literal — anything that
# names a *specific* referent rather than an abstract category.
_CONCRETE_SUBJECT = re.compile(
    r"`[^`]+`"                          # `code span`
    r"|\b[A-Z][A-Za-z]+(?:[A-Z][A-Za-z]+)+\b"   # CamelCase identifier
    r"|\b[A-Z]{2,}-\d+\b"               # artifact id e.g. WS-001 / ADR-013
    r"|\b[A-Z][a-z]+\s[A-Z][a-z]+\b"    # Title Case proper noun
    r"|[\w./-]+\.(?:py|md|yaml|yml|json|sh|toml)\b"  # a file path
    r"|\"[^\"]+\"|'[^']{3,}'"           # a quoted literal
)

# Rationale markers — the prose states *why*.
_RATIONALE = re.compile(
    r"\b(?:because|since|so that|so as to|in order to|to ensure|to avoid|"
    r"to prevent|to keep|rationale|reason|driven by|motivat\w*|"
    r"the reason|which is why|therefore|thereby|otherwise)\b",
    re.IGNORECASE,
)

# Outcome markers — the prose states an observable result / behavior.
_OUTCOME = re.compile(
    r"\b(?:result\w*|produc\w*|emit\w*|return\w*|yield\w*|rais\w*|"
    r"output\w*|behav\w*|exit\w*|fail\w*|succeed\w*|success\w*|"
    r"pass(?:es|ed|ing)?|reject\w*|accept\w*|verif\w*|assert\w*|"
    r"observ\w*|guarantee\w*|ensure\w*|so that|leads? to|"
    r"surfac\w*|report\w*|exact\w*|round-trips?\w*)\b",
    re.IGNORECASE,
)

# Scope markers — the prose bounds what is / is not covered.
_SCOPE = re.compile(
    r"\b(?:only|never|always|every|each|all|any|except|excluding|including|"
    r"unless|when|whenever|limited to|scoped to|covered|included|"
    r"\bper\b|across every|for any|for every|out of scope|in scope|"
    r"applies? to|does not\b)",
    re.IGNORECASE,
)

# Example markers — the prose includes a concrete instance / value / case.
# Abbreviations are NOT word-bounded on the right: `e.g.,` puts a comma
# after the final `.`, so a trailing `\b` would never match.
_EXAMPLE_MARKER = re.compile(
    r"(?:\be\.g\.|\bi\.e\.|\bfor example\b|\bfor instance\b|"
    r"\bsuch as\b|\bnamely\b)",
    re.IGNORECASE,
)
# Number-with-unit / concrete-value signal (an embedded example value).
_EXAMPLE_VALUE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|sec|seconds?|days?|chars?|"
    r"lines?|bytes?|KB|MB|GB|items?|files?|rules?)\b"
)


def _normalize(text: str) -> str:
    """Collapse whitespace; return the stripped single-line form."""
    return re.sub(r"\s+", " ", text).strip()


def has_precision(text: str) -> bool:
    """Precision — the prose names a concrete, specific subject.

    True when a concrete-subject signal is present (a code span, an
    identifier, an artifact id, a path, a Title-Case proper noun, or a
    quoted literal) and the prose is not dominated solely by vague
    abstract nouns.
    """
    norm = _normalize(text)
    if len(norm) < _MIN_PROSE_CHARS:
        return False
    if not _CONCRETE_SUBJECT.search(norm):
        # No concrete referent at all — fall through to the vague check:
        # if the prose is *only* vague subjects it definitely lacks
        # precision; otherwise (e.g. a domain verb phrase) be lenient.
        words = re.findall(r"[A-Za-z][\w-]*", norm.lower())
        if not words:
            return False
        vague_hits = sum(1 for w in words if w in _VAGUE_SUBJECTS)
        return vague_hits == 0 and len(words) >= 8
    return True


def has_rationale(text: str) -> bool:
    """Rationale — the prose says *why* (a reason, cause, or driver)."""
    norm = _normalize(text)
    if len(norm) < _MIN_PROSE_CHARS:
        return False
    return bool(_RATIONALE.search(norm))


def has_outcome(text: str) -> bool:
    """Outcome — the prose states an observable result or behavior."""
    norm = _normalize(text)
    if len(norm) < _MIN_PROSE_CHARS:
        return False
    return bool(_OUTCOME.search(norm))


def has_scope(text: str) -> bool:
    """Scope — the prose bounds what is and is not covered."""
    norm = _normalize(text)
    if len(norm) < _MIN_PROSE_CHARS:
        return False
    return bool(_SCOPE.search(norm))


def has_example(text: str) -> bool:
    """Example — the prose includes a concrete instance, value, or case."""
    norm = _normalize(text)
    if len(norm) < _MIN_PROSE_CHARS:
        return False
    return bool(_EXAMPLE_MARKER.search(norm) or _EXAMPLE_VALUE.search(norm))


#: Detector dispatch — facet name → predicate. Ordered like PROSE_FACETS.
_FACET_DETECTORS: dict[str, Any] = {
    "Precision": has_precision,
    "Rationale": has_rationale,
    "Outcome": has_outcome,
    "Scope": has_scope,
    "Example": has_example,
}


def missing_facets(text: str) -> list[str]:
    """Return the PROSE facets `text` appears to be missing, in canonical order."""
    return [facet for facet in PROSE_FACETS if not _FACET_DETECTORS[facet](text)]


def facet_count(text: str) -> int:
    """Return the number of PROSE facets `text` appears to satisfy."""
    return len(PROSE_FACETS) - len(missing_facets(text))


# --------------------------------------------------------------------------- #
# Finding construction
# --------------------------------------------------------------------------- #

def _truncate(text: str, max_chars: int = 90) -> str:
    """One-line excerpt of `text`, ellipsised at `max_chars`."""
    norm = _normalize(text)
    if len(norm) <= max_chars:
        return norm
    return norm[: max_chars - 1].rstrip() + "…"


def _evaluate(
    *,
    rule_code: str,
    artifact_id: str,
    field_label: str,
    text: str,
    config: _ProseShapeConfig,
) -> Finding | None:
    """Evaluate one prose item; return a Finding if it is under-shaped.

    `field_label` already includes any list-item index/excerpt so the
    author can locate the offending prose. A prose item below the
    `_MIN_PROSE_CHARS` floor is skipped (returns None) — too little text
    to read a facet from is treated as a false-negative, not flagged.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if len(_normalize(text)) < _MIN_PROSE_CHARS:
        return None
    missing = missing_facets(text)
    satisfied = len(PROSE_FACETS) - len(missing)
    if satisfied >= config.threshold:
        return None
    return Finding(
        severity=config.severity,
        rule=rule_code,
        artifact_id=artifact_id,
        message=(
            f"{field_label} prose is below the prose-shape threshold "
            f"(satisfies {satisfied}/{len(PROSE_FACETS)} PROSE facets, "
            f"threshold {config.threshold}) — appears to be missing facets: "
            f"{', '.join(missing)}. Snippet: {_truncate(text)}"
        ),
        fix_kind="semantic",
    )


# Artifact statuses for which prose-shape checks are skipped — terminal /
# pre-authoring states where shape is not yet meaningful. Mirrors the
# skip-status convention used by the D-15 / D-series rules.
_SKIP_WS = {"DEPRECATED", "SUPERSEDED", "TODO"}
_SKIP_IB = {"DEPRECATED", "COMPLETED", "TODO"}
_SKIP_AE = {"DEPRECATED", "TODO"}


# --------------------------------------------------------------------------- #
# The five T-PROSE-* rules — one per (artifact-kind, field) pair
# --------------------------------------------------------------------------- #

def _t_prose_ws_business_rule(graph: SpecGraph, profile: Any) -> list[Finding]:
    """T-PROSE-WS-BUSINESS-RULE (advisory): a WS business rule whose prose
    falls below the shape threshold. Evaluated per business-rule item."""
    config = _resolve_config("T-PROSE-WS-BUSINESS-RULE", profile)
    if not config.enabled:
        return []
    out: list[Finding] = []
    for ws in graph.wses():
        if ws.get("status") in _SKIP_WS:
            continue
        ws_id = ws["id"]
        for br in ws.get("business_rules", []) or []:
            if not isinstance(br, dict):
                continue
            rule_text = br.get("rule")
            number = br.get("number", "?")
            finding = _evaluate(
                rule_code="T-PROSE-WS-BUSINESS-RULE",
                artifact_id=ws_id,
                field_label=f"WS.business_rules[{number}]",
                text=rule_text if isinstance(rule_text, str) else "",
                config=config,
            )
            if finding is not None:
                out.append(finding)
    return out


def _t_prose_ws_failure_behavior(graph: SpecGraph, profile: Any) -> list[Finding]:
    """T-PROSE-WS-FAILURE-BEHAVIOR (advisory): a WS failure-behavior entry
    whose `behavior` prose falls below the shape threshold. Per-item."""
    config = _resolve_config("T-PROSE-WS-FAILURE-BEHAVIOR", profile)
    if not config.enabled:
        return []
    out: list[Finding] = []
    for ws in graph.wses():
        if ws.get("status") in _SKIP_WS:
            continue
        ws_id = ws["id"]
        for idx, fb in enumerate(ws.get("failure_behavior", []) or []):
            if not isinstance(fb, dict):
                continue
            behavior_text = fb.get("behavior")
            label = fb.get("failure") or f"#{idx + 1}"
            finding = _evaluate(
                rule_code="T-PROSE-WS-FAILURE-BEHAVIOR",
                artifact_id=ws_id,
                field_label=f"WS.failure_behavior[{label}].behavior",
                text=behavior_text if isinstance(behavior_text, str) else "",
                config=config,
            )
            if finding is not None:
                out.append(finding)
    return out


def _t_prose_ib_goal(graph: SpecGraph, profile: Any) -> list[Finding]:
    """T-PROSE-IB-GOAL (advisory): an IB whose `goal` prose falls below the
    shape threshold. Evaluated as a single field (one finding per IB)."""
    config = _resolve_config("T-PROSE-IB-GOAL", profile)
    if not config.enabled:
        return []
    out: list[Finding] = []
    for ib in graph.ibs():
        if ib.get("status") in _SKIP_IB:
            continue
        ib_id = ib["id"]
        goal = ib.get("goal")
        finding = _evaluate(
            rule_code="T-PROSE-IB-GOAL",
            artifact_id=ib_id,
            field_label="IB.goal",
            text=goal if isinstance(goal, str) else "",
            config=config,
        )
        if finding is not None:
            out.append(finding)
    return out


def _t_prose_ib_done_when(graph: SpecGraph, profile: Any) -> list[Finding]:
    """T-PROSE-IB-DONE-WHEN (advisory): an IB done-when criterion whose prose
    falls below the shape threshold. Evaluated per criterion item."""
    config = _resolve_config("T-PROSE-IB-DONE-WHEN", profile)
    if not config.enabled:
        return []
    out: list[Finding] = []
    for ib in graph.ibs():
        if ib.get("status") in _SKIP_IB:
            continue
        ib_id = ib["id"]
        for idx, criterion in enumerate(ib.get("done_when", []) or []):
            text = criterion if isinstance(criterion, str) else ""
            finding = _evaluate(
                rule_code="T-PROSE-IB-DONE-WHEN",
                artifact_id=ib_id,
                field_label=f"IB.done_when[{idx + 1}]",
                text=text,
                config=config,
            )
            if finding is not None:
                out.append(finding)
    return out


def _t_prose_ae_responsibility(graph: SpecGraph, profile: Any) -> list[Finding]:
    """T-PROSE-AE-RESPONSIBILITY (advisory): an AE responsibility whose prose
    falls below the shape threshold. Evaluated per responsibility item."""
    config = _resolve_config("T-PROSE-AE-RESPONSIBILITY", profile)
    if not config.enabled:
        return []
    out: list[Finding] = []
    for ae in graph.aes():
        if ae.get("status") in _SKIP_AE:
            continue
        ae_id = ae["id"]
        for idx, resp in enumerate(ae.get("responsibilities", []) or []):
            text = resp if isinstance(resp, str) else ""
            finding = _evaluate(
                rule_code="T-PROSE-AE-RESPONSIBILITY",
                artifact_id=ae_id,
                field_label=f"AE.responsibilities[{idx + 1}]",
                text=text,
                config=config,
            )
            if finding is not None:
                out.append(finding)
    return out


#: Every T-PROSE-* rule code this module emits — the family's public list.
PROSE_SHAPE_RULE_CODES: tuple[str, ...] = (
    "T-PROSE-WS-BUSINESS-RULE",
    "T-PROSE-WS-FAILURE-BEHAVIOR",
    "T-PROSE-IB-GOAL",
    "T-PROSE-IB-DONE-WHEN",
    "T-PROSE-AE-RESPONSIBILITY",
)

_RULE_FUNCTIONS = (
    _t_prose_ws_business_rule,
    _t_prose_ws_failure_behavior,
    _t_prose_ib_goal,
    _t_prose_ib_done_when,
    _t_prose_ae_responsibility,
)


def prose_shape_rules(graph: SpecGraph, profile: Any = None) -> list[Finding]:
    """Run the whole T-PROSE-* family against `graph`; return its findings.

    This is the single entrypoint the rule-dispatch sequence in `linkage.py`
    calls. The rules emit unconditionally — profile *filtering* (whether a
    consumer sees the findings) is `audit_linkage`'s job, exactly as for
    every other family. `profile`, when passed, lets the rule functions read
    per-rule `parameters:` overrides (threshold / severity / enabled); when
    None the conservative hardcoded defaults apply.
    """
    findings: list[Finding] = []
    for rule_fn in _RULE_FUNCTIONS:
        findings.extend(rule_fn(graph, profile))
    return findings


__all__ = [
    "PROSE_FACETS",
    "PROSE_SHAPE_RULE_CODES",
    "DEFAULT_SHAPE_THRESHOLD",
    "DEFAULT_CONFIG",
    "has_precision",
    "has_rationale",
    "has_outcome",
    "has_scope",
    "has_example",
    "missing_facets",
    "facet_count",
    "prose_shape_rules",
]
