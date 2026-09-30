"""The execution engine: one production path from accepted IB to verified completion.

Every CLI verb in ``dekspec ib`` / ``dekspec delivery`` is a thin wrapper over
a method here, and every gate fails closed. Exit semantics used by the CLI:
``ExecutionError`` → refused (1), ``Blocked`` → truthful blocked outcome (3).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dekspec.diff_confinement import matches_any_glob
from dekspec.execution import acceptance as acc
from dekspec.execution.artifact_edit import append_amendment_row, set_status
from dekspec.execution.context import ContextPacket, build_context
from dekspec.execution.contract import ContractError, IBContract, load_contract
from dekspec.execution import snapshots
from dekspec.execution.fingerprint import (
    content_manifest,
    current_commit,
    fingerprint_of,
    manifest_changes,
    worktree_dirty,
)
from dekspec.execution.plan import validate_plan
from dekspec.execution.record import EXECUTION_DIRNAME, Event, ExecutionRecord, RecordIntegrityError
from dekspec.execution.scope import ScopeError, evaluate_scope
from dekspec.execution.settings import ExecutionSettings, load_settings, resolve_python
from dekspec.execution.state import RunState, fold, parse_ts

__all__ = ["Blocked", "Check", "Engine", "ExecutionError", "GateResult", "IntegrationUnknown"]

SYSTEM_ACTOR = "dekspec"
BLOCK_REASONS = (
    "attempts-exhausted", "no-progress", "stalled", "prerequisite-unavailable",
    "contract-conflict", "scope-expansion", "acceptance-invalid", "other",
)


#: IB statuses that retire work (ADR-056 §7): the record is kept; the delivery
#: gate applies a retirement disposition instead of completion.
RETIRED_STATUSES = ("DEPRECATED", "SUPERSEDED")


class ExecutionError(RuntimeError):
    """The request is refused (wrong state, failed gate, invalid input)."""


class Blocked(ExecutionError):
    """The run is blocked — a truthful outcome, never success."""


class IntegrationUnknown(ExecutionError):
    """A completion does not meet the current rules (``problem``), and the delivery
    base does not resolve here (``why``), so whether it is integrated history —
    which would exempt it — cannot be told (ADR-061). It neither counts as complete
    nor may be reopened until the base is known."""

    def __init__(self, ident: str, why: str, problem: str) -> None:
        super().__init__(f"{ident}'s completion does not hold under the current rules ({problem}), and "
                         f"whether it is integrated history cannot be told: {why}")
        self.ident, self.why, self.problem = ident, why, problem


def probe_blocker(blocker: dict[str, Any]) -> bool:
    """A blocker raised by the engine's own failed prerequisite probe — the only
    kind a passing re-probe may resolve."""
    return blocker.get("reason") == "prerequisite-unavailable" and blocker.get("raised_by") == SYSTEM_ACTOR


#: The Agent Role Specification whose policy an IB review verdict answers to
#: (ADR-061); an Intent's manual-verification verdict answers to the verifier's.
CODE_REVIEWER_ROLE = "code-reviewer"
VERIFIER_ROLE = "verifier"


def verdict_role_stamp(role_id: str, policy_revision: int | None) -> dict[str, Any]:
    """The role provenance a verdict records (IC-019).

    The role must load: a missing or malformed definition refuses the verdict,
    so no review is ever recorded against a policy nobody can read. A reviewer
    dispatched under ``policy_revision`` records only while that is still the
    role's revision — a review performed under superseded instructions must be
    repeated, not relabelled.
    """
    from dekspec.roles import RoleDefinitionError, load_role

    try:
        role = load_role(role_id)
    except RoleDefinitionError as exc:
        raise ExecutionError(f"cannot record the verdict: {exc}") from exc
    if policy_revision is not None and policy_revision != role.policy_revision:
        raise ExecutionError(
            f"the {role_id} policy changed since this review was dispatched (revision {policy_revision} → "
            f"{role.policy_revision}); the verdict was not recorded — repeat the review under the current policy")
    return role.stamp()


def verdict_policy_problem(role_id: str, verdict: dict[str, Any]) -> str | None:
    """Why a recorded verdict no longer meets its role's policy, or None."""
    from dekspec.roles import RoleDefinitionError, load_role, policy_is_current

    try:
        role = load_role(role_id)
    except RoleDefinitionError as exc:
        return f"the review policy cannot be established: {exc}"
    ok, why = policy_is_current(verdict.get("agent_role"), role)
    return None if ok else f"verdict predates a review-policy change ({why}) — a fresh review is required"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"check": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class GateResult:
    ib: str
    checks: list[Check] = field(default_factory=list)
    carried_forward: list[str] = field(default_factory=list)
    evidence_seq: int | None = None
    verdict_seq: int | None = None
    fingerprint: str | None = None

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def as_dict(self) -> dict[str, Any]:
        return {"ib": self.ib, "ok": self.ok, "fingerprint": self.fingerprint,
                "evidence_seq": self.evidence_seq, "verdict_seq": self.verdict_seq,
                "carried_forward": self.carried_forward, "checks": [c.as_dict() for c in self.checks]}


def _serialized(method):
    """Run an IB verb under that IB's record lock, so the state it validates
    is still the state when its events land (ADR-057 bounds cannot be raced)."""
    import functools

    @functools.wraps(method)
    def wrapper(self, ref, *args, **kwargs):
        ib_id = self.contract(ref).ib_id
        with self.record(ib_id).locked():
            return method(self, ref, *args, **kwargs)
    return wrapper


def integrated_completion(repo_root: Path, ident: str, rev: str) -> int | None:
    """Sequence of the current completion ``ident``'s execution record holds
    at ``rev`` (``None`` when there is none)."""
    from dekspec.execution.record import parse_record_text

    shown = subprocess.run(["git", "show", f"{rev}:{EXECUTION_DIRNAME}/{ident}/record.jsonl"], cwd=str(repo_root),
                           capture_output=True, text=True)
    if shown.returncode != 0:
        return None
    st = fold(parse_record_text(shown.stdout))
    return st.completions[-1][0] if st.completions else None


class Engine:
    def __init__(self, repo_root: Path, *, spec_root: str = "dekspec",
                 settings: ExecutionSettings | None = None, base: str | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.spec_root = spec_root
        #: The delivery's base branch (a stacked PR or release branch; default
        #: main). One context for scope, historical provenance and dependency
        #: completion, so readiness, start and completion agree with the
        #: delivery check run against the same base.
        self.base = base
        self.settings = settings or load_settings(self.repo_root, spec_root=spec_root)
        self._records: dict[str, ExecutionRecord] = {}

    # ------------------------------------------------------------------ basics
    def contract(self, ref: str) -> IBContract:
        try:
            return load_contract(self.repo_root, ref, spec_root=self.spec_root)
        except ContractError as exc:
            raise ExecutionError(str(exc)) from exc

    def record(self, artifact_id: str) -> ExecutionRecord:
        # One instance per artifact, so a lock taken for a check-then-append
        # sequence is re-entered (not re-acquired on a second descriptor).
        if artifact_id not in self._records:
            self._records[artifact_id] = ExecutionRecord(self.repo_root, artifact_id)
        return self._records[artifact_id]

    def _events(self, rec: ExecutionRecord):
        try:
            return rec.events()
        except RecordIntegrityError as exc:
            raise ExecutionError(str(exc)) from exc

    def state(self, artifact_id: str) -> tuple[ExecutionRecord, list, RunState]:
        rec = self.record(artifact_id)
        events = self._events(rec)
        return rec, events, fold(events)

    def manifest(self) -> dict[str, str]:
        return content_manifest(self.repo_root, spec_root=self.spec_root,
                                extra_excludes=self.settings.fingerprint_exclude)

    def fingerprint(self) -> str:
        return fingerprint_of(self.manifest())

    def is_complete(self, ref: str, *, base: str | None = None) -> bool:
        """COMPLETE *and* backed by an intact completion record — a status
        written by hand never counts (ADR-057). A legacy IB completes only
        historically: its COMPLETE must be provenance-backed by the committed
        history (see :meth:`historically_complete`)."""
        c = self.contract(ref)
        if c.status != "COMPLETE":
            return False
        if not c.is_delegated:
            return self.historically_complete(c, base=base or self.base)
        return self.current_completion(c.ib_id) is not None

    def unintegrated_completion_problem(self, ref: str, base: str | None = None) -> str | None:
        """Why an IB's recorded completion does not hold, or None (ADR-061).

        An integrated completion is history and always holds. For unintegrated work
        the claim stands only while no later independent review has failed, and the
        verdict the completion cites (its latest, if none is cited) meets the
        code-reviewer's current, loadable policy. A fresh FAIL is unfinished work; a
        fresh PASS after a policy change counts once `dekspec ib complete` records a
        completion citing it.

        When the base does not resolve, a completion that meets those rules still
        holds (it would hold integrated or not); one that does not raises
        :class:`IntegrationUnknown` — an unknown base is never proof of history."""
        c = self.contract(ref)
        completion = self.current_completion(c.ib_id)
        if completion is None:
            return None
        state, why = self.integration_state(c.ib_id, c.rel_path, base)
        if state == "integrated":
            return None
        problem = self._completion_rule_problem(c.ib_id, completion)
        if problem and state == "unknown":
            raise IntegrationUnknown(c.ib_id, why, problem)
        return problem

    def _completion_rule_problem(self, ib_id: str, completion: dict[str, Any]) -> str | None:
        _rec, _events, st = self.state(ib_id)
        if st.verdicts and st.verdicts[-1][1].get("verdict") != "pass":
            seq, latest = st.verdicts[-1]
            return (f"a later independent review failed (verdict #{seq} by {latest.get('reviewer')}): "
                    f"{latest.get('notes', '')[:200]}")
        cited = completion.get("verdict_seq")
        verdict = next((p for seq, p in st.verdicts if seq == cited), None) or (
            st.verdicts[-1][1] if st.verdicts else None)
        if verdict is None:
            return "its completion cites no independent review verdict"
        return verdict_policy_problem(CODE_REVIEWER_ROLE, verdict)

    def current_completion(self, ident: str) -> dict[str, Any] | None:
        """The record's current completion — its latest ``completion.recorded``
        not followed by a ``completion.reopened`` — read from an intact chain.
        Works for IB and Intent records alike."""
        rec = self.record(ident)
        if not rec.exists() or rec.verify_chain():
            return None
        st = fold(rec.events(strict=False))
        return st.completions[-1][1] if st.completions else None

    def integration_state(self, ident: str, rel_path: str, base: str | None = None) -> tuple[str, str]:
        """Where ``ident``'s completion stands against the delivery base:
        ``("integrated", "")`` — the base holds it (its execution record there ends
        in a completion, or its file there is COMPLETE), so it is history;
        ``("unintegrated", "")`` — the base resolves and does not hold it;
        ``("unknown", why)`` — the base does not resolve here, so neither can be told.
        The landing gate re-checks against the delivery's own base
        (`integrated-completions-kept`), whatever base a caller passed here."""
        from dekspec.execution.references import artifact_status
        from dekspec.execution.scope import resolve_base

        try:
            rev = resolve_base(self.repo_root, base or self.base)
        except ScopeError as exc:
            return "unknown", str(exc)
        if integrated_completion(self.repo_root, ident, rev):
            return "integrated", ""
        shown = subprocess.run(["git", "show", f"{rev}:{rel_path}"], cwd=str(self.repo_root),
                               capture_output=True, text=True)
        held = shown.returncode == 0 and artifact_status(shown.stdout) == "COMPLETE"
        return ("integrated" if held else "unintegrated"), ""

    def completed_in_base(self, ident: str, rel_path: str, base: str | None = None) -> bool:
        """Must ``ident``'s completion be treated as history — never reopened or added
        to? True when integrated, and also when the base does not resolve (never
        reopen on a guess). It is a refusal test, not proof of integration: whether a
        completion still holds asks :meth:`integration_state`, where an unknown base
        proves nothing (ADR-061)."""
        return self.integration_state(ident, rel_path, base)[0] != "unintegrated"

    @_serialized
    def reopen(self, ref: str, actor: str, reason: str, *, base: str | None = None) -> dict[str, Any]:
        """Reopen a completion that has not been integrated, so work found
        wrong before it lands (a required check failing on the landing head)
        is repaired rather than abandoned. The completion stays in the record,
        followed by the reopening; the status returns to ACCEPTED with an
        Amendment Log row; the next completion goes through the full gate
        again. A completion already in the base is history, and is refused."""
        c = self.contract(ref)
        self._require_delegated(c)
        if not reason.strip():
            raise ExecutionError("a reopening needs its reason")
        rec, _events, st = self.state(c.ib_id)
        if c.status != "COMPLETE" or not st.completions:
            raise ExecutionError(f"{c.ib_id} has no current completion to reopen")
        state, why = self.integration_state(c.ib_id, c.rel_path, base)
        if state == "unknown":
            raise ExecutionError(f"cannot tell whether {c.ib_id}'s completion is already integrated: {why} — "
                                 "fetch the base, or pass --base / set DEKSPEC_BASE; nothing is reopened on a guess")
        if state == "integrated":
            raise ExecutionError(f"{c.ib_id}'s completion is already integrated in the delivery base; "
                                 "later work needs its own IB")
        payload = {"reason": reason, "completion_seq": st.completions[-1][0],
                   "commit": current_commit(self.repo_root)}
        rec.append("completion.reopened", actor, payload)
        set_status(c.path, {"COMPLETE"}, "ACCEPTED", author=actor, change=(
            f"Reopened before integration (completion #{payload['completion_seq']}): {reason}"))
        return payload

    def historically_complete(self, contract: IBContract, base: str | None = None) -> bool:
        """A legacy IB whose completion predates this delivery: some committed
        version at or before the delivery base already carried a terminal
        status (the retired ``COMPLETED`` or ``COMPLETE``). The migration maps
        that status explicitly; no acceptance evidence is invented for it, and
        a COMPLETE written on the delivery branch itself never qualifies."""
        from dekspec.execution.history import LEGACY_TERMINAL_STATUSES, file_versions, status_of
        from dekspec.execution.scope import resolve_base

        if contract.is_delegated or contract.status != "COMPLETE":
            return False
        try:
            rev = resolve_base(self.repo_root, base)
        except ScopeError:
            return False
        return any(status_of(text) in LEGACY_TERMINAL_STATUSES
                   for _commit, _path, text in file_versions(self.repo_root, contract.rel_path, rev=rev))

    def context(self, ref: str) -> ContextPacket:
        return build_context(self.repo_root, self.contract(ref), spec_root=self.spec_root)

    def _dependency_ready(self, dep: str, base: str | None = None) -> bool:
        """A dependency is ready to build on when it is COMPLETE, or when its
        latest verification passed (it is being delivered in the same branch
        and will be reviewed with it — ADR-058). Completion of the dependent
        still requires every dependency COMPLETE."""
        c = self.contract(dep)
        if self.is_complete(dep, base=base):
            return True
        _rec, _events, st = self.state(c.ib_id)
        latest = st.latest_evidence("ib")
        return bool(latest) and latest[1].get("overall") == "passed"

    def _require_delegated(self, c: IBContract) -> None:
        problems = c.contract_problems()
        if problems:
            raise ExecutionError(f"{c.ib_id} is not an executable delegated contract: " + "; ".join(problems))

    # ----------------------------------------------------------- authorization
    def propose(self, ref: str, actor: str) -> str:
        c = self.contract(ref)
        self._require_delegated(c)
        packet = build_context(self.repo_root, c, spec_root=self.spec_root)
        if packet.problems:
            raise ExecutionError("obligation references do not resolve: " + "; ".join(packet.problems))
        set_status(c.path, {"DRAFT"}, "PROPOSED", author=actor,
                   change="Proposed for authorization (`dekspec ib propose`): contract lint clean.")
        return "PROPOSED"

    @_serialized
    def accept(self, ref: str, actor: str) -> dict[str, Any]:
        """PROPOSED → ACCEPTED: authorize execution and take the acceptance baseline."""
        c = self.contract(ref)
        self._require_delegated(c)
        if c.status != "PROPOSED":
            raise ExecutionError(f"{c.ib_id} is {c.status}; only a PROPOSED IB can be accepted")
        packet = build_context(self.repo_root, c, spec_root=self.spec_root)
        if packet.problems:
            raise ExecutionError("cannot authorize: " + "; ".join(packet.problems))
        for dep in c.depends_on:
            self.contract(dep)  # must exist and parse
        rec = self.record(c.ib_id)
        payload = acc.baseline_payload(self.repo_root, c)
        payload.update({"by": actor, "phase": "authorization",
                        "absent_assets": sorted(k for k, v in payload["assets"].items() if v is None)})
        ev = rec.append("acceptance.baselined", actor, payload)
        set_status(c.path, {"PROPOSED"}, "ACCEPTED", author=actor, change=(
            f"Accepted for execution (`dekspec ib accept`). Acceptance baseline "
            f"{acc.baseline_digest(payload)[:12]} recorded as event {ev.seq} in "
            f"{EXECUTION_DIRNAME}/{c.ib_id}/."))
        return payload

    @_serialized
    def rebaseline(self, ref: str, actor: str, reason: str) -> dict[str, Any]:
        """Refresh the baseline before execution starts (e.g. after acceptance
        tests were written). After a run starts only :meth:`amend` applies."""
        c = self.contract(ref)
        self._require_delegated(c)
        rec, _events, st = self.state(c.ib_id)
        if c.status != "ACCEPTED" or st.baseline is None:
            raise ExecutionError(f"{c.ib_id} must be ACCEPTED with a baseline before it can be re-baselined")
        if st.started:
            raise ExecutionError(
                f"{c.ib_id}'s run has started; the baseline changes only by `dekspec ib amend` "
                "with a reason and an independent reviewer")
        payload = acc.baseline_payload(self.repo_root, c)
        payload.update({"by": actor, "phase": "pre-execution", "reason": reason,
                        "absent_assets": sorted(k for k, v in payload["assets"].items() if v is None)})
        rec.append("acceptance.baselined", actor, payload)
        return payload

    @_serialized
    def amend(self, ref: str, actor: str, *, reviewer: str, reason: str) -> dict[str, Any]:
        """Recorded amendment of the acceptance contract after execution started."""
        c = self.contract(ref)
        self._require_delegated(c)
        rec, _events, st = self.state(c.ib_id)
        if st.baseline is None:
            raise ExecutionError(f"{c.ib_id} has no baseline; accept it first")
        if not st.started:
            raise ExecutionError("the run has not started; use `dekspec ib baseline` instead")
        if not reason.strip():
            raise ExecutionError("an amendment needs a reason")
        if not reviewer or reviewer in st.builder_identities:
            raise ExecutionError(
                f"the amendment must be authorized by a reviewer independent of the builder "
                f"({', '.join(sorted(st.builder_identities)) or 'none recorded'})")
        if actor != reviewer:
            raise ExecutionError(
                f"the reviewer records the amendment themselves (actor {actor!r} ≠ reviewer {reviewer!r})")
        payload = acc.baseline_payload(self.repo_root, c)
        prev = st.baseline
        changes = {
            "contract": prev.get("contract_hash") != payload["contract_hash"],
            "assets": sorted(k for k in set(prev.get("assets", {})) | set(payload["assets"])
                             if prev.get("assets", {}).get(k) != payload["assets"].get(k)),
            "runner_inputs": sorted(k for k in set(prev.get("runner_inputs", {})) | set(payload["runner_inputs"])
                                    if prev.get("runner_inputs", {}).get(k) != payload["runner_inputs"].get(k)),
        }
        payload.update({"by": actor, "reviewer": reviewer, "reason": reason, "changes": changes,
                        "previous_digest": acc.baseline_digest(prev),
                        "absent_assets": sorted(k for k, v in payload["assets"].items() if v is None)})
        event = rec.append("acceptance.amended", actor, payload)
        # The decision belongs to the durable spec, not only to the execution
        # history: the IB's Amendment Log carries it (outside the contract
        # hash, and normalized out of the fingerprint, so nothing goes stale).
        changed = [k for k, v in (("contract", changes["contract"]), ("assets", changes["assets"]),
                                  ("runner inputs", changes["runner_inputs"])) if v]
        reason_cell = " ".join(reason.split()).replace("|", "\\|")
        c.path.write_text(append_amendment_row(
            c.path.read_text(encoding="utf-8"),
            f"| {datetime.now(timezone.utc).date().isoformat()} | Substantive | Acceptance amended after execution "
            f"started (`dekspec ib amend`, execution record #{event.seq}; changed: "
            f"{', '.join(changed) or 'nothing'}): {reason_cell} | {reviewer} |"), encoding="utf-8")
        return payload

    # -------------------------------------------------------------- execution
    def _sweep_stall(self, rec: ExecutionRecord, st: RunState) -> RunState:
        att = st.open_attempt
        if att is None:
            return st
        last = parse_ts(att.last_seen or att.started)
        if datetime.now(timezone.utc) - last < timedelta(minutes=self.settings.stall_minutes):
            return st
        rec.append("attempt.ended", SYSTEM_ACTOR, {
            "attempt": att.number, "outcome": "stalled",
            "summary": f"no heartbeat for {self.settings.stall_minutes} min — closed and counted"})
        rec.append("blocker.raised", SYSTEM_ACTOR, {
            "reason": "stalled", "detail": f"attempt {att.number} stalled (no heartbeat since {att.last_seen})"})
        return fold(self._events(rec))

    @_serialized
    def start(self, ref: str, owner: str, *, takeover: bool = False, base: str | None = None) -> dict[str, Any]:
        base = base or self.base
        c = self.contract(ref)
        self._require_delegated(c)
        if c.status != "ACCEPTED":
            raise ExecutionError(f"{c.ib_id} is {c.status}; only an ACCEPTED IB can be executed")
        self._refuse_integrated(c, base)
        rec, _events, st = self.state(c.ib_id)
        if st.baseline is None:
            raise ExecutionError(f"{c.ib_id} has no acceptance baseline — accept it with `dekspec ib accept`")
        if st.completions:
            raise ExecutionError(f"{c.ib_id} already has a completion record")
        if st.started and st.owner and st.owner != owner and not takeover:
            raise ExecutionError(f"{c.ib_id}'s run is owned by {st.owner}; pass --takeover to transfer it")
        unmet = [d for d in c.depends_on if not self._dependency_ready(d, base)]
        if unmet:
            raise ExecutionError(
                f"{c.ib_id} depends on IBs that are neither COMPLETE nor verified: {', '.join(unmet)}")
        packet = build_context(self.repo_root, c, spec_root=self.spec_root)
        if packet.problems:
            raise ExecutionError("contract conflict — obligations do not resolve: " + "; ".join(packet.problems))
        fp = self.fingerprint()
        if not st.started:
            rec.append("run.started", owner, {"owner": owner, "contract_hash": c.contract_hash(),
                                              "fingerprint": fp, "commit": current_commit(self.repo_root)})
        elif st.owner != owner:
            rec.append("run.ownership-transferred", owner, {"from": st.owner, "to": owner})
        else:
            rec.append("run.resumed", owner, {"fingerprint": fp})
        rec.append("context.bound", owner, {"manifest": packet.manifest, "manifest_hash": packet.manifest_hash,
                                            "contract_hash": c.contract_hash()})
        prereq = self._probe(c)
        if prereq:
            rec.append("prerequisites.checked", owner, {"results": prereq})
            failed = [p["prerequisite"] for p in prereq if p["required"] and not p["ok"]]
            if failed:
                rec.append("blocker.raised", SYSTEM_ACTOR, {
                    "reason": "prerequisite-unavailable", "detail": "unavailable: " + ", ".join(failed)})
                raise Blocked(f"{c.ib_id} blocked: required prerequisite(s) unavailable: {', '.join(failed)}")
            # The re-probe is evidence the prerequisite is back; nothing else is
            # auto-resolved (exhaustion, stalls and conflicts need a decision).
            # Only a blocker a failed probe raised is resolved by a passing one: a
            # worker's own escalation stays for a decision, whatever reason it named.
            if st.blockers and all(probe_blocker(b) for b in st.blockers):
                rec.append("blocker.resolved", SYSTEM_ACTOR, {
                    "decision": "required prerequisites passed their probes on restart",
                    "extra_attempts": 0, "resolved": ["prerequisite-unavailable"]})
        return {"ib": c.ib_id, "owner": owner, "manifest_hash": packet.manifest_hash, "fingerprint": fp}

    def _probe(self, c: IBContract) -> list[dict[str, Any]]:
        results = []
        for p in c.prerequisites:
            try:
                proc = subprocess.run(p["probe"], shell=True, cwd=str(self.repo_root),
                                      capture_output=True, text=True, timeout=30)
                ok, tail = proc.returncode == 0, (proc.stdout + proc.stderr)[-300:]
            except subprocess.TimeoutExpired:
                ok, tail = False, "probe timed out after 30s"
            results.append({"prerequisite": p["prerequisite"], "probe": p["probe"],
                            "required": p["required"], "ok": ok, "tail": tail})
        return results

    def _refuse_integrated(self, c: IBContract, base: str | None = None) -> None:
        """Integrated work is history (ADR-057): no attempt, evidence, verdict or
        completion is added to an IB whose completion the delivery base holds.
        Only an IB that was ever completed can be integrated, so nothing else
        needs the base at all."""
        from dekspec.execution.scope import resolve_base

        if not c.is_delegated:
            return
        rec = self.record(c.ib_id)
        st = fold(rec.events(strict=False)) if rec.exists() else RunState()  # integrity is judged by each verb
        if not st.completions and not st.reopenings and c.status != "COMPLETE":
            return
        try:
            resolve_base(self.repo_root, base or self.base)
        except ScopeError as exc:
            raise ExecutionError(f"cannot tell whether {c.ib_id}'s completion is already integrated: {exc} — "
                                 "pass --base or set DEKSPEC_BASE") from exc
        if self.completed_in_base(c.ib_id, c.rel_path, base):
            raise ExecutionError(f"{c.ib_id}'s completion is already integrated in the delivery base; "
                                 "later work needs its own IB")

    def _require_active(self, c: IBContract) -> tuple[ExecutionRecord, list, RunState]:
        self._refuse_integrated(c)
        rec, events, st = self.state(c.ib_id)
        if not st.started:
            raise ExecutionError(f"{c.ib_id} has no run; start one with `dekspec ib start`")
        if st.completions:
            raise ExecutionError(f"{c.ib_id} is already complete")
        st = self._sweep_stall(rec, st)
        return rec, self._events(rec), st

    @_serialized
    def plan(self, ref: str, plan: dict[str, Any], actor: str, *, takeover: bool = False) -> dict[str, Any]:
        c = self.contract(ref)
        rec, events, st = self._require_active(c)
        payload = validate_plan(plan, c, st, events, actor, takeover=takeover)
        rec.append("plan.committed", actor, payload)
        if payload["hypothesis_deviations"]:
            rec.append("deviation.recorded", actor, {
                "kind": "plan-departs-from-hypothesis", "files": payload["hypothesis_deviations"],
                "detail": "in-scope files the IB's implementation hypothesis did not name (no permission needed)"})
        return payload

    @_serialized
    def task(self, ref: str, task_id: str, action: str, actor: str, *, note: str = "",
             evidence: str = "", takeover: bool = False) -> dict[str, Any]:
        c = self.contract(ref)
        rec, _events, st = self._require_active(c)
        task = st.tasks.get(task_id)
        if task is None:
            raise ExecutionError(f"{task_id} is not in {c.ib_id}'s current plan")
        owner = task.get("owner")
        if action == "claim":
            if task["status"] == "done":
                raise ExecutionError(f"{task_id} is already done")
            if task["status"] == "in_progress" and owner not in (None, actor) and not takeover:
                raise ExecutionError(f"{task_id} is in progress by {owner}; pass --takeover to take it over")
            undone = [d for d in task.get("depends_on", []) if st.tasks.get(d, {}).get("status") != "done"]
            if undone:
                raise ExecutionError(f"{task_id} waits on {', '.join(undone)}")
            data = {"task": task_id, "status": "in_progress", "owner": actor}
        elif action == "done":
            if owner not in (None, actor) and not takeover:
                raise ExecutionError(f"{task_id} is owned by {owner}")
            data = {"task": task_id, "status": "done", "owner": actor, "evidence": evidence or note}
        elif action == "block":
            data = {"task": task_id, "status": "blocked", "note": note}
        elif action == "release":
            data = {"task": task_id, "status": "pending", "owner": None}
        else:
            raise ExecutionError(f"unknown task action {action!r}")
        if takeover and owner and owner != actor:
            data["takeover_from"] = owner
        rec.append("task.updated", actor, data)
        return data

    # --------------------------------------------------------------- attempts
    @_serialized
    def attempt_start(self, ref: str, actor: str, *, task: str | None = None) -> dict[str, Any]:
        c = self.contract(ref)
        rec, _events, st = self._require_active(c)
        if st.blockers:
            raise Blocked(f"{c.ib_id} is blocked ({st.blockers[-1]['reason']}): resolve with `dekspec ib unblock`")
        if st.open_attempt:
            raise ExecutionError(f"attempt {st.open_attempt.number} is still open; end it first")
        allowed = self.settings.max_attempts + st.extra_attempts
        if st.attempts_used >= allowed:
            rec.append("blocker.raised", SYSTEM_ACTOR, {
                "reason": "attempts-exhausted", "detail": f"{st.attempts_used} of {allowed} attempts used"})
            raise Blocked(f"{c.ib_id} blocked: attempts exhausted ({st.attempts_used}/{allowed})")
        data = {"attempt": st.attempts_used + 1, "allowed": allowed}
        if task:
            data["task"] = task
        rec.append("attempt.started", actor, data)
        return data

    @_serialized
    def heartbeat(self, ref: str, actor: str, note: str = "") -> None:
        c = self.contract(ref)
        rec, _events, st = self._require_active(c)
        att = st.open_attempt
        if att is None:
            raise ExecutionError("no open attempt")
        rec.append("attempt.heartbeat", actor, {"attempt": att.number, "note": note})

    @_serialized
    def attempt_end(self, ref: str, actor: str, *, outcome: str, failure_class: str = "",
                    summary: str = "") -> dict[str, Any]:
        if outcome not in ("passed", "failed", "error", "abandoned"):
            raise ExecutionError("outcome must be passed | failed | error | abandoned")
        c = self.contract(ref)
        rec, events, st = self._require_active(c)
        att = st.open_attempt
        if att is None:
            raise ExecutionError("no open attempt to end")
        start_seq = next(e.seq for e in reversed(events) if e.type == "attempt.started" and e.data.get("attempt") == att.number)
        latest = next((d for seq, d in reversed(st.evidence) if seq > start_seq), None)
        progress = {
            "fingerprint": latest["fingerprint"] if latest else self.fingerprint(),
            "passing": sorted(r["id"] for r in (latest or {}).get("results", []) if r["status"] == "passed"),
            "evidence": bool(latest),
        }
        rec.append("attempt.ended", actor, {"attempt": att.number, "outcome": outcome,
                                             "failure_class": failure_class, "summary": summary,
                                             "progress": progress})
        st = fold(self._events(rec))
        verdict = {"attempt": att.number, "outcome": outcome, "progress": progress}
        blocker = self._progress_blocker(st)
        if blocker:
            rec.append("blocker.raised", SYSTEM_ACTOR, blocker)
            verdict["blocked"] = blocker
        return verdict

    def _progress_blocker(self, st: RunState) -> dict[str, Any] | None:
        ended = [a for a in st.attempts if not a.open]
        latest_ok = bool(ended) and ended[-1].outcome == "passed"
        allowed = self.settings.max_attempts + st.extra_attempts
        if st.attempts_used >= allowed and not latest_ok:
            return {"reason": "attempts-exhausted", "detail": f"{st.attempts_used} of {allowed} attempts used"}
        window = self.settings.no_progress_attempts
        if len(ended) <= window:
            return None
        stagnant = 0
        for i in range(len(ended) - window, len(ended)):
            prior = ended[:i]
            seen_fp = {a.progress.get("fingerprint") for a in prior}
            seen_pass = {ac for a in prior for ac in a.progress.get("passing", [])}
            cur = ended[i].progress
            new_pass = set(cur.get("passing", [])) - seen_pass
            if not new_pass and cur.get("fingerprint") in seen_fp and ended[i].outcome != "passed":
                stagnant += 1
        if stagnant == window:
            return {"reason": "no-progress",
                    "detail": f"{window} consecutive attempts satisfied no new condition and returned to already-seen content"}
        return None

    @_serialized
    def block(self, ref: str, actor: str, reason: str, detail: str) -> None:
        if reason not in BLOCK_REASONS:
            raise ExecutionError(f"reason must be one of {', '.join(BLOCK_REASONS)}")
        if actor == SYSTEM_ACTOR:
            raise ExecutionError(f"`{SYSTEM_ACTOR}` is the engine's own identity; record the blocker as yourself")
        c = self.contract(ref)
        rec, _events, _st = self._require_active(c)
        rec.append("blocker.raised", actor, {"reason": reason, "detail": detail})

    @_serialized
    def unblock(self, ref: str, actor: str, decision: str, *, extra_attempts: int = 0) -> None:
        c = self.contract(ref)
        rec, _events, st = self._require_active(c)
        if not st.blockers:
            raise ExecutionError(f"{c.ib_id} is not blocked")
        if actor in st.builder_identities:
            raise ExecutionError(
                f"{actor} is a builder of {c.ib_id}; unblocking is an operator decision (ADR-057)")
        if not decision.strip():
            raise ExecutionError("record the decision that resolves the blocker")
        rec.append("blocker.resolved", actor, {"decision": decision, "extra_attempts": extra_attempts,
                                                "resolved": [b["reason"] for b in st.blockers]})

    # ----------------------------------------------------------- verification
    def _integrity(self, c: IBContract, st: RunState) -> tuple[list[str], list[str]]:
        """(problems, attention): problems fail verification; attention items
        need an independent verdict's acknowledgment before completion."""
        problems: list[str] = []
        attention: list[str] = []
        base = st.baseline
        if base is None:
            return ["no acceptance baseline (accept the IB first)"], attention
        if base.get("contract_hash") != c.contract_hash():
            problems.append("the IB's binding/acceptance content changed since the baseline without `dekspec ib amend`")
        now_assets = acc.asset_hashes(self.repo_root, c)
        for path in sorted(set(now_assets) | set(base.get("assets", {}))):
            before, after = base.get("assets", {}).get(path, "untracked"), now_assets.get(path, "untracked")
            if before == after:
                continue
            if before is None and after:
                continue  # created during execution: attention, below
            if after is None:
                problems.append(f"acceptance asset {path} was deleted or renamed")
            elif before == "untracked":
                problems.append(f"acceptance asset {path} is not in the baseline (contract changed without amendment)")
            else:
                problems.append(f"acceptance asset {path} changed without an amendment")
        # Attention is judged against the last baseline taken *before* execution
        # (authorization or a pre-start refresh), so amendments cannot launder it.
        authorization = st.pre_execution_baseline or base
        for path, h in authorization.get("assets", {}).items():
            if h is None and now_assets.get(path):
                attention.append(path)
        now_inputs = acc.runner_input_hashes(self.repo_root, c)
        auth_inputs = authorization.get("runner_inputs", {})
        for path in sorted(set(now_inputs) | set(auth_inputs)):
            if now_inputs.get(path) != auth_inputs.get(path):
                attention.append(path)
        attention.extend(f"amendment:{a['seq']}" for a in st.amendments)
        return problems, sorted(set(attention))

    def _scope(self, c: IBContract, st: RunState, events: list, base: str | None):
        """Scope report for ``c`` inside its delivery (ADR-058): partners are the
        co-delivered IBs that actually ran; attribution is anchored at the
        authorization baseline's commit (the builder does not choose it)."""
        planned = [f for t in st.tasks.values() for f in t.get("files", [])]
        # A retired IB never widens the delivery's allowed scope: its leftover
        # changes must be reverted or owned by active work (delivery check).
        partners = [p for p in (self.contract(i) for i in self.delivery_ibs(base) if i != c.ib_id)
                    if p.status not in RETIRED_STATUSES]
        anchor = (st.pre_execution_baseline or {}).get("commit") or next(
            (ev.data.get("commit") for ev in events if ev.type == "run.started"), None)
        return evaluate_scope(self.repo_root, [c, *partners], base=base, spec_root=self.spec_root,
                              planned_files=planned, since=anchor)

    @property
    def python(self) -> str:
        return resolve_python(self.repo_root, self.settings.python)

    def _interpreter_problem(self) -> str | None:
        configured = self.python
        python = Path(configured)
        if python.is_absolute():
            resolved = python
        elif "/" in configured or "\\" in configured:
            resolved = self.repo_root / python  # a relative path means repo-relative
        else:
            resolved = Path(shutil.which(configured) or python)
        try:
            real = resolved.resolve()
            inside = real.is_relative_to(self.repo_root)
        except OSError:
            inside = False
        # An ignored, untracked interpreter (a local `.venv`) is environment,
        # not delivered content; one the delivery could commit is refused.
        if inside and subprocess.run(["git", "check-ignore", "-q", str(real)], cwd=str(self.repo_root),
                                     capture_output=True).returncode != 0:
            return (f"the test interpreter {configured!r} is part of the repository's content; "
                    "evidence must come from an interpreter the delivery cannot rewrite")
        return None

    def verify(self, ref: str, actor: str, *, base: str | None = None, record: bool = True,
               kind: str = "ib") -> dict[str, Any]:
        base = base or self.base
        c = self.contract(ref)
        self._require_delegated(c)
        if c.status not in ("ACCEPTED", "COMPLETE"):
            raise ExecutionError(f"{c.ib_id} is {c.status}; verification applies to ACCEPTED IBs")
        if record:
            self._refuse_integrated(c, base)
        rec, events, st = self.state(c.ib_id)
        if record and st.started and not st.completions:
            st = self._sweep_stall(rec, st)
        packet = build_context(self.repo_root, c, spec_root=self.spec_root)
        fp = self.fingerprint()
        problems, attention = self._integrity(c, st)
        interpreter = self._interpreter_problem()
        if interpreter:
            problems = problems + [interpreter]
        try:
            scope = self._scope(c, st, events, base)
            scope_dict = scope.as_dict()
        except ScopeError as exc:
            scope, scope_dict = None, {"ok": False, "violations": [{"kind": "indeterminate", "detail": str(exc)}]}
        results = [acc.run_condition(self.repo_root, cond, python=self.python,
                                     timeout=self.settings.command_timeout) for cond in c.acceptance]
        # Test-runner plugins the run loaded from the repository (beyond the
        # hashed conftest files) change what "passed" means: any that differ
        # from the authorization baseline need the reviewer's acknowledgment.
        anchor = (st.pre_execution_baseline or {}).get("commit")
        from dekspec.execution.scope import _same_as

        # Only plugins that are repository content count: an ignored local
        # `.venv` is the environment, not something the delivery ships.
        content = self.manifest()
        for plugin in sorted({pl for r in results for pl in r.get("plugins_in_repo", [])}):
            if plugin in content and not _same_as(self.repo_root, anchor, plugin):
                attention = sorted(set(attention) | {f"plugin:{plugin}"})
        failing = [r["id"] for r in results if r["kind"] != "review" and r["status"] != "passed"]
        after = self.fingerprint()
        if after != fp:
            problems = problems + [
                "running the acceptance checks changed the repository content (a check writes tracked or "
                "unignored files) — the evidence cannot be bound to what was tested"]
        if packet.problems or problems or (scope_dict.get("ok") is False):
            overall = "failed"
        elif failing:
            overall = "failed"
        else:
            overall = "passed"
        payload = {
            "kind": kind,
            "fingerprint": fp,
            "commit": current_commit(self.repo_root),
            "dirty": worktree_dirty(self.repo_root),
            "contract_hash": c.contract_hash(),
            "baseline_digest": acc.baseline_digest(st.baseline),
            "manifest_hash": packet.manifest_hash,
            "python": self.python,
            "context_problems": packet.problems,
            "integrity_problems": problems,
            "attention": attention,
            "scope": scope_dict,
            "results": results,
            "overall": overall,
        }
        if record:
            rec.append("evidence.recorded", actor, payload)
            recorded = {f for d in st.deviations for f in d.get("files", [])}
            fresh = [f for f in (scope.unplanned_in_scope if scope else []) if f not in recorded]
            if fresh:
                rec.append("deviation.recorded", actor, {
                    "kind": "unplanned-in-scope-change", "files": fresh,
                    "detail": "changed within Scope but not named by the hypothesis or plan — recorded, no permission needed"})
        return payload

    def own_evidence(self, ref: str, actor: str, *, base: str | None = None) -> Event | None:
        """The IB's latest acceptance evidence, when ``actor`` recorded it, it
        passed, and it stands at the identical binding: implementation
        fingerprint, contract hash, acceptance baseline, context manifest and
        base (the merge-base commit its scope was judged against, which the
        evidence records), under the test interpreter this engine runs.
        ``None`` otherwise, and the caller executes.

        Only the caller's *own* evidence is returned: evidence another actor
        recorded, a builder's included, is never a substitute for executing
        (ADR-057; ADR-059 stages 2 and 6)."""
        from dekspec.execution.scope import resolve_base

        c = self.contract(ref)
        _rec, events, st = self.state(c.ib_id)
        latest = next((e for e in reversed(events)
                       if e.type == "evidence.recorded" and e.data.get("kind", "ib") == "ib"), None)
        if latest is None or latest.actor != actor or latest.data.get("overall") != "passed":
            return None
        ev = latest.data
        try:
            base_commit = resolve_base(self.repo_root, base or self.base)
        except ScopeError:
            return None
        if (ev.get("scope") or {}).get("base") != base_commit \
                or ev.get("contract_hash") != c.contract_hash() \
                or ev.get("baseline_digest") != acc.baseline_digest(st.baseline) \
                or ev.get("fingerprint") != self.fingerprint() \
                or ev.get("manifest_hash") != build_context(self.repo_root, c, spec_root=self.spec_root).manifest_hash \
                or ev.get("python") != self.python:
            return None
        return latest

    # ----------------------------------------------------------------- review
    @_serialized
    def review(self, ref: str, reviewer: str, verdict: str, *, criteria: list[str] | None = None,
               acknowledge: list[str] | None = None, notes: str = "",
               policy_revision: int | None = None) -> dict[str, Any]:
        if verdict not in ("pass", "fail"):
            raise ExecutionError("verdict must be pass or fail")
        c = self.contract(ref)
        self._require_delegated(c)
        self._refuse_integrated(c)
        rec, _events, st = self.state(c.ib_id)
        if reviewer in st.builder_identities:
            raise ExecutionError(f"{reviewer} built this IB; the verdict must come from an independent reviewer")
        role = verdict_role_stamp(CODE_REVIEWER_ROLE, policy_revision)
        packet = build_context(self.repo_root, c, spec_root=self.spec_root)
        review_ids = [a.id for a in c.acceptance if a.kind == "review"]
        # Keep exactly what was reviewed, so a later change can be named path by
        # path (the verdict's carry-forward rule depends on it).
        reviewed_fp = snapshots.save(self.repo_root, c.ib_id, self.manifest())
        payload = {
            "verdict": verdict,
            "reviewer": reviewer,
            "fingerprint": reviewed_fp,
            "commit": current_commit(self.repo_root),
            "contract_hash": c.contract_hash(),
            "baseline_digest": acc.baseline_digest(st.baseline),
            "manifest_hash": packet.manifest_hash,
            "criteria": criteria or review_ids,
            "acknowledged": sorted(set(acknowledge or [])),
            "notes": notes,
            "agent_role": role,
        }
        rec.append("verdict.recorded", reviewer, payload)
        return payload

    # ------------------------------------------------------------- completion
    def _reviewed_surfaces(self, c: IBContract, st: RunState, manifest: list[dict[str, Any]]) -> list[str]:
        globs = list(c.scope) + [p.split("::", 1)[0] for p in c.protected]
        globs += c.acceptance_asset_paths()
        globs += [k.split("#", 1)[0] for k in (st.baseline or {}).get("runner_inputs", {})]
        globs += [m["path"] for m in manifest if m.get("path")]
        globs.append(c.rel_path)
        return globs

    def _stalled(self, st: RunState) -> bool:
        att = st.open_attempt
        if att is None:
            return False
        last = parse_ts(att.last_seen or att.started)
        return datetime.now(timezone.utc) - last >= timedelta(minutes=self.settings.stall_minutes)

    def evaluate_completion(self, ref: str, *, readonly: bool = False, base: str | None = None) -> GateResult:
        base = base or self.base
        c = self.contract(ref)
        gate = GateResult(ib=c.ib_id)
        checks = gate.checks
        problems = c.contract_problems()
        checks.append(Check("delegated-contract", not problems, "; ".join(problems) or "executable contract"))
        if problems:
            return gate
        unbacked = c.status == "COMPLETE" and self.current_completion(c.ib_id) is None
        checks.append(Check("authorized", c.status in ("ACCEPTED", "COMPLETE") and not unbacked,
                            f"status {c.status}" + (" without a current completion record — only "
                                                    "`dekspec ib complete` writes COMPLETE" if unbacked else "")))
        rec = self.record(c.ib_id)
        integrity = rec.verify_chain()
        # The hash chain cannot see its own tail being cut; the committed
        # history can: the working record must extend the committed one.
        committed = subprocess.run(
            ["git", "show", f"HEAD:{rec.path.relative_to(self.repo_root).as_posix()}"],
            cwd=str(self.repo_root), capture_output=True, text=True)
        if committed.returncode == 0 and rec.path.is_file() and \
                not rec.path.read_text(encoding="utf-8").startswith(committed.stdout):
            integrity = integrity + ["the working record no longer extends the committed record (events removed)"]
        checks.append(Check("record-integrity", not integrity, "; ".join(integrity) or "hash chain intact"))
        if integrity:
            return gate
        events = rec.events()
        st = fold(events)
        if st.started and not st.completions:
            if readonly:
                if self._stalled(st):
                    checks.append(Check("no-stalled-attempt", False,
                                        f"attempt {st.open_attempt.number} has no heartbeat within the stall limit"))
            else:
                st = self._sweep_stall(rec, st)
        checks.append(Check("run-recorded", st.started,
                            f"owned by {st.owner}" if st.started else
                            "no run was started — `dekspec ib start` binds the context and checks prerequisites"))
        checks.append(Check("no-active-blocker", not st.blockers,
                            "; ".join(f"{b['reason']}: {b.get('detail', '')}" for b in st.blockers) or "none"))
        unmet = [d for d in c.depends_on if not self.is_complete(d, base=base)]
        checks.append(Check("dependencies-complete", not unmet, ", ".join(unmet) or "none pending"))
        checks.append(Check("attempt-recorded", bool(st.attempts),
                            f"{len(st.attempts)} attempt(s) recorded" if st.attempts else
                            "no attempt was recorded — work runs inside `dekspec ib attempt <IB> start|end`, "
                            "which is what bounds it"))
        # Investigation precedes the committed plan (ADR-056 §3): completion
        # attests that findings were recorded, whether the run was one direct
        # pass or decomposed into tasks.
        checks.append(Check("investigation-recorded", bool(st.findings),
                            f"findings recorded (plan revision {st.plan_revision})" if st.findings else
                            "no investigation findings — commit a plan with findings (`dekspec ib plan`; "
                            "`direct: true` for a single continuous run)"))
        packet = build_context(self.repo_root, c, spec_root=self.spec_root)
        checks.append(Check("obligations-resolve", not packet.problems, "; ".join(packet.problems) or "all approved and in force"))
        current = self.manifest()
        fp = fingerprint_of(current)
        gate.fingerprint = fp
        integrity_problems, attention = self._integrity(c, st)
        interpreter = self._interpreter_problem()
        if interpreter:
            integrity_problems = integrity_problems + [interpreter]
        checks.append(Check("acceptance-integrity", not integrity_problems,
                            "; ".join(integrity_problems) or "contract, assets and baseline consistent"))

        latest = st.latest_evidence("ib")
        if latest is None:
            checks.append(Check("evidence-present", False, "no evidence recorded — run `dekspec ib verify`"))
            return gate
        seq, ev = latest
        gate.evidence_seq = seq
        stale = []
        if ev.get("fingerprint") != fp:
            stale.append("implementation content changed since verification")
        if ev.get("contract_hash") != c.contract_hash():
            stale.append("contract changed")
        if ev.get("baseline_digest") != acc.baseline_digest(st.baseline):
            stale.append("acceptance baseline changed")
        if ev.get("manifest_hash") != packet.manifest_hash:
            stale.append("a governing source changed")
        checks.append(Check("evidence-current", not stale, "; ".join(stale) or f"evidence #{seq} matches current content"))
        failing = [f"{r['id']} {r['status']}: {r.get('detail', '')}" for r in ev.get("results") or []
                   if r["kind"] != "review" and r["status"] != "passed"]
        checks.append(Check("acceptance-passed", ev.get("overall") == "passed" and not failing,
                            "; ".join(failing) or ("all deterministic conditions passed" if ev.get("overall") == "passed"
                                                   else "verification reported " + str(ev.get("overall")))))
        # Scope is re-evaluated now rather than trusted from the evidence: the
        # set of co-delivered IBs (and so the allowed union) can change after it.
        attention = sorted(set(attention) | {a for a in ev.get("attention", []) if a.startswith("plugin:")})
        try:
            scope = self._scope(c, st, events, base).as_dict()
            scope_bad = [v.get("detail") for v in scope.get("violations", [])] + list(scope.get("missing_spec_impact", []))
        except ScopeError as exc:
            scope_bad = [f"scope indeterminate: {exc}"]
        checks.append(Check("scope-and-protected-surfaces", not scope_bad, "; ".join(scope_bad) or "confined"))

        if not st.verdicts:
            checks.append(Check("independent-review", False, "no review verdict — run the review and `dekspec ib review`"))
            return gate
        vseq, verdict = st.verdicts[-1]
        gate.verdict_seq = vseq
        vproblems = []
        if verdict["verdict"] != "pass":
            vproblems.append(f"latest verdict is FAIL ({verdict.get('notes', '')})")
        if verdict["reviewer"] in st.builder_identities:
            vproblems.append(f"{verdict['reviewer']} is a builder of this IB")
        if verdict.get("contract_hash") != c.contract_hash():
            vproblems.append("verdict predates a contract change")
        if verdict.get("baseline_digest") != acc.baseline_digest(st.baseline):
            vproblems.append("verdict predates an acceptance amendment")
        stale_policy = verdict_policy_problem(CODE_REVIEWER_ROLE, verdict)
        if stale_policy and not (st.completions and
                                 self.integration_state(c.ib_id, c.rel_path, base)[0] == "integrated"):
            # Integrated completions are history (ADR-057): a later policy revision does
            # not re-judge them, only work that has not landed yet (ADR-061). Only a base
            # that resolves and holds the completion proves it integrated.
            vproblems.append(stale_policy)
        if verdict["fingerprint"] != fp:
            reviewed = snapshots.load(self.repo_root, c.ib_id, verdict["fingerprint"])
            if reviewed is None:
                vproblems.append("content changed since the verdict and the reviewed snapshot is missing or altered")
            else:
                changed = manifest_changes(reviewed, current)
                surfaces = self._reviewed_surfaces(c, st, packet.manifest)
                touched = [p for p in changed if matches_any_glob(p, surfaces) or p in surfaces]
                if touched:
                    vproblems.append("reviewed surfaces changed since the verdict: " + ", ".join(touched[:8]))
                else:
                    gate.carried_forward = changed
        review_ids = [a.id for a in c.acceptance if a.kind == "review"]
        uncovered = [r for r in review_ids if r not in verdict.get("criteria", [])]
        if uncovered:
            vproblems.append("verdict does not cover " + ", ".join(uncovered))
        unacked = [a for a in attention if a not in verdict.get("acknowledged", [])]
        if unacked:
            vproblems.append("verdict does not acknowledge " + ", ".join(unacked))
        detail = "; ".join(vproblems) or (
            f"verdict #{vseq} by {verdict['reviewer']}"
            + (f" (carried forward across {len(gate.carried_forward)} unreviewed-surface change(s))"
               if gate.carried_forward else ""))
        checks.append(Check("independent-review", not vproblems, detail))
        return gate

    @_serialized
    def complete(self, ref: str, actor: str, *, base: str | None = None) -> GateResult:
        c = self.contract(ref)
        self._refuse_integrated(c, base)
        gate = self.evaluate_completion(ref, base=base)
        if not gate.ok:
            return gate
        rec = self.record(c.ib_id)
        st = fold(self._events(rec))
        if st.open_attempt:
            rec.append("attempt.ended", actor, {
                "attempt": st.open_attempt.number, "outcome": "passed",
                "summary": "closed at completion: the completion gate passed on current evidence",
                "progress": {"fingerprint": gate.fingerprint, "evidence": True}})
        if not st.completions or st.completions[-1][1].get("fingerprint") != gate.fingerprint \
                or st.completions[-1][1].get("verdict_seq") != gate.verdict_seq:
            # A new completion cites the evidence and verdict it rests on — also when a
            # fresh review (a review-policy change, ADR-061) replaced the one cited before.
            rec.append("completion.recorded", actor, {
                "fingerprint": gate.fingerprint, "commit": current_commit(self.repo_root),
                "evidence_seq": gate.evidence_seq, "verdict_seq": gate.verdict_seq,
                "carried_forward": gate.carried_forward})
        if c.status == "ACCEPTED":
            set_status(c.path, {"ACCEPTED"}, "COMPLETE", author=actor, change=(
                f"Completed (`dekspec ib complete`): evidence #{gate.evidence_seq} and verdict "
                f"#{gate.verdict_seq} current at fingerprint {gate.fingerprint[:12]}."))
        return gate

    def delivery_ibs(self, base: str | None = None) -> list[str]:
        """Delegated IBs this branch delivers: those whose execution record in
        the diff shows a started run, plus any delegated IB the diff marks
        COMPLETE. Merely authorizing an IB (spec work) does not deliver it."""
        from dekspec.execution.scope import changed_files, resolve_base

        found: set[str] = set()
        for ch in changed_files(self.repo_root, resolve_base(self.repo_root, base)):
            for path in (ch.path, ch.old_path):
                if not path:
                    continue
                if path.startswith(EXECUTION_DIRNAME + "/"):
                    ident = path[len(EXECUTION_DIRNAME) + 1:].split("/", 1)[0]
                    if ident.startswith("IB-"):
                        rec = self.record(ident)
                        try:
                            if rec.exists() and any(e.type == "run.started" for e in rec.events(strict=False)):
                                found.add(ident)
                        except (ValueError, KeyError):
                            found.add(ident)  # an unreadable record is gated, never skipped
                elif path.startswith(f"{self.spec_root}/impl-briefs/") and path.rsplit("/", 1)[-1].startswith("IB-"):
                    try:
                        c = load_contract(self.repo_root, str(self.repo_root / path), spec_root=self.spec_root)
                    except ContractError:
                        continue  # reported by delivery_anomalies
                    if c.is_delegated and c.status == "COMPLETE":
                        found.add(c.ib_id)
        usable = []
        for ident in sorted(found):
            try:
                if self.contract(ident).is_delegated:
                    usable.append(ident)
            except ExecutionError:
                continue
        return usable

    def delivery_anomalies(self, base: str | None = None) -> list[str]:
        """IB-file changes in the delivery the gates must refuse outright: a
        status newly set to COMPLETE on an IB that cannot complete on evidence
        (legacy policy, unparseable), a delegated IB relabelled legacy, and an
        IB file that no longer parses."""
        import subprocess as _sp

        from dekspec.execution.scope import changed_files, resolve_base

        base_commit = resolve_base(self.repo_root, base)
        problems: list[str] = []
        for ch in changed_files(self.repo_root, base_commit):
            path = ch.path
            if not (path.startswith(f"{self.spec_root}/impl-briefs/") and path.rsplit("/", 1)[-1].startswith("IB-")
                    and path.endswith(".md")) or ch.status == "D":
                continue
            try:
                head = load_contract(self.repo_root, str(self.repo_root / path), spec_root=self.spec_root)
            except ContractError as exc:
                problems.append(f"{path} does not parse: {exc}")
                continue
            before = _sp.run(["git", "show", f"{base_commit}:{ch.old_path or path}"], cwd=str(self.repo_root),
                             capture_output=True, text=True)
            old_status = old_policy = None
            if before.returncode == 0:
                import re as _re

                m = _re.search(r"^\*\*Status:\*\*\s*`?([A-Za-z_]+)", before.stdout, _re.MULTILINE)
                old_status = m.group(1).upper() if m else None
                pm = _re.search(r"^\*\*Authority policy:\*\*\s*`?([A-Za-z]+)", before.stdout, _re.MULTILINE)
                old_policy = pm.group(1).lower() if pm else "legacy"
            # A legacy COMPLETE is historical only: the base already carried a
            # terminal status (the migration maps the retired COMPLETED).
            if head.status == "COMPLETE" and not head.is_delegated and old_status not in ("COMPLETE", "COMPLETED"):
                problems.append(f"{head.ib_id} is marked COMPLETE but its authority policy is legacy and its "
                                "completion does not predate this delivery — only `dekspec ib complete` on a "
                                "delegated IB records new completion")
            if old_policy == "delegated" and not head.is_delegated:
                problems.append(f"{head.ib_id} was relabelled from delegated to legacy; the authority policy "
                                "only moves legacy → delegated (ADR-055)")
        return problems

    # ----------------------------------------------------------------- queries
    def status(self, ref: str, *, base: str | None = None) -> dict[str, Any]:
        c = self.contract(ref)
        rec, _events, st = self.state(c.ib_id)
        allowed = self.settings.max_attempts + st.extra_attempts
        out: dict[str, Any] = {
            "ib": c.ib_id, "path": c.rel_path, "status": c.status, "authority_policy": c.authority_policy,
            "phase": st.phase(), "owner": st.owner,
            "attempts": {"used": st.attempts_used, "allowed": allowed,
                         "open": st.open_attempt.number if st.open_attempt else None},
            "blockers": st.blockers, "plan_revision": st.plan_revision,
            "tasks": {tid: {"status": t.get("status"), "owner": t.get("owner"), "covers": t.get("covers", [])}
                      for tid, t in st.tasks.items()},
            "deviations": len(st.deviations), "evidence": len(st.evidence), "verdicts": len(st.verdicts),
            "record_integrity": rec.verify_chain() or "ok",
        }
        if c.is_delegated and c.status in ("ACCEPTED", "COMPLETE") and st.baseline:
            # Status is a pure query: it never records anything (stall closure
            # happens on the next mutating verb).
            gate = self.evaluate_completion(ref, readonly=True, base=base)
            out["completion_gate"] = gate.as_dict()
        return out

    def ready(self, base: str | None = None) -> list[dict[str, Any]]:
        """Accepted delegated IBs whose dependencies are COMPLETE or verified
        (see :meth:`_dependency_ready`) and that no run owns."""
        base = base or self.base
        folder = self.repo_root / self.spec_root / "impl-briefs"
        out = []
        for path in sorted(folder.rglob("IB-*.md")) if folder.is_dir() else []:
            try:
                c = load_contract(self.repo_root, str(path), spec_root=self.spec_root)
            except ContractError:
                continue
            if not c.is_delegated or c.status != "ACCEPTED":
                continue
            try:
                _rec, _ev, st = self.state(c.ib_id)
            except ExecutionError:
                continue
            if st.started or st.completions:
                continue
            try:
                deps_ok = all(self._dependency_ready(d, base) for d in c.depends_on)
            except ExecutionError:
                deps_ok = False
            if deps_ok:
                out.append({"ib": c.ib_id, "path": c.rel_path, "name": c.name})
        return out
