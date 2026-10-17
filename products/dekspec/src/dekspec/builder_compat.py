"""Hides the provider boundary; adds exactly IC-020's record_tests_authored, record_floor_verdict, base_move_touches, lean_guard, the fifth call lean_state, and LeanNotBuilt; COMPAT_VERSION stays structural3-compat-v1.
lean_state(engine, ib) is read-only and returns the provider's LeanHistory snapshot (lean_records.py); it answers with lean switched off and for a lean brief with no lean record, and never raises LeanNotBuilt; LeanHistory is not exported here.
Callers use IC-020's arguments/results and never probe implementation availability, read lean records or events themselves, name the view's type or check the switch before a read.
Writes refuse invalid input without effects; read-only unbuilt calls raise LeanNotBuilt naming the facade call; lean_state refuses a brief that is not lean with ExecutionError naming the brief and "not lean", and never returns an empty view for one.
For any brief, whatever its policy or runner (IC-020 1.5.0): own_tests(engine, ib) -> tuple[str, ...] is the tests its conditions name, as the brief names them, in its order, each once, () when it names none, and reads nothing else; runners_unable(engine, ib) -> dict[str, str] maps each runner it names that cannot run here, a runner with no adapter included, to why not, {} when all can or it names no tests, running each runner's own probe and writing nothing; both refuse an unknown brief as engine.contract does (ContractError), and check_test_interpreter keeps its signature and its pytest answer. Callers never learn condition kinds, decide by a runner's name or probe a runner.
Alternatives: expose provider internals; new versioned client; a next-step call, a mapping or lean fields on RunState for the state read; the retained facade with one read call on the one view wins because Builder consumes the specified five calls and reads the answer the engine judges by. For a brief's tests: one call returning tests and probe results together (every read of the names would run programs), or check_test_interpreter widened per brief (changes its answer); two calls, one pure read and one probe, won."""

from dekspec.execution.artifact_edit import ArtifactEditError
from dekspec.execution.context import ContextPacket
from dekspec.execution.contract import ContractError, IBContract
from dekspec.execution.delivery import (
    DeliveryResult, _failure_reasons, _integration, _integration_policy,
    delivery_check, delivery_verify,
)
from dekspec.execution.engine import (
    CODE_REVIEWER_ROLE, RETIRED_STATUSES, VERIFIER_ROLE, Blocked, Engine,
    ExecutionError, ExecutionRecord, GateResult, IntegrationUnknown, probe_blocker, verdict_policy_problem,
)
from dekspec.execution.fingerprint import FingerprintError
from dekspec.execution.intent_gate import (
    intent_children, intent_complete, intent_evaluate, intent_reopen, intent_verify,
)
from dekspec.execution.plan import PlanError
from dekspec.execution.readiness import (
    AuthorityAssessment, Missing, Readiness, ReadinessTarget, TargetReadiness,
    assess_authority, check_delivery_source, check_test_interpreter, intent_completion,
)
from dekspec.execution.record import EXECUTION_DIRNAME, Event, RecordIntegrityError
from dekspec.execution.scope import ScopeError, resolve_base
from dekspec.execution.settings import ExecutionSettings
from dekspec.execution.state import RunState, fold
from dekspec.git_hooks import hooks_installed
from dekspec.roles import AgentRole, RoleDefinitionError, compose, load_role

COMPAT_VERSION = "structural3-compat-v1"

__all__ = [
    "COMPAT_VERSION", "Engine", "IBContract", "ContextPacket", "ExecutionRecord", "Event",
    "RunState", "GateResult", "ExecutionSettings", "AgentRole", "Missing", "TargetReadiness",
    "Readiness", "DeliveryResult", "Blocked", "ExecutionError", "IntegrationUnknown",
    "RoleDefinitionError", "ScopeError", "ContractError", "RecordIntegrityError", "ArtifactEditError",
    "FingerprintError", "PlanError", "CODE_REVIEWER_ROLE", "VERIFIER_ROLE", "RETIRED_STATUSES",
    "EXECUTION_DIRNAME", "dependency_ready", "probe_prerequisites", "delivery_verify", "delivery_check",
    "delivery_failure_reasons", "verify_integration", "intent_children", "intent_verify", "intent_evaluate",
    "intent_complete", "intent_reopen", "intent_completion", "load_role", "compose", "verdict_policy_problem",
    "probe_blocker", "hooks_installed", "resolve_base", "completion_receipt", "fold", "ReadinessTarget",
    "AuthorityAssessment", "assess_authority", "check_delivery_source", "check_test_interpreter",
    "own_tests", "runners_unable",
]


def dependency_ready(engine: Engine, dep: str, base: str | None = None) -> bool:
    return engine._dependency_ready(dep, base=base)


def probe_prerequisites(engine: Engine, contract: IBContract) -> list[dict]:
    return engine._probe(contract)


def delivery_failure_reasons(evidence: dict) -> list[str]:
    return _failure_reasons(evidence)


def verify_integration(engine: Engine, *, base_commit: str | None = None) -> dict | None:
    return _integration(engine, _integration_policy(engine, base_commit))


def completion_receipt(engine: Engine, ref: str) -> dict | None:
    """Current Spec judgment plus strict, cited evidence/verdict record references.

    Unfinished or invalid completions yield no receipt. Broken record chains refuse.
    This preserves the existing completion gate; it does not repair retained defects.
    """
    contract = engine.contract(ref)
    events = engine.record(contract.ib_id).events(strict=True)
    completions = fold(events).completions
    if not completions or not engine.evaluate_completion(ref, readonly=True).ok:
        return None
    seq, data = completions[-1]
    by_seq = {event.seq: event for event in events}
    evidence = by_seq.get(data.get("evidence_seq"))
    verdict = by_seq.get(data.get("verdict_seq"))
    if not (evidence and evidence.type == "evidence.recorded" and evidence.data.get("overall") == "passed"):
        return None
    ended = engine.contract(ref).is_lean and lean_state(engine, ref).code_loop.disposition == "ended"
    if not (verdict and verdict.type == "verdict.recorded"
            and (verdict.data.get("verdict") == "pass" or ended)):
        return None
    return {"seq": seq, "hash": by_seq[seq].hash,
            "evidence_seq": evidence.seq, "verdict_seq": verdict.seq}


# These operations retain the provider's single implementation and signatures.
from dekspec.execution.evidence_scope import LeanNotBuilt  # noqa: E402
from dekspec.execution.lean_records import (  # noqa: E402
    LeanHistory as _LeanHistory,
    current as _current_lean_history,
    record_tests_authored,
    record_floor_verdict,
)

__all__ += ["record_tests_authored", "record_floor_verdict", "base_move_touches",
            "lean_guard", "lean_state", "LeanNotBuilt"]


def base_move_touches(engine: Engine, ib: str, old: str, new: str) -> list[str]:
    """IC-020 read-only base query, or LeanNotBuilt naming this call."""
    from dekspec.execution import evidence_scope

    return evidence_scope.base_move_touches(engine, ib, old, new)


def lean_guard(engine: Engine, *, base: str, head: str,
               ibs: list[str] | None = None) -> DeliveryResult:
    """IC-020 read-only guard, or LeanNotBuilt naming this call."""
    from dekspec.execution import lean_tests

    return lean_tests.guard(engine, base=base, head=head, ibs=ibs)


def lean_state(engine: Engine, ib: str) -> _LeanHistory:
    """Read a lean brief's current history, regardless of status or switch."""
    contract = engine.contract(ib)
    if not contract.is_lean:
        raise ExecutionError(f"{contract.ib_id} is not lean")
    return _current_lean_history(engine, ib)


def own_tests(engine: Engine, ib: str) -> tuple[str, ...]:
    """The tests ``ib``'s conditions name, exactly as the brief writes them,
    in the brief's order and each once; () when no condition names tests.
    Any policy, status or runner; reads the brief only. An unknown brief
    refuses as ``engine.contract`` does."""
    contract = _brief(engine, ib)
    return tuple(dict.fromkeys(test for condition in contract.acceptance for test in condition.nodes))


def runners_unable(engine: Engine, ib: str) -> dict[str, str]:
    """Each test runner ``ib``'s conditions name that cannot run in the
    project here, mapped to the reason (a runner DekSpec has no adapter for
    included); {} when every one can, or when no condition names tests.
    Runs each runner's own probe in this environment, like
    ``probe_prerequisites``; writes nothing. An unknown brief refuses as
    ``engine.contract`` does."""
    from dekspec.execution.test_runners import CannotAnswer, adapter_for

    unable: dict[str, str] = {}
    for runner in dict.fromkeys(c.kind for c in _brief(engine, ib).acceptance if c.nodes):
        adapter = adapter_for(runner)
        if adapter is None:
            unable[runner] = f"DekSpec has no adapter for the test runner {runner}"
            continue
        try:
            reason = adapter.ready(engine.repo_root, engine.settings)
        except CannotAnswer as exc:
            reason = str(exc)
        if reason:
            unable[runner] = reason
    return unable


def _brief(engine: Engine, ib: str) -> IBContract:
    """The brief's contract; an unknown or unreadable brief raises the
    ContractError ``engine.contract`` reports."""
    from dekspec.execution.contract import load_contract

    return load_contract(engine.repo_root, ib, spec_root=engine.spec_root)
