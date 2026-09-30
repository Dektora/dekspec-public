"""Executor plans and internal tasks — revisable execution records (ADR-056 §2–3).

A plan is the executor's own construction plan for one IB. It is committed
only after investigation (the first revision must carry findings), and it may
be revised freely as long as the revision:

* keeps every acceptance condition covered (or declares a direct, single-run
  plan, in which case conditions are verified directly at IB level);
* keeps task dependencies resolvable and acyclic;
* never drops a completed task, narrows what it covered, or reuses a retired id;
* never rewrites or removes a task another agent is working on (a takeover is
  explicit and recorded);
* stays inside the IB's allowed scope — a file outside it is a scope expansion
  that needs an IB amendment, not a plan revision.

Tasks carry no authority: completing all of them proves nothing on its own
(ADR-057); the IB's acceptance evidence does.
"""

from __future__ import annotations

import re
from typing import Any

from dekspec.diff_confinement import matches_any_glob
from dekspec.execution.contract import IBContract
from dekspec.execution.record import Event
from dekspec.execution.state import RunState

__all__ = ["FINDING_KEYS", "PlanError", "validate_plan"]

FINDING_KEYS = ("inspected", "contracts", "reuse", "uncertainties")
_TASK_ID = re.compile(r"^T-[A-Za-z0-9][A-Za-z0-9._-]*$")


class PlanError(ValueError):
    """The proposed plan revision violates a replanning rule."""


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _cycle(tasks: dict[str, dict[str, Any]]) -> list[str] | None:
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        path.append(node)
        for dep in tasks[node].get("depends_on", []):
            if state.get(dep) == 1:
                return path[path.index(dep):] + [dep]
            if state.get(dep) is None:
                found = visit(dep)
                if found:
                    return found
        state[node] = 2
        path.pop()
        return None

    for tid in tasks:
        if state.get(tid) is None:
            found = visit(tid)
            if found:
                return found
    return None


def validate_plan(
    plan: dict[str, Any],
    contract: IBContract,
    state: RunState,
    events: list[Event],
    actor: str,
    *,
    takeover: bool = False,
) -> dict[str, Any]:
    """Validate a proposed plan revision; return the normalized event payload.

    Raises :class:`PlanError` naming every violated rule.
    """
    if not isinstance(plan, dict):
        raise PlanError("a plan is a mapping (findings, rationale, direct | tasks)")
    if not isinstance(plan.get("tasks") or [], list) or not all(isinstance(t, dict) for t in plan.get("tasks") or []):
        raise PlanError("`tasks` must be a list of mappings (id, title, covers, depends_on, files)")
    errors: list[str] = []
    first = state.plan_revision == 0

    findings = plan.get("findings")
    if first:
        if not isinstance(findings, dict):
            errors.append(
                "the first plan must record investigation findings "
                f"({', '.join(FINDING_KEYS)}) — investigate the repository before committing a plan"
            )
        else:
            for key in FINDING_KEYS:
                if not _as_list(findings.get(key)):
                    errors.append(f"findings.{key} is empty (write 'none' explicitly if nothing applies)")
    normalized_findings = (
        {k: _as_list(findings.get(k)) for k in FINDING_KEYS} if isinstance(findings, dict) else None
    )

    direct = bool(plan.get("direct"))
    raw_tasks = plan.get("tasks") or []
    ac_ids = [c.id for c in contract.acceptance]
    tasks: dict[str, dict[str, Any]] = {}
    for raw in raw_tasks:
        tid = str(raw.get("id", "")).strip()
        if not _TASK_ID.match(tid):
            errors.append(f"task id {tid!r} must look like T-1 / T-parse")
            continue
        if tid in tasks:
            errors.append(f"duplicate task id {tid}")
            continue
        task = {
            "id": tid,
            "title": str(raw.get("title", "")).strip(),
            "covers": _as_list(raw.get("covers")),
            "depends_on": _as_list(raw.get("depends_on")),
            "files": _as_list(raw.get("files")),
        }
        for ac in task["covers"]:
            if ac not in ac_ids:
                errors.append(f"{tid} covers {ac}, which is not an acceptance condition of {contract.ib_id}")
        tasks[tid] = task

    if direct and tasks:
        errors.append("a direct plan verifies the IB in one run and must not also list tasks")
    if not direct:
        if not tasks:
            errors.append("a plan without tasks must say `direct: true`")
        covered = {ac for t in tasks.values() for ac in t["covers"]}
        missing = [ac for ac in ac_ids if ac not in covered]
        if missing:
            errors.append(f"acceptance coverage lost: no task covers {', '.join(missing)}")
        for t in tasks.values():
            for dep in t["depends_on"]:
                if dep not in tasks:
                    errors.append(f"{t['id']} depends on unknown task {dep}")
        if not any("depends on unknown" in e for e in errors):
            cyc = _cycle(tasks)
            if cyc:
                errors.append(f"task dependency cycle: {' → '.join(cyc)}")

    # Completed work and other agents' in-flight work survive every revision.
    ever_used = {
        t["id"] for ev in events if ev.type == "plan.committed" for t in ev.data.get("tasks", [])
    }
    for tid, prior in state.tasks.items():
        new = tasks.get(tid)
        if prior.get("status") == "done":
            if new is None:
                errors.append(f"{tid} is done and cannot be removed (its evidence must stay traceable)")
            elif not set(prior.get("covers", [])) <= set(new["covers"]):
                errors.append(f"{tid} is done; its covered conditions cannot be narrowed")
        elif prior.get("status") == "in_progress" and prior.get("owner") and prior["owner"] != actor:
            changed = new is None or any(new[k] != prior.get(k, []) for k in ("covers", "depends_on", "files"))
            if changed and not takeover:
                errors.append(
                    f"{tid} is in progress by {prior['owner']}; coordinate or pass an explicit takeover"
                )
    for tid in tasks:
        if tid in ever_used and tid not in state.tasks:
            errors.append(f"{tid} was retired in an earlier revision; use a new id")

    deviations: list[str] = []
    if contract.is_delegated:
        planned_hypothesis = {p for h in contract.hypothesis for p in re.findall(r"`([^`]+)`", h)}
        for t in tasks.values():
            for f in t["files"]:
                if not matches_any_glob(f, contract.scope):
                    errors.append(
                        f"{t['id']} plans to change {f}, outside {contract.ib_id}'s scope — "
                        "that is a scope expansion and needs an IB amendment, not a plan revision"
                    )
                elif f not in planned_hypothesis:
                    deviations.append(f)

    if errors:
        raise PlanError("; ".join(errors))

    return {
        "revision": state.plan_revision + 1,
        "direct": direct,
        "findings": normalized_findings,
        "rationale": str(plan.get("rationale", "")).strip(),
        "tasks": list(tasks.values()),
        "hypothesis_deviations": sorted(set(deviations)),
        "takeover": takeover,
    }
