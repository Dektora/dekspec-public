"""Public Step and next_step(engine, run_id, ib, *, base_ref, record_error=None) answer one read-only question: the next mechanical action for a lean brief; identical records/git give the same immutable Step.
Step carries operation and arguments: dispatch(worker, task, assignment facts), record-tests(commit, author, skeletons), reset(source commit), verify/complete/land(brief), or stop(kind, detail); paths are repository-relative.
Hides order, checkpoints, five-call availability, floor bounds and returns; callers never fold lean records or decide which count, and the module reads current commit, skeletons, floor/notes and returns only through spec.lean_state.
Empty history starts authorship and interrupted work resumes normally, without a session or new writer; a refused record is passed back as record_error, never a caller-derived returning flag.
Distinct remedies stay distinct: cannot-start for unavailable/refused calls (including first record), review-not-converging for failed rounds, review-not-recorded for silence, interface-not-returned for unsafe/refused returns; guard-only completion failures repair, others are completion-refused; no verdict is inferred.
Alternatives: mutable begin/review/return sessions expose restart/order; separate stage helpers duplicate policy in callers; one derived next action wins because every restart asks the same question."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from typing import Literal as _Literal
import subprocess as _subprocess
from pathlib import Path as _Path

from dekspec import builder_compat as _spec

__all__ = ["Step", "next_step"]


@_dataclass(frozen=True)
class Step:
    """One mechanical action and immutable assignment facts, never a verdict.

    Unused facts have empty defaults. A strategy reason requests the existing
    shared recovery allowance; kind names the stop if that allowance is spent.
    """

    operation: _Literal["dispatch", "record-tests", "reset", "verify", "complete", "land", "stop"]
    ib: str = ""
    worker: _Literal["", "test-author", "floor-reviewer", "builder", "reviewer"] = ""
    task: str = ""
    commit: str = ""
    author: str = ""
    skeletons: tuple[str, ...] = ()
    own_nodes: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    interface_problem: str | None = None
    strategy_reason: str | None = None
    verdicts: int = 0
    kind: str = ""
    detail: str = ""


def _git(engine, *args: str) -> str:
    result = _subprocess.run(["git", *args], cwd=engine.repo_root, capture_output=True, text=True)
    if result.returncode:
        raise _spec.ExecutionError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def _stop(kind: str, detail: str) -> Step:
    return Step("stop", kind=kind, detail=detail)


def _available(engine, ib: str, base_ref: str) -> None:
    """Invalid writer probes must refuse before effects (IC-020, OI 23)."""
    probes = (
        ("record_tests_authored", dict(commit="", author="", actor="implement-driver", skeletons=[])),
        ("record_floor_verdict", dict(commit="", verdict="fail", reviewer="", criteria=[])),
    )
    for name, kwargs in probes:
        try:
            getattr(_spec, name)(engine, ib, **kwargs)
        except _spec.LeanNotBuilt:
            raise
        except _spec.ExecutionError:
            pass  # the deliberately invalid write refused without effects
        else:
            raise _spec.ExecutionError(f"{name}: invalid availability probe did not refuse")
    base = _git(engine, "rev-parse", base_ref)
    _spec.base_move_touches(engine, ib, base, base)
    _spec.lean_guard(engine, base=base, head=base, ibs=[])


def _return_step(engine, ib, history, state, author, base_ref):
    blocks = state.blockers
    block = next((b for b in blocks if b.get("reason") == "acceptance-invalid"
                  and b.get("detail", "").startswith("interface:")
                  and b.get("raised_by") in state.builder_identities), None)
    if block is None:
        return None
    detail = block["detail"]
    reason = None
    if history.returns >= 2:
        reason = "2 returns used"
    elif len(blocks) != 1:
        reason = "also blocked"
    elif history.commit and _git(engine, "merge-base", history.commit, base_ref) != _git(
            engine, "merge-base", "HEAD", base_ref):
        reason = "base merged"
    if reason:
        return _stop("interface-not-returned", f"{reason}: {detail}")
    # A dispatched author owns its partial work even if its reply was lost.
    returning = author and author.data.get("interface_problem") == detail and author.data.get("commit") == history.commit
    if not returning and (state.open_attempt or _git(
            engine, "diff", "--name-only", history.commit, "--", ".",
            ":(exclude).dekspec/execution", ":(exclude).dekbuilder")):
        return Step("reset", commit=history.commit)
    return Step("dispatch", worker="test-author", task="repair", commit=history.commit,
                interface_problem=detail)


def _other_delivery(engine, run_id, ib):
    """A rejected mixed delivery still owns its briefs until it is resolved.

    Observe existing worktrees rather than starting a second worker for the same
    brief under a differently worded request. This reads operational records,
    never another brief's lean history.
    """
    path = None
    for line in _git(engine, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = _Path(line[len("worktree "):])
        elif line.startswith("branch refs/heads/implement/") and path != engine.repo_root:
            slug = line.removeprefix("branch refs/heads/implement/")
            other_id = f"RUN-{slug.upper()}"
            if other_id == run_id:
                continue
            other = _spec.Engine(path, base=engine.base)
            events = other.record(other_id).events()
            auth = next((e.data for e in events if e.type == "run.requested"), {})
            blocked = None
            for event in events:
                if event.type == "blocker.recorded" and event.data.get("key") == "lean-delivery":
                    blocked = event.data
                elif event.type == "blocker.cleared" and event.data.get("key") == "lean-delivery":
                    blocked = None
            if ib in auth.get("ibs", ()) and blocked:
                return _stop("cannot-start", f"{ib}: {other_id}: {blocked['detail']}")
    return None


def next_step(engine, run_id, ib, *, base_ref, record_error=None) -> Step:
    """Derive an action without writing state.

    Pass a refused record as its exception. For a failed completion result,
    pass ExecutionError(result): the existing exception transports the provider's
    GateResult unchanged, so this module alone chooses its distinct remedy.
    """
    names = ("record_tests_authored", "record_floor_verdict", "base_move_touches", "lean_guard", "lean_state")
    for name in names:
        if not callable(getattr(_spec, name, None)):
            return _stop("cannot-start", f"{name} is missing from dekspec.builder_compat")
    try:
        history = _spec.lean_state(engine, ib)
    except _spec.ExecutionError as exc:
        return _stop("cannot-start", f"lean_state: {exc}")
    state = engine.state(ib)[2]
    nodes = tuple(node for ac in engine.contract(ib).acceptance if ac.kind == "pytest" for node in ac.nodes)
    facts = dict(skeletons=history.skeletons, own_nodes=nodes)
    if record_error is not None:
        result = record_error.args[0] if record_error.args else None
        if isinstance(result, _spec.GateResult):
            failures = tuple(f"{ch.name}: {ch.detail}" for ch in result.failures())
            if result.failures() and {ch.name for ch in result.failures()} <= {
                    "test-files-unchanged", "skeleton-interface-kept"}:
                return Step("dispatch", worker="builder", task="repair", findings=failures,
                            strategy_reason="; ".join(failures), kind="no-convergence", **facts)
            return _stop("completion-refused", "; ".join(failures))
        returning = any(b.get("reason") == "acceptance-invalid" and b.get("detail", "").startswith("interface:")
                        for b in state.blockers)
        return _stop("interface-not-returned" if returning else "cannot-start", str(record_error))

    events = engine.record(run_id).events()
    issued = [e for e in events if e.type == "dispatch.issued" and e.data.get("ib") == ib]
    returned = {e.data["id"]: e for e in events if e.type == "dispatch.returned"}
    author = next((e for e in reversed(issued) if e.data["role"] == "test-author"), None)
    if author and author.data["id"] in returned:
        reply = returned[author.data["id"]]
        # ack's checkpoint contains this exact dispatch return; record-only
        # checkpoints afterwards must never be mistaken for authored content.
        commit = _git(engine, "log", "-1", "--format=%H", "--fixed-strings",
                      f"--grep=test-author {author.data['key']} returned ({author.data['id']})")
        if not commit:
            return _stop("cannot-start", "test-author checkpoint is missing")
        if commit != history.commit:
            return Step("record-tests", commit=commit, author=author.data["actor"],
                        skeletons=tuple(reply.data.get("skeletons", ())))

    returning = _return_step(engine, ib, history, state, author, base_ref)
    if returning:
        return returning
    if state.blockers:
        detail = "; ".join(f"{b['reason']}: {b.get('detail', '')}" for b in state.blockers)
        if {b["reason"] for b in state.blockers} <= {"attempts-exhausted", "no-progress", "stalled"}:
            return Step("dispatch", worker="builder", task="repair", findings=(detail,),
                        strategy_reason=detail, kind="no-convergence", **facts)
        return _stop("blocked", detail)
    # Persisted terminal decisions survive another next, without another dispatch.
    blocks = {}
    for event in events:
        if event.type == "blocker.recorded":
            blocks[event.data["key"]] = event.data
        elif event.type == "blocker.cleared":
            blocks.pop(event.data["key"], None)
    blocker = blocks.get(f"lean:{ib}")
    if blocker and blocker["kind"] in {"no-convergence", "completion-refused"}:
        return _stop(blocker["kind"], blocker["detail"])
    if history.commit is None:
        other = _other_delivery(engine, run_id, ib)
        if other:
            return other
        if author is None:
            try:
                _available(engine, ib, base_ref)
            except _spec.ExecutionError as exc:
                return _stop("cannot-start", str(exc))
        return Step("dispatch", worker="test-author", task="build")
    if history.floor == "fail":
        failed = {e.data.get("commit") for e in issued if e.data["role"] == "test-author"
                  and e.data.get("findings") and not e.data.get("interface_problem")}
        if len(failed | {history.commit}) >= 3:
            return _stop("review-not-converging", f"{ib}: three failed floor rounds; {history.floor_notes}")
        return Step("dispatch", worker="test-author", task="repair", commit=history.commit,
                    findings=(history.floor_notes,))
    if not history.floor_passed:
        quiet = sum(e.data["id"] in returned for e in issued
                    if e.data["role"] == "floor-reviewer" and e.data.get("commit") == history.commit)
        if quiet >= 3:
            return _stop("review-not-recorded", f"{ib}: three floor reviews returned without a verdict")
        return Step("dispatch", worker="floor-reviewer", commit=history.commit, **facts)

    built = next((e for e in reversed(issued) if e.data["role"] == "builder"
                  and (author is None or e.seq > author.seq)), None)
    if built is None:
        return Step("dispatch", worker="builder", task="build", **facts)
    if built.data["id"] not in returned:
        return Step("dispatch", worker="builder", task="resume",
                    findings=tuple(built.data.get("reasons", ())), **facts)
    build_ack = returned[built.data["id"]].seq
    verification = next((e for e in reversed(events) if e.type == "verification.reported"
                         and e.data.get("artifact") == ib and e.data.get("kind") == "ib"
                         and e.seq > build_ack), None)
    gate = engine.evaluate_completion(ib, readonly=True, base=base_ref)
    if verification is None or any(not ch.ok and ch.name == "evidence-current" for ch in gate.checks):
        return Step("verify", ib=ib)
    evidence = verification.data["result"]
    if evidence.get("overall") != "passed":
        return Step("dispatch", worker="builder", task="repair",
                    findings=tuple(_spec.delivery_failure_reasons(evidence)), **facts)
    review = next((e for e in reversed(issued) if e.data["role"] == "reviewer" and e.seq > build_ack), None)
    if review is None or review.data["id"] not in returned:
        return Step("dispatch", worker="reviewer", verdicts=len(state.verdicts), **facts)
    last = state.verdicts[-1][1] if state.verdicts else None
    if last and last.get("verdict") == "fail" and last.get("fingerprint") == evidence.get("fingerprint")             and not _spec.verdict_policy_problem(_spec.CODE_REVIEWER_ROLE, last):
        detail = f"independent review ({last.get('reviewer')}) failed: {last.get('notes', '')}"
        exhausted = state.attempts_used >= engine.settings.max_attempts + state.extra_attempts
        return Step("dispatch", worker="builder", task="repair", findings=(detail,),
                    strategy_reason=detail if exhausted else None, kind="review-not-converging", **facts)
    failures = {ch.name: ch.detail for ch in gate.failures()}
    if "independent-review" in failures:
        silent = 0
        for dispatch in reversed(issued):
            if dispatch.data["role"] != "reviewer" or dispatch.data["id"] not in returned:
                continue
            if dispatch.data.get("verdicts", -1) < len(state.verdicts):
                break
            silent += 1
        if silent >= 3:
            return _stop("review-not-recorded", f"{ib}: three code reviews returned without a verdict")
        return Step("dispatch", worker="reviewer", verdicts=len(state.verdicts), **facts)
    if state.completions and gate.ok:
        return Step("land", ib=ib)
    return Step("complete", ib=ib)
