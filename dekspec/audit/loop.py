"""Mechanical-fixed-point audit loop driver (INT-127 / ds-bqhf).

`dekspec audit doctor --loop` runs the configured rule family repeatedly
against the corpus until one of four termination conditions fires:

  - **quiescence** — a pass produced 0 new findings; the corpus is at
    rest under the current rule set.
  - **semantic-only** — every finding under the same (rule, artifact,
    field) identity as the prior pass; the loop is making no progress.
  - **oscillation** — the same identity disappears + reappears across
    passes; the rule family is unstable (often a sign of a feedback
    cycle between two rules).
  - **pass-cap** — the `--pass-cap N` ceiling is reached without any of
    the above; loop bails with a warning so the operator can investigate.

Oscillation detection uses **semantic identity** `(rule, artifact, field)`
— line numbers shift across passes (Nygard R1), so finding-hash-based
detection is unreliable.

Property-based convergence spec (per the methodology section):
  ∀ corpus C, rule set R, finite pass-cap N:
    run_loop(R, N) terminates in ≤ N passes with one of
    {quiescence, semantic-only, oscillation, pass-cap}.

The algorithm below is the canonical illustration; the property above
is the actual contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Finding identity — semantic, not hash.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FindingId:
    """Semantic finding identity per Nygard R1. Line numbers / hashes
    are intentionally NOT part of the identity."""

    rule: str
    artifact: str
    field: Optional[str] = None


# ---------------------------------------------------------------------------
# State + result objects.
# ---------------------------------------------------------------------------
@dataclass
class LoopState:
    """Passed to the rule_fn each pass. Carries pass index + prior
    pass's findings so a rule may short-circuit."""

    pass_index: int  # 1-based
    prior_findings: list[FindingId]


@dataclass
class LoopResult:
    """Result of `run_loop`. `termination` is one of:
    `quiescence | semantic-only | oscillation | pass-cap`."""

    termination: str
    passes: int
    finding_log: list[list[FindingId]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run_loop(
    rule_fn: Callable[[LoopState], list[FindingId]],
    pass_cap: int = 5,
) -> LoopResult:
    """Run the mechanical-fixed-point loop.

    `rule_fn(state)` returns the list of finding identities for the
    current pass. The driver does NOT mutate state; the rule function is
    expected to be a pure function of the corpus (the loop's whole point
    is to keep applying it until it stabilises).

    `pass_cap` defaults to 5 (placeholder per cross-plan SOFT dep on
    DekFactory Phase 0 archeology; recalibrate when that data lands).
    """
    finding_log: list[list[FindingId]] = []
    seen_identities_per_pass: list[set[FindingId]] = []

    for pass_index in range(1, pass_cap + 1):
        prior = finding_log[-1] if finding_log else []
        state = LoopState(pass_index=pass_index, prior_findings=list(prior))
        current = list(rule_fn(state))
        finding_log.append(current)
        seen_identities_per_pass.append(set(current))

        # Termination check 1: quiescence.
        # A pass produced 0 findings. Treat the 1st pass specially:
        # if the corpus starts clean, terminate at pass 1.
        if not current:
            return LoopResult(
                termination="quiescence",
                passes=pass_index,
                finding_log=finding_log,
            )

        # Termination checks below require ≥ 2 passes to compare.
        if pass_index < 2:
            continue

        prev = seen_identities_per_pass[-2]
        curr = seen_identities_per_pass[-1]

        # Termination check 2: oscillation.
        # The same identity disappeared at some earlier pass and now
        # reappears. Walk the history backwards looking for a "was
        # present → disappeared → present-again" pattern on any
        # identity in the current pass.
        for fid in curr:
            if fid in prev:
                continue
            # fid is in curr but NOT in prev — check whether it appeared
            # earlier and then disappeared.
            saw_earlier = any(
                fid in seen_identities_per_pass[i]
                for i in range(pass_index - 2)
            )
            if saw_earlier:
                return LoopResult(
                    termination="oscillation",
                    passes=pass_index,
                    finding_log=finding_log,
                )

        # Termination check 3: semantic-only.
        # Every finding identity in the current pass appeared in the
        # previous pass (and vice-versa) — no progress.
        if curr == prev:
            return LoopResult(
                termination="semantic-only",
                passes=pass_index,
                finding_log=finding_log,
            )

    # Termination check 4: pass-cap.
    return LoopResult(
        termination="pass-cap",
        passes=pass_cap,
        finding_log=finding_log,
    )
