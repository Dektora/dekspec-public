"""Step and next_step answer the next mechanical action for a lean brief, read-only.
A Step carries the operation and its assignment, including DekSpec's loop snapshots.
Callers never fold lean records or know review limits, return order or checkpoints.
Empty history starts authorship; refusals retain their distinct remedies on restart.
Alternatives: mutable sessions expose restart order; event helpers duplicate policy; one derived action hides both.
"""

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
    floor_loop: object | None = None
    code_loop: object | None = None
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
    names = ("record_tests_authored", "record_floor_verdict", "base_move_touches", "lean_guard", "lean_state",
             "own_tests", "runners_unable")
    for name in names:
        if not callable(getattr(_spec, name, None)):
            return _stop("cannot-start", f"{name} is missing from dekspec.builder_compat")
    try:
        history = _spec.lean_state(engine, ib)
    except _spec.ExecutionError as exc:
        return _stop("cannot-start", f"lean_state: {exc}")
    for answer in ("floor_loop", "code_loop"):
        if not hasattr(history, answer):
            return _stop("cannot-start", f"incompatible dekspec.builder_compat lean_state: missing {answer}")
    state = engine.state(ib)[2]
    try:
        nodes = _spec.own_tests(engine, ib)
    except _spec.ExecutionError as exc:
        return _stop("cannot-start", f"own_tests: {exc}")
    facts = dict(skeletons=history.skeletons, own_nodes=nodes,
                 floor_loop=history.floor_loop, code_loop=history.code_loop)
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
    issued = [e for e in events if e.type == "dispatch.issued"
              and (e.data.get("ib") == ib or e.data.get("role") == "resolver")]
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
    for loop_name, loop in (("floor", history.floor_loop), ("code", history.code_loop)):
        if loop.disposition == "stopped":
            detail = "; ".join(f"{f.level} {f.text}" for f in loop.findings if f.level == "P1")
            return _stop("review-not-converging", f"{ib}: {loop_name} review stopped for the owner: {detail}")
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
    if history.floor == "fail" and history.floor_loop.disposition != "ended":
        return Step("dispatch", worker="test-author", task="repair", commit=history.commit, **facts)
    if history.floor_loop.disposition not in ("passed", "ended") or history.floor is None:
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
    # A conflict starts a new verification/review cycle even when its resolution
    # restores identical content. Only the current resolver's acknowledgement
    # and records after it can satisfy that cycle.
    departure = next((e for e in reversed(events)
                      if e.type == "queue.left" and e.data.get("brief") == ib), None)
    conflict_return = departure and departure.data.get("reason") == "conflict"
    if conflict_return:
        resolver = next((e for e in reversed(issued)
                         if e.data["role"] == "resolver" and e.seq > departure.seq), None)
        if resolver and resolver.data["id"] in returned:
            build_ack = max(build_ack, returned[resolver.data["id"]].seq)
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
    if (last and last.get("verdict") == "fail" and history.code_loop.disposition != "ended"
            and last.get("fingerprint") == evidence.get("fingerprint")
            and not _spec.verdict_policy_problem(_spec.CODE_REVIEWER_ROLE, last)):
        return Step("dispatch", worker="builder", task="repair", **facts)
    failures = {ch.name: ch.detail for ch in gate.failures()}
    if ("independent-review" in failures
            or (conflict_return and len(state.verdicts) <= review.data.get("verdicts", -1))):
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
