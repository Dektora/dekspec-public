"""Owned loop-control driver behind the `deepen-until-dry` goal-command.

Bead ds-3mbf / IB-132. Backs ``plugins/dekspec/commands/deepen-until-dry.md``.

The command markdown owns and *documents* the AFK repeat-until-dry deepening
loop; this module is the deterministically-testable termination control the
command drives — loop bound, consecutive-dry convergence, and scope threading —
exactly as ``/orchestrate-coding-session`` owns :mod:`dekspec.action_handlers`.

The actual per-pass work (re-invoking the ``orchestrate-module-deepening`` skill with
fresh context and reading back its ``{completed, remaining, dry}`` convergence
signal) is INJECTED by the command runtime as the ``pass_runner`` callable.
This keeps the skill-invocation boundary mockable: the loop here is pure
control flow over an injected callable — no git / merge / subprocess / network
call ever happens in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class LoopResult:
    """Outcome of a :func:`run_until_dry` run.

    Fields:
        converged: whether the loop reached the consecutive-dry target.
        exit_reason: ``"convergence"`` or ``"safety_bound"``.
        passes: total number of ``orchestrate-module-deepening`` passes driven.
        beads_created: sum of per-pass ``completed`` counts across all rounds.
        scope: the active scope threaded into every pass (``None`` = whole repo).
        prompts_issued: human-in-the-loop prompts issued — always 0 (AFK).
        report: human-readable result summary. On a safety-bound trip it
            contains the exact phrase "stopped at bound, not converged".
    """

    converged: bool
    exit_reason: str
    passes: int
    beads_created: int
    scope: Optional[str]
    prompts_issued: int = 0
    report: str = ""


@dataclass
class _PassContext:
    """A fresh, per-pass context object handed to the injected ``pass_runner``.

    A NEW instance is created for every pass so each ``orchestrate-module-deepening``
    invocation gets no shared cross-pass context (the fresh-context guarantee).
    The iteration index is informational only; the loop's termination decision
    keys solely off the per-pass ``dry`` signal.
    """

    iteration: int


def run_until_dry(
    *,
    pass_runner: Callable[..., dict],
    scope: Optional[str] = None,
    max_iterations: int,
    dry_streak_target: int = 2,
) -> LoopResult:
    """Drive the repeat-until-dry deepening loop and return a :class:`LoopResult`.

    Each iteration calls ``pass_runner(scope=scope, context=<fresh context>)``
    where the context object is a NEW instance per pass (the fresh-context
    guarantee — no shared object threaded between rounds). The runner returns a
    dict-like ``{completed, remaining, dry}`` signal.

    Termination:
        - Convergence: a consecutive run of ``dry: true`` passes reaching
          ``dry_streak_target`` (a non-dry pass resets the streak to 0) exits
          with ``converged=True`` / ``exit_reason="convergence"``.
        - Safety bound: reaching ``max_iterations`` without convergence exits
          with ``converged=False`` / ``exit_reason="safety_bound"`` and a
          report containing "stopped at bound, not converged" — never loops
          forever.

    ``beads_created`` is the sum of per-pass ``completed`` counts. The loop is
    AFK: it never prompts (``prompts_issued`` is always 0).
    """
    streak = 0
    passes = 0
    beads_created = 0
    converged = False

    for iteration in range(max_iterations):
        # Fresh context object per pass — no cross-pass carry-over.
        signal = pass_runner(scope=scope, context=_PassContext(iteration=iteration))
        passes += 1
        beads_created += int(signal.get("completed", 0))

        if signal.get("dry"):
            streak += 1
        else:
            streak = 0

        if streak >= dry_streak_target:
            converged = True
            break

    scope_label = scope if scope is not None else "whole-repo"
    if converged:
        exit_reason = "convergence"
        report = (
            f"Converged after {passes} pass(es) over {scope_label}: "
            f"{beads_created} bead(s) created across rounds; exit reason "
            f"= convergence ({dry_streak_target} consecutive dry passes)."
        )
    else:
        exit_reason = "safety_bound"
        report = (
            f"Stopped at bound, not converged: hit the {max_iterations}-pass "
            f"safety bound over {scope_label} with {beads_created} bead(s) "
            f"created across rounds; exit reason = safety_bound."
        )

    return LoopResult(
        converged=converged,
        exit_reason=exit_reason,
        passes=passes,
        beads_created=beads_created,
        scope=scope,
        prompts_issued=0,
        report=report,
    )
