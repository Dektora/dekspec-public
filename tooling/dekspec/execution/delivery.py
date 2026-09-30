"""Delivery-level verification and the landing gate (ADR-058).

A delivery is whatever one branch / worktree / pull request carries: a single
IB, an Intent's IBs, or a Mission cluster. Acceptance stays per IB; this
module makes sure the evidence and verdicts cover the *final integrated head*:

* :func:`delivery_verify` re-runs every included IB's acceptance and the
  repository integration command against the same content, recording both.
* :func:`delivery_check` is the gate the land skill and CI run before merge.
  It passes only when the branch is current with its base and every included
  IB's completion gate passes at the exact head. With ``rerun=True`` (CI) it
  re-executes the acceptance checks itself instead of trusting recorded
  results, and writes nothing.

The `/implement` driver alone may ask both not to repeat an execution it made
itself at the identical binding (ADR-059 stages 2 and 6): ``delivery_verify(...,
reuse_own=True)`` relies on its own per-IB re-verification, and
``delivery_check(..., rerun=True, reuse_actor=...)`` on its own delivery
verification. What they rely on is named in the record; evidence anyone else
recorded is always executed again, and the command line never reuses.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from dekspec.execution.engine import (
    RETIRED_STATUSES,
    Check,
    Engine,
    ExecutionError,
    GateResult,
    integrated_completion,
)
from dekspec.execution import acceptance as acc
from dekspec.execution.fingerprint import current_commit
from dekspec.execution.history import record_ids_in_history, record_versions
from dekspec.execution.record import EXECUTION_DIRNAME, parse_record_text
from dekspec.execution.scope import ScopeError, resolve_base
from dekspec.execution.settings import load_settings_at

__all__ = ["DeliveryResult", "delivery_check", "delivery_verify", "discover_delivery_ibs"]


@dataclass
class DeliveryResult:
    ibs: list[str]
    checks: list[Check] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)
    #: With ``rerun`` and a ``reuse_actor``: the evidence the gate relied on
    #: instead of re-executing — per IB ``{"delivery": ref, "evidence": ref}``,
    #: and ``"integration"`` — and what it executed itself (O-4, IB-146).
    relied_on: dict[str, Any] = field(default_factory=dict)
    executed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks) and all(g.ok for g in self.gates)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "ibs": self.ibs, "checks": [c.as_dict() for c in self.checks],
                "gates": [g.as_dict() for g in self.gates]}


def discover_delivery_ibs(engine: Engine, base: str | None = None) -> list[str]:
    """IBs this branch delivers (see :meth:`Engine.delivery_ibs`)."""
    return engine.delivery_ibs(base)


def _integration_policy(engine: Engine, base_commit: str | None) -> str | None:
    """The integration command the delivery must satisfy: the *base* branch's
    policy — a delivery cannot switch it off or swap it for a weaker one."""
    if base_commit:
        base_cmd = load_settings_at(engine.repo_root, base_commit, spec_root=engine.spec_root).integration_command
        if base_cmd:
            return base_cmd
    return engine.settings.integration_command


def _integration(engine: Engine, cmd: str | None) -> dict[str, Any] | None:
    if not cmd:
        return None
    started = time.monotonic()
    try:
        # The runner's identity never reaches the check (evidence must not depend on who runs it).
        env = {k: v for k, v in os.environ.items() if k not in acc._ENV_DROP_EXACT}
        proc = subprocess.run(cmd, shell=True, cwd=str(engine.repo_root), capture_output=True, text=True,
                              timeout=engine.settings.command_timeout, env=env)
        code, tail = proc.returncode, (proc.stdout + proc.stderr)[-3000:]
    except subprocess.TimeoutExpired:
        code, tail = -1, f"timed out after {engine.settings.command_timeout}s"
    return {"command": cmd, "exit_code": code, "status": "passed" if code == 0 else "failed",
            "duration": round(time.monotonic() - started, 2), "tail": tail if code else ""}


def _ref(ident: str, event: Any) -> dict[str, Any]:
    """How a record names one event of another: its record, sequence and hash."""
    return {"record": ident, "seq": event.seq, "hash": event.hash}


def _latest_ib_evidence(engine: Engine, ident: str, actor: str) -> Any:
    _rec, events, _st = engine.state(ident)
    return next((e for e in reversed(events)
                 if e.type == "evidence.recorded" and e.actor == actor and e.data.get("kind", "ib") == "ib"), None)


def delivery_verify(engine: Engine, ibs: list[str], actor: str, *, base: str | None = None,
                    reuse_own: bool = False) -> dict[str, Any]:
    """Verify every included IB and the base's integration command against the
    same content, and record one delivery evidence event in each IB's record.

    ``reuse_own`` (the `/implement` driver's stage 2, ADR-059): an IB whose
    latest evidence ``actor`` itself recorded, passing, at the identical
    binding (:meth:`Engine.own_evidence`) is not executed again; the delivery
    evidence names it under ``relies_on``. Everything else is executed and
    named under ``executed``. Evidence another actor recorded is always
    executed again (ADR-057). The integration command always runs."""
    base = base or engine.base
    ibs = [ib for ib in ibs if engine.contract(ib).status not in RETIRED_STATUSES]  # retired: no verification
    if not ibs:
        raise ExecutionError("no active IBs to verify in this delivery")
    try:
        base_commit: str | None = resolve_base(engine.repo_root, base)
    except ScopeError:
        base_commit = None
    per_ib: dict[str, dict[str, Any]] = {}
    relies_on: dict[str, dict[str, Any]] = {}
    executed: dict[str, dict[str, Any]] = {}
    for ib in ibs:
        c = engine.contract(ib)
        own = engine.own_evidence(ib, actor, base=base) if reuse_own and base_commit else None
        if own is not None:
            engine._refuse_integrated(c, base)  # integrated work takes no evidence, reused or not
            per_ib[ib] = own.data
            relies_on[c.ib_id] = _ref(c.ib_id, own)
            continue
        per_ib[ib] = engine.verify(ib, actor, base=base)
        recorded = _latest_ib_evidence(engine, c.ib_id, actor)
        if recorded is not None:
            executed[c.ib_id] = _ref(c.ib_id, recorded)
    fp = engine.fingerprint()
    integration = _integration(engine, _integration_policy(engine, base_commit))
    if integration and engine.fingerprint() != fp:
        integration.update(status="failed", tail="the integration command changed the repository content; "
                                                  "its result cannot be bound to what was tested")
    summary = {
        "kind": "delivery",
        "ibs": ibs,
        "fingerprint": fp,
        "commit": current_commit(engine.repo_root),
        "base_commit": base_commit,
        "relies_on": relies_on,
        "executed": executed,
        "integration": integration,
        "overall": "passed" if all(e["overall"] == "passed" for e in per_ib.values())
        and (integration is None or integration["status"] == "passed") else "failed",
    }
    for ib in ibs:
        engine.record(engine.contract(ib).ib_id).append("evidence.recorded", actor, summary)
    return {"delivery": summary, "ibs": {k: v["overall"] for k, v in per_ib.items()}}


def _standing(engine: Engine, ib: str, actor: str | None, active: list[str], fp: str,
              base_commit: str, base: str | None) -> tuple[Any, Any] | None:
    """``actor``'s own passing delivery verification that still stands for ``ib``
    at the identical binding, as ``(delivery evidence, the IB's evidence it
    names)``, or ``None``: the IB's latest delivery evidence was recorded by
    ``actor``, passed, covers every active IB, and is at this fingerprint and
    base commit; and the per-IB evidence it names is still the IB's
    :meth:`Engine.own_evidence` — so the contract, acceptance baseline, context
    manifest and test interpreter match as well. Anything unreadable is not
    relied on: the gate executes, and reports what it finds."""
    if not actor:
        return None
    try:
        c = engine.contract(ib)
        _rec, events, _st = engine.state(c.ib_id)
        delivery = next((e for e in reversed(events)
                         if e.type == "evidence.recorded" and e.data.get("kind") == "delivery"), None)
        if delivery is None:
            return None
        d = delivery.data
        covered = {engine.contract(i).ib_id for i in d.get("ibs", [])}
        if delivery.actor != actor or d.get("overall") != "passed" or d.get("fingerprint") != fp \
                or d.get("base_commit") != base_commit or not {engine.contract(i).ib_id for i in active} <= covered:
            return None
        own = engine.own_evidence(ib, actor, base=base)
    except ExecutionError:
        return None
    named = {**(d.get("executed") or {}), **(d.get("relies_on") or {})}.get(c.ib_id) or {}
    if own is None or named.get("seq") != own.seq or named.get("hash") != own.hash:
        return None
    return delivery, own


def _standing_integration(engine: Engine, actor: str | None, active: list[str], fp: str, base_commit: str,
                          base: str | None, policy: str) -> tuple[str, Any] | None:
    """``(record, delivery evidence)`` of ``actor``'s own passing delivery
    verification at this fingerprint and base commit, covering every active IB,
    whose integration command is exactly the base's ``policy`` and passed."""
    if not actor:
        return None
    for ib in active:
        try:
            c = engine.contract(ib)
            _rec, events, _st = engine.state(c.ib_id)
        except ExecutionError:
            continue
        delivery = next((e for e in reversed(events)
                         if e.type == "evidence.recorded" and e.data.get("kind") == "delivery"), None)
        if delivery is None:
            continue
        d = delivery.data
        ran = d.get("integration") or {}
        try:
            covered = {engine.contract(i).ib_id for i in d.get("ibs", [])}
            wanted = {engine.contract(i).ib_id for i in active}
        except ExecutionError:
            continue
        if delivery.actor == actor and d.get("overall") == "passed" and d.get("fingerprint") == fp \
                and d.get("base_commit") == base_commit and wanted <= covered \
                and ran.get("command") == policy and ran.get("status") == "passed":
            return c.ib_id, delivery
    return None


def _append_only(engine: Engine, ib: str, base_commit: str) -> str | None:
    """Every committed version of the record — at the base and in every commit
    of the delivery, on either side of a merge — must be a prefix of the current
    one: history is only appended to."""
    rel = f"{EXECUTION_DIRNAME}/{ib}/record.jsonl"
    current_path = engine.repo_root / rel
    current = current_path.read_text(encoding="utf-8") if current_path.is_file() else ""
    for commit, prior in record_versions(engine.repo_root, rel, base_commit):
        if not current.startswith(prior):
            return f"{rel} at {commit[:12]} is not a prefix of the current record (events were removed or rewritten)"
    return None


def _failure_reasons(evidence: dict) -> list[str]:
    """Every reason a verification failed, not only the failing conditions."""
    reasons = [*evidence.get("context_problems", []), *evidence.get("integrity_problems", [])]
    scope = evidence.get("scope") or {}
    reasons += [f"{v.get('kind', 'scope')}: {v.get('detail') or v.get('path', '')}"
                for v in scope.get("violations", [])]
    reasons += [f"spec impact not delivered: {a}" for a in scope.get("missing_spec_impact", [])]
    reasons += [f"{r['id']} {r['status']}" for r in evidence.get("results", [])
                if r["kind"] != "review" and r["status"] != "passed"]
    return reasons or ["unknown"]


def _record_history_checks(engine: Engine, base_commit: str) -> list[Check]:
    """Every execution record the base or any commit of the delivery carried
    must still be present, append-only and attached to its artifact. A record
    is never deleted, truncated or relabelled — work is retired by the IB's
    status (SUPERSEDED / DEPRECATED), with its record kept (ADR-056)."""
    checks: list[Check] = []
    seen = record_ids_in_history(engine.repo_root, base_commit)
    present = {p.parent.name for p in (engine.repo_root / EXECUTION_DIRNAME).glob("*/record.jsonl")}
    missing = sorted(set(seen) - present)
    checks.append(Check(
        "execution-records-present", not missing,
        "every record in the base and the delivery's history is present" if not missing else
        "; ".join(f"{rid}'s execution record existed (seen at {seen[rid][:12]}) and is gone — records are never "
                  "deleted or relabelled; retire the IB by status instead" for rid in missing)))
    for rid in sorted(present | set(seen)):
        if rid in missing:
            continue
        problem = _append_only(engine, rid, base_commit)
        if problem or rid in seen:
            checks.append(Check(f"{rid}:record-append-only", problem is None, problem or "append-only"))
    extended = []
    for rid in sorted(present):
        seq = integrated_completion(engine.repo_root, rid, base_commit)
        if seq is None:
            continue
        base_text = subprocess.run(["git", "show", f"{base_commit}:{EXECUTION_DIRNAME}/{rid}/record.jsonl"],
                                   cwd=str(engine.repo_root), capture_output=True, text=True).stdout
        base_last = max((e.seq for e in parse_record_text(base_text)), default=0)
        added = sorted({e.type for e in engine.record(rid).events(strict=False) if e.seq > base_last})
        if added:
            extended.append(f"{rid} (completion #{seq}; appends {', '.join(added)})")
    checks.append(Check("integrated-completions-kept", not extended,
                        "no record whose completion the base integrated is extended" if not extended else
                        "extends work whose completion is already integrated in the base: " + ", ".join(extended)
                        + " — integrated work is history; later work needs its own IB"))
    orphans = []
    for rid in sorted(present):
        if rid.startswith("IB-"):
            try:
                engine.contract(rid)
            except ExecutionError:
                orphans.append(rid)
    checks.append(Check("execution-records-attached", not orphans,
                        "every IB record belongs to an IB file" if not orphans else
                        f"records without an IB file: {', '.join(orphans)} (deleted or relabelled work)"))
    return checks


def _literal_prefix(pattern: str) -> str:
    return re.split(r"[*?\[]", pattern.split("::", 1)[0], maxsplit=1)[0]


def _explicitly_owns(owner: Any, path: str, surface: str) -> bool:
    """Does ``owner``'s Scope name the protected area itself — an entry at
    least as specific as the protecting surface — rather than cover it with a
    broader glob? A broad allowance never waives another contract's
    protection (ADR-058); an approved contract that targets the area does."""
    from dekspec.diff_confinement import matches_any_glob

    if "::" in surface:
        return False  # a Scope entry names files; it can never be as specific as a protected symbol
    protected = _literal_prefix(surface)
    return bool(protected) and any(
        matches_any_glob(path, [entry]) and _literal_prefix(entry).startswith(protected) for entry in owner.scope)


def _retirement_check(engine: Engine, ib: str, base_commit: str, active: list[str],
                      delivered: list[str]) -> Check:
    """Disposition of a retired (DEPRECATED / SUPERSEDED) IB that ran in this
    delivery. Retirement is not completion: the record is kept (checked with
    every other record), no attempt may be left open, and every implementation
    change remaining in the delivery must be accounted for. Only these are:

    * lifecycle records and bookkeeping (execution and tracker records, the
      delivered IB files, generated indexes, status-only spec edits);
    * work an active co-delivered IB owns: inside its Scope and outside every
      active IB's protected surfaces;
    * changes that predate the retired run (unchanged since its authorization
      anchor), except DekSpec state and test-runner configuration.

    The retired IB's protected surfaces stay in force, compared with the base
    whoever changed them: only an active IB whose Scope names the protected
    area itself (not a broader glob) may own such a change. Relabelling failed
    work — inside or outside the retired Scope, or on a protected surface —
    cannot land it."""
    from dekspec.diff_confinement import matches_any_glob
    from dekspec.execution.scope import (_bookkeeping_only, _is_lifecycle, _never_pre_run, _protected_hits,
                                         changed_files, predates_run)

    c = engine.contract(ib)
    _rec, _events, st = engine.state(c.ib_id)
    problems = []
    if st.open_attempt:
        problems.append(f"attempt {st.open_attempt.number} is still open — end it before retiring")
    if not st.started and not st.attempts:
        # No run, so nothing was left by one: the delivery is judged like any change
        # that delivers no executed IB.
        return Check(f"{ib}:retired", not problems,
                     f"{c.status}: retired before its run started" if not problems else "; ".join(problems))
    if st.baseline and st.baseline.get("contract_hash") != c.contract_hash():
        problems.append("its contract changed after authorization — retiring an IB changes its status only; "
                        "restore the authorized Scope, Protected Surfaces and acceptance (or amend them first)")
    anchor = (st.pre_execution_baseline or {}).get("commit")
    owners = [engine.contract(a) for a in active]
    # Contract material: every delivered IB file, and the acceptance assets active IBs
    # govern (their acceptance-integrity gate judges them). The retired IB's own assets
    # are judged like its code: unchanged since the anchor, or left by its run.
    ib_files = {engine.contract(i).rel_path for i in delivered} | {
        a for o in owners for a in o.acceptance_asset_paths()}
    notes: list[str] = []
    left: list[str] = []
    for change in changed_files(engine.repo_root, base_commit):
        paths = [p for p in (change.path, change.old_path) if p]
        hits = [(s, h) for s in c.protected if (h := _protected_hits(engine.repo_root, base_commit, change, s, notes))]
        if hits:
            if not any(all(_explicitly_owns(o, p, s) for s, _h in hits for p in paths) and not any(
                    _protected_hits(engine.repo_root, base_commit, change, s, []) for s in o.protected)
                    for o in owners):
                left.append(f"{change.path} (protected by {ib}: {hits[0][1]})")
            continue
        if all(_is_lifecycle(p, ib_files, engine.spec_root) for p in paths) or \
                _bookkeeping_only(engine.repo_root, base_commit, change, engine.spec_root):
            continue
        if any(all(matches_any_glob(p, list(o.scope)) for p in paths) and not any(
                _protected_hits(engine.repo_root, base_commit, change, s, []) for s in o.protected) for o in owners):
            continue  # active work owns it; that IB's own gate judges it
        if anchor and not any(_never_pre_run(p) for p in paths) and \
                all(predates_run(engine.repo_root, base_commit, anchor, p, engine.spec_root) for p in paths):
            continue  # predates the retired run
        where = "inside" if all(matches_any_glob(p, list(c.scope)) for p in paths) else "outside"
        left.append(f"{change.path} ({where} {ib}'s Scope)")
    if left:
        problems.append("changes remain that no active IB owns: " + ", ".join(sorted(set(left)))
                        + " — revert them, or deliver them under an active IB authorized for them")
    return Check(f"{ib}:retired", not problems,
                 f"{c.status}: record retained, no implementation remains" if not problems else "; ".join(problems))


def delivery_check(engine: Engine, ibs: list[str] | None = None, *, base: str | None = None,
                   rerun: bool = False, reuse_actor: str | None = None) -> DeliveryResult:
    """The landing gate (ADR-058). ``rerun`` re-executes acceptance and the
    base's integration command instead of trusting recorded results, and
    writes nothing — the command line (CI) always re-executes everything.

    ``reuse_actor`` (with ``rerun``; the `/implement` driver's landing gate
    only, ADR-059 stage 6): where ``reuse_actor``'s own passing delivery
    verification stands at the identical binding (:func:`_standing`),
    the IB's acceptance, and the integration command for the base's exact
    command, are not executed again; ``relied_on`` names that evidence and
    ``executed`` lists what the gate executed itself."""
    base = base or engine.base
    try:
        base_commit = resolve_base(engine.repo_root, base)
        if rerun:
            # CI: the delivery must not choose its own verification policy.
            engine = Engine(engine.repo_root, spec_root=engine.spec_root, base=base,
                            settings=load_settings_at(engine.repo_root, base_commit, spec_root=engine.spec_root))
        discovered = discover_delivery_ibs(engine, base)
        anomalies = engine.delivery_anomalies(base)
    except ScopeError as exc:
        result = DeliveryResult(ibs=[])
        result.checks.append(Check("base-resolvable", False, str(exc)))
        return result
    try:
        selected = [engine.contract(ib).ib_id for ib in ibs] if ibs else []
    except ExecutionError as exc:
        result = DeliveryResult(ibs=[])
        result.checks.append(Check("ib-selection", False, str(exc)))
        return result
    # A landing decision covers every delivered IB: an explicit selection can
    # add IBs, never hide one (a partial check is a diagnostic, not READY).
    evaluated = sorted(set(selected) | set(discovered))
    result = DeliveryResult(ibs=evaluated)
    result.checks.append(Check("ib-file-integrity", not anomalies, "; ".join(anomalies) or "no refused IB-file changes"))
    result.checks.extend(_record_history_checks(engine, base_commit))
    omitted = sorted(set(discovered) - set(selected)) if selected else []
    if omitted:
        result.checks.append(Check("delivery-coverage", False,
                                   f"the selection omits delivered IB(s) {', '.join(omitted)}; they were evaluated "
                                   "anyway, and a partial selection never lands"))
    ibs = evaluated
    if not ibs:
        result.checks.append(Check("governed-ibs", True, "this change delivers no delegated IB"))
        return result

    base_ref = base or "main"
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", base_ref, "HEAD"], cwd=str(engine.repo_root),
                          capture_output=True)
    if proc.returncode not in (0, 1):
        proc = subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{base_ref}", "HEAD"],
                              cwd=str(engine.repo_root), capture_output=True)
    current = proc.returncode == 0
    result.checks.append(Check(
        "branch-current-with-base", current,
        f"{base_ref} is an ancestor of HEAD" if current
        else f"{base_ref} has moved past this branch — rebase or merge it, then re-verify"))

    fp = engine.fingerprint()
    retired = [ib for ib in ibs if engine.contract(ib).status in RETIRED_STATUSES]
    active = [ib for ib in ibs if ib not in retired]
    for ib in retired:
        result.checks.append(_retirement_check(engine, ib, base_commit, active, ibs))
    for ib in active:
        try:
            gate = engine.evaluate_completion(ib, readonly=rerun, base=base)
        except ExecutionError as exc:
            gate = GateResult(ib=ib, checks=[Check("loadable", False, str(exc))])
        result.gates.append(gate)
        standing = _standing(engine, ib, reuse_actor, active, fp, base_commit, base) if rerun else None
        if standing is not None:
            delivery, own = standing
            result.relied_on[ib] = {"delivery": _ref(ib, delivery), "evidence": _ref(ib, own)}
            result.checks.append(Check(
                f"{ib}:own-verification", True,
                f"not re-executed: {reuse_actor}'s own passing delivery verification {ib}#{delivery.seq} "
                f"(on evidence {ib}#{own.seq}) stands at this binding"))
            continue
        if rerun:
            result.executed.append(ib)
            try:
                fresh = engine.verify(ib, "ci", base=base, record=False)
            except ExecutionError as exc:
                result.checks.append(Check(f"{ib}:independent-rerun", False, f"cannot re-execute: {exc}"))
                continue
            result.checks.append(Check(f"{ib}:independent-rerun", fresh["overall"] == "passed",
                                       "re-executed acceptance at this head: " + fresh["overall"]
                                       + ("" if fresh["overall"] == "passed" else " — " + "; ".join(
                                           _failure_reasons(fresh)))))

    policy = _integration_policy(engine, base_commit)
    relied = _standing_integration(engine, reuse_actor, active, fp, base_commit, base, policy) \
        if policy and rerun else None
    if relied is not None:
        ident, delivery = relied
        result.relied_on["integration"] = _ref(ident, delivery)
        result.checks.append(Check(
            "integrated-verification", True,
            f"not re-executed: {reuse_actor}'s own passing delivery verification {ident}#{delivery.seq} ran the "
            f"base's integration command at this binding ({policy})"))
    elif policy and rerun:
        # CI executes the base's integration command itself; a recorded
        # success is not evidence of what happens now.
        result.executed.append("integration")
        ran = _integration(engine, policy)
        changed = engine.fingerprint() != fp
        ok = ran is not None and ran["status"] == "passed" and not changed
        result.checks.append(Check(
            "integrated-verification", ok,
            f"integration command re-executed at this head: passed ({policy})" if ok else
            ("the integration command changed the repository content" if changed else
             f"integration command re-executed at this head: exit {ran['exit_code']} ({policy})"
             + (f" — {ran['tail'][-300:]}" if ran and ran.get("tail") else ""))))
    elif policy and active:
        latest = None
        for ib in active:
            _rec, _ev, st = engine.state(engine.contract(ib).ib_id)
            ev = st.latest_evidence("delivery")
            if ev and (latest is None or ev[1]["fingerprint"] == fp):
                latest = ev[1]
        integration = (latest or {}).get("integration") or {}
        problems = []
        if not latest:
            problems.append("no `dekspec delivery verify` evidence")
        else:
            if latest["fingerprint"] != fp:
                problems.append("the delivery verification predates this head")
            if not set(active) <= set(latest.get("ibs", [])):
                problems.append("the delivery verification does not cover every IB")
            if integration.get("command") != policy:
                problems.append(f"the integration command recorded ({integration.get('command') or 'none'}) is "
                                f"not the base's ({policy})")
            elif integration.get("status") != "passed":
                problems.append("the integration command failed")
            if latest["overall"] != "passed":
                problems.append("the delivery verification failed")
        result.checks.append(Check("integrated-verification", not problems,
                                   "delivery verification current at this head, integration passed" if not problems
                                   else "; ".join(problems)))
    return result
