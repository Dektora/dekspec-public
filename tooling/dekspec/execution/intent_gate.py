"""Intent completion from its IBs and its outcome evidence (ADR-057).

An Intent no longer carries IMPLEMENTING / TESTPASS / MERGED: it completes when
every IB that names it as parent is COMPLETE and its own Verification commands
(the ADR-029 outcome test among them) pass against current content. Manual
verification entries need an independent verdict. Evidence lives in the
Intent's execution record (``.dekspec/execution/INT-NNN/``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dekspec.constraint_compiler.parser import IntentParseError, parse_intent
from dekspec.execution import acceptance as acc
from dekspec.execution.artifact_edit import set_status
from dekspec.execution.contract import AcceptanceCondition, ContractError, load_contract
from dekspec.execution.engine import (
    VERIFIER_ROLE,
    Check,
    Engine,
    ExecutionError,
    GateResult,
    IntegrationUnknown,
    verdict_policy_problem,
    verdict_role_stamp,
)
from dekspec.execution.fingerprint import current_commit
from dekspec.execution.state import fold

__all__ = ["intent_children", "intent_complete", "unintegrated_intent_completion_problem", "intent_evaluate", "intent_reopen",
           "intent_review", "intent_verify"]


def _intent(engine: Engine, ref: str) -> tuple[Path, dict[str, Any]]:
    folder = engine.repo_root / engine.spec_root / "intents"
    path = Path(ref) if ref.endswith(".md") else next(iter(sorted(folder.glob(f"{ref}-*.md"))), None)
    if path is None or not Path(path).is_file():
        raise ExecutionError(f"no Intent file for {ref}")
    try:
        return Path(path), parse_intent(path)
    except IntentParseError as exc:
        raise ExecutionError(str(exc)) from exc


def intent_children(engine: Engine, intent_id: str) -> list[Any]:
    base = engine.repo_root / engine.spec_root / "impl-briefs"
    out = []
    for p in sorted(base.rglob("IB-*.md")) if base.is_dir() else []:
        try:
            c = load_contract(engine.repo_root, str(p), spec_root=engine.spec_root)
        except ContractError:
            continue
        if c.parent == intent_id:
            out.append(c)
    return out


def _conditions(ir: dict[str, Any]) -> list[AcceptanceCondition]:
    conds = []
    for i, v in enumerate(ir.get("verification", []), start=1):
        if v.get("manual"):
            conds.append(AcceptanceCondition(f"V-{i}", v["name"], "review",
                                             review=v.get("manual_rationale") or v["cmd"]))
        else:
            conds.append(AcceptanceCondition(f"V-{i}", v["name"], "command", command=v["cmd"]))
    return conds


def _integration(engine: Engine, ir: dict[str, Any], path: Path) -> tuple[str, str]:
    """The Intent's completion against the delivery base (see
    :meth:`Engine.integration_state`); a completion that no longer stands is
    ``unintegrated``."""
    if engine.current_completion(ir["id"]) is None:
        return "unintegrated", ""
    return engine.integration_state(ir["id"], str(Path(path).resolve().relative_to(engine.repo_root)))


def _refuse_integrated_intent(engine: Engine, ir: dict[str, Any], path: Path) -> None:
    from dekspec.execution.scope import ScopeError, resolve_base

    rel = str(Path(path).resolve().relative_to(engine.repo_root))
    if engine.current_completion(ir["id"]) is None:
        return
    try:
        resolve_base(engine.repo_root, engine.base)
    except ScopeError as exc:
        raise ExecutionError(f"cannot tell whether {ir['id']}'s completion is already integrated: {exc} — "
                             "pass --base or set DEKSPEC_BASE") from exc
    if engine.completed_in_base(ir["id"], rel):
        raise ExecutionError(f"{ir['id']}'s completion is already integrated in the delivery base; "
                             "later work needs its own Intent")


def intent_verify(engine: Engine, ref: str, actor: str, *, record: bool = True) -> dict[str, Any]:
    path, ir = _intent(engine, ref)
    if record:
        _refuse_integrated_intent(engine, ir, path)
    conds = _conditions(ir)
    if not conds:
        raise ExecutionError(f"{ir['id']} declares no Verification commands")
    results = [acc.run_condition(engine.repo_root, c, python=engine.python,
                                 timeout=engine.settings.command_timeout) for c in conds]
    overall = "passed" if all(r["status"] in ("passed", "needs-review") for r in results) else "failed"
    payload = {"kind": "intent", "fingerprint": engine.fingerprint(), "commit": current_commit(engine.repo_root),
               "results": results, "overall": overall}
    if record:
        engine.record(ir["id"]).append("evidence.recorded", actor, payload)
    return payload


def _builders(engine: Engine, children: list[Any]) -> set[str]:
    ids: set[str] = set()
    for c in children:
        _rec, _ev, st = engine.state(c.ib_id)
        ids |= st.builder_identities
    return ids


def intent_review(engine: Engine, ref: str, reviewer: str, verdict: str, notes: str = "", *,
                  policy_revision: int | None = None) -> dict[str, Any]:
    _path, ir = _intent(engine, ref)
    _refuse_integrated_intent(engine, ir, _path)
    if reviewer in _builders(engine, intent_children(engine, ir["id"])):
        raise ExecutionError(f"{reviewer} built one of {ir['id']}'s IBs; the verdict must be independent")
    role = verdict_role_stamp(VERIFIER_ROLE, policy_revision)
    payload = {"verdict": verdict, "reviewer": reviewer, "fingerprint": engine.fingerprint(),
               "commit": current_commit(engine.repo_root), "notes": notes, "agent_role": role}
    engine.record(ir["id"]).append("verdict.recorded", reviewer, payload)
    return payload


def unintegrated_intent_completion_problem(engine: Engine, ref: str) -> str | None:
    """Why a completed Intent's recorded completion does not hold, or None.

    Integrated completions are history (ADR-057). For an unintegrated one, each
    child IB's completion must still hold, and the manual-verification
    attestation, if its outcome needs one, must satisfy the same rule the
    completion gate applies (``manual-verification-attested``): a PASS, by
    someone who built none of its IBs, for the current content, under the
    verifier's current policy (ADR-061). A fresh FAIL, a missing attestation, or
    an attestation for other content therefore never restores the claim. When the
    base does not resolve, a claim that fails these rules raises
    :class:`IntegrationUnknown` (see :meth:`Engine.unintegrated_completion_problem`)."""
    path, ir = _intent(engine, ref)
    if engine.current_completion(ir["id"]) is None:
        return None
    state, why = _integration(engine, ir, path)
    if state == "integrated":
        return None
    problem = None
    for c in intent_children(engine, ir["id"]):
        try:
            child = engine.unintegrated_completion_problem(c.ib_id)
        except IntegrationUnknown as exc:
            child = exc.problem
        if child:
            problem = f"its IB {c.ib_id}: {child}"
            break
    if problem is None:
        gate = intent_evaluate(engine, ir["id"])
        manual = next((ch for ch in gate.checks if ch.name == "manual-verification-attested"), None)
        if manual is not None and not manual.ok:
            problem = f"its manual verification is not attested: {manual.detail}"
    if problem and state == "unknown":
        raise IntegrationUnknown(ir["id"], why, problem)
    return problem


def intent_evaluate(engine: Engine, ref: str) -> GateResult:
    _path, ir = _intent(engine, ref)
    gate = GateResult(ib=ir["id"])
    gate.checks.append(Check("authorized", ir["status"] in ("ACCEPTED", "COMPLETE"), f"status {ir['status']}"))
    children = intent_children(engine, ir["id"])
    incomplete = [c.ib_id for c in children if not engine.is_complete(str(c.path))]
    gate.checks.append(Check("child-ibs", bool(children) and not incomplete,
                             "no IB names this Intent as parent" if not children
                             else (f"incomplete: {', '.join(incomplete)}" if incomplete
                                   else f"{len(children)} IB(s) complete")))
    rec = engine.record(ir["id"])
    st = fold(rec.events())
    fp = engine.fingerprint()
    gate.fingerprint = fp
    latest = st.latest_evidence("intent")
    if latest is None:
        gate.checks.append(Check("outcome-evidence", False, "no evidence — run `dekspec intent verify`"))
        return gate
    seq, ev = latest
    gate.evidence_seq = seq
    ok = ev["fingerprint"] == fp and ev["overall"] == "passed"
    gate.checks.append(Check("outcome-evidence", ok,
                             f"evidence #{seq} current and passing" if ok else
                             ("stale — content changed since verification" if ev["fingerprint"] != fp
                              else "verification failed: " + "; ".join(
                                  f"{r['id']} {r['status']}" for r in ev["results"] if r["status"] == "failed"))))
    if any(r["status"] == "needs-review" for r in ev["results"]):
        verdict = st.verdicts[-1][1] if st.verdicts else None
        builders = _builders(engine, children)
        stale_policy = verdict_policy_problem(VERIFIER_ROLE, verdict) if verdict else None
        if stale_policy and _integration(engine, ir, _path)[0] == "integrated":
            stale_policy = None  # integrated completions are history (ADR-057); ADR-061 re-judges only unlanded work
        if verdict is None:
            why = "no independent `dekspec intent review` verdict"
        elif verdict["verdict"] != "pass":
            why = f"the latest attestation is a FAIL ({verdict.get('notes', '')[:200]})"
        elif verdict["fingerprint"] != fp:
            why = "the attestation is for other content — the content changed since it was recorded"
        elif verdict["reviewer"] in builders:
            why = f"{verdict['reviewer']} built one of its IBs"
        else:
            why = stale_policy
        gate.checks.append(Check("manual-verification-attested", not why,
                                 "independent verdict current" if not why else
                                 f"manual verification needs a current, passing, independent attestation: {why}"))
    return gate


def intent_reopen(engine: Engine, ref: str, actor: str, reason: str, *, base: str | None = None) -> dict[str, Any]:
    """Reopen an Intent completion that has not been integrated (see
    :meth:`Engine.reopen`); its outcome is verified and completed again."""
    path, ir = _intent(engine, ref)
    if not reason.strip():
        raise ExecutionError("a reopening needs its reason")
    current = engine.current_completion(ir["id"])
    if ir["status"] != "COMPLETE" or current is None:
        raise ExecutionError(f"{ir['id']} has no current completion to reopen")
    rel = str(Path(path).resolve().relative_to(engine.repo_root))
    state, why = engine.integration_state(ir["id"], rel, base)
    if state == "unknown":
        raise ExecutionError(f"cannot tell whether {ir['id']}'s completion is already integrated: {why} — "
                             "fetch the base, or pass --base / set DEKSPEC_BASE; nothing is reopened on a guess")
    if state == "integrated":
        raise ExecutionError(f"{ir['id']}'s completion is already integrated in the delivery base")
    rec = engine.record(ir["id"])
    with rec.locked():
        st = fold(rec.events(strict=False))
        if not st.completions:
            raise ExecutionError(f"{ir['id']} has no current completion to reopen")
        payload = {"reason": reason, "completion_seq": st.completions[-1][0],
                   "commit": current_commit(engine.repo_root)}
        rec.append("completion.reopened", actor, payload)
    set_status(path, {"COMPLETE"}, "ACCEPTED", author=actor,
               change=f"Reopened before integration (completion #{payload['completion_seq']}): {reason}")
    return payload


def intent_complete(engine: Engine, ref: str, actor: str) -> GateResult:
    path, ir = _intent(engine, ref)
    _refuse_integrated_intent(engine, ir, path)
    gate = intent_evaluate(engine, ref)
    current = engine.current_completion(ir["id"])
    if gate.ok and ir["status"] == "COMPLETE" and current and current.get("fingerprint") != gate.fingerprint:
        # Re-verified at new, unintegrated content: record the completion at what lands.
        engine.record(ir["id"]).append("completion.recorded", actor,
                                       {"fingerprint": gate.fingerprint, "evidence_seq": gate.evidence_seq})
    if gate.ok and ir["status"] == "ACCEPTED":
        engine.record(ir["id"]).append("completion.recorded", actor,
                                       {"fingerprint": gate.fingerprint, "evidence_seq": gate.evidence_seq})
        set_status(path, {"ACCEPTED"}, "COMPLETE", author=actor,
                   change=f"Completed (`dekspec intent complete`): child IBs complete, outcome evidence "
                          f"#{gate.evidence_seq} current at {gate.fingerprint[:12]}.")
    return gate
