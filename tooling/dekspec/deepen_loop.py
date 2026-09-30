"""Deterministic progress checks for the optional multi-pass deepening skill.

No agent runtime or readiness policy. Callers supply verified pass evidence.
The optional skill and record CLI share this reducer so stop semantics agree.

Passes written by `dekspec deepen-record` carry a lifecycle: a ``state``
(``pending``, ``complete``, ``blocker``, ``dry``, ``abandoned``), the ``begin``
facts the tool read, and — for a completion — the ``core`` evidence it read
from core's execution records. The reducer honours them: a pending latest pass
is ``interrupted``, an abandoned pass counts toward nothing, and a dry pass
counts toward convergence only when its input contained the latest
integration. Plain caller signals (no ``state``) keep their earlier meaning.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LoopResult:
    converged: bool
    exit_reason: str
    passes: int
    completed: int
    scope: str | None
    prompts_issued: int = 0
    report: str = ""
    history: list[dict] = field(default_factory=list)


@dataclass
class _PassContext:
    iteration: int
    history: list[dict]


def assess(history: list[dict], *, max_iterations: int, dry_streak_target: int = 2) -> str:
    """Return continue/interrupted/convergence/stalled/budget/blocker from durable evidence."""
    if max_iterations < 1 or dry_streak_target < 1:
        raise ValueError("pass and convergence bounds must be positive")
    history = [h for h in history if h.get("state") != "abandoned"]
    if not history:
        return "continue"
    latest = history[-1]
    if latest.get("state") == "pending":
        return "interrupted"
    if latest.get("blocker") or latest.get("implementation_status") in {"blocked", "unavailable", "not-ready", "running", "incomplete"}:
        return "blocker"
    # Completed implementation needs both behavioral and architecture evidence.
    # A lifecycle pass is complete only on core's evidence (the caller's flags do not count).
    for signal in history:
        if "state" in signal:
            verified = signal["state"] == "complete" and (signal.get("core") or {}).get("outcome") == "complete"
        else:
            verified = bool(signal.get("verified") and signal.get("revision")
                            and signal.get("implementation_status") == "complete")
        if signal.get("completed", 0) and not (verified and signal.get("evidence")):
            return "blocker"
    integrated = [(h.get("core") or {}).get("revision") for h in history if h.get("state") == "complete"]
    latest_integration = integrated[-1] if integrated else None
    proposals = [h.get("candidate") for h in history if h.get("candidate")]
    rejected = {r["id"] for h in history[:-1] for r in h.get("rejected", [])}
    if latest.get("candidate") in rejected and not latest.get("new_evidence"):
        return "stalled"
    if len(proposals) >= 2 and proposals[-1] == proposals[-2]:
        return "stalled"
    if len(proposals) >= 3 and proposals[-1] == proposals[-3]:
        return "stalled"
    # Unresolved work is carried forward unless explicitly resolved, not erased
    # by omission or by a later dry assertion.
    pending: set[str] = set()
    for signal in history:
        pending.update(signal.get("unresolved", []))
        pending.difference_update(signal.get("resolved", []))
    recent = history[-dry_streak_target:]
    if len(recent) == dry_streak_target and not pending and all(
        h.get("dry") and h.get("remaining") == 0 and h.get("evidence")
        and h.get("implementation_status") in ("complete", "not-needed")
        and ("begin" not in h or h["begin"].get("latest_integration") == latest_integration)
        for h in recent
    ):
        return "convergence"
    if len(history) >= max_iterations:
        return "budget"
    return "continue"


def run_until_dry(*, pass_runner: Callable[..., dict], scope: str | None = None,
                  max_iterations: int, dry_streak_target: int = 2,
                  history: list[dict] | None = None) -> LoopResult:
    records = copy.deepcopy(history or [])
    reason = assess(records, max_iterations=max_iterations, dry_streak_target=dry_streak_target)
    while reason == "continue":
        signal = pass_runner(scope=scope, context=_PassContext(len(records), copy.deepcopy(records)))
        records.append(copy.deepcopy(signal))
        reason = assess(records, max_iterations=max_iterations, dry_streak_target=dry_streak_target)
    completed = sum(int(s.get("completed", 0)) for s in records)
    return LoopResult(reason == "convergence", reason, len(records), completed, scope,
                      report=f"{reason}: {len(records)} passes; {completed} verified changes",
                      history=records)
