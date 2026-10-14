"""Hides git validation, ordering, returns and identities; record_tests_authored and record_floor_verdict use the IC-020 S0 signatures and atomically raise ExecutionError naming invalid writes (BS-045 BR 10-14,37,42,47,50-52; stale role revision).
current(engine, ib) returns a read-only LeanHistory snapshot: commit, skeletons (tuple), floor ("pass", "fail" or None when no verdict counts: the one stored verdict fact), floor_passed (bool, exactly floor == "pass", stored nowhere), floor_notes (str), returns (int), counts(event) and builder_problems(actor); refresh it after writes.
floor_notes is the standing verdict's reviewer text, passed on as data, unchanged and never interpreted, and "" when no verdict stands or it gave none; returns is the number of returns in the whole record and has one home, which the return check also reads against its limit.
counts means the event follows the current author; builder_problems returns named actor/role refusals for every past test author or floor reviewer, including before returns, and [] for allowed actors; it does not judge floor currency or attempt limits.
Absent history is normal: commit=None, skeletons=(), floor=None, floor_passed/counts=False, floor_notes="", returns=0 and builder_problems=[]; callers never inspect events, sequence numbers, identity sets or return protocols.
Alternatives: exposed events/identity sets or a begin/return/finish session with attempt authorization; two verdict booleans or an enum; atomic writes plus one history view with one three-valued verdict win by hiding the protocol without owning attempt limits or allowing an impossible value."""
from __future__ import annotations

import ast as _ast
import subprocess as _subprocess
from dataclasses import dataclass as _dataclass, field as _field
from pathlib import PurePosixPath as _Path

from dekspec.execution.engine import ExecutionError as _ExecutionError, verdict_role_stamp as _role_stamp
from dekspec.execution.record import ExecutionRecord as _Record
from dekspec.execution.scope import resolve_base as _resolve_base, ScopeError as _ScopeError
from dekspec.execution.state import fold as _fold

__all__ = ["LeanHistory", "current", "record_tests_authored", "record_floor_verdict"]

_DESIGN_CRITERIA = frozenset((
    "deep-interface", "information-hidden", "complexity-pulled-down",
    "errors-defined-out", "no-pass-through", "interface-note",
    "tests-through-interface", "design-before-tests", "note-tested", "serves-design-intent",
))


@_dataclass(frozen=True)
class LeanHistory:
    """Current author/floor view; counts hides event ordering from callers."""
    commit: str | None = None
    skeletons: tuple[str, ...] = ()
    floor: str | None = None
    floor_notes: str = ""
    returns: int = 0
    _authors: frozenset[str] = _field(default=frozenset(), init=False, repr=False, compare=False)
    _reviewers: frozenset[str] = _field(default=frozenset(), init=False, repr=False, compare=False)
    _author_seq: int = _field(default=0, init=False, repr=False, compare=False)

    @property
    def floor_passed(self) -> bool:
        """Whether the standing floor verdict passes."""
        return self.floor == "pass"

    def builder_problems(self, actor: str) -> list[str]:
        """Identity refusals across the whole history; empty means allowed."""
        problems = []
        for identities, role in ((self._authors, "test author"),
                                 (self._reviewers, "floor reviewer")):
            if actor in identities:
                problems.append(f"{actor} is a {role}; cannot build this brief")
        return problems

    def counts(self, event) -> bool:
        """Whether this event follows the current test-author record."""
        return self.commit is not None and event.seq > self._author_seq


def _history(events):
    author = verdict = None
    authors, reviewers = set(), set()
    returns, attempted = 0, False
    for event in events:
        if event.type == "attempt.started":
            attempted = True
        elif event.type == "tests.authored":
            returns += int(author is not None and attempted)
            author, verdict, attempted = event, None, False
            authors.add(event.data.get("actor"))
        elif event.type == "floor.verdict":
            reviewers.add(event.data.get("reviewer"))
            if (author and event.seq > author.seq
                    and event.data.get("commit") == author.data["commit"]):
                verdict = event
    history = LeanHistory(
        commit=author.data["commit"] if author else None,
        skeletons=tuple(author.data.get("skeletons", ())) if author else (),
        floor=verdict.data["verdict"] if verdict else None,
        floor_notes=verdict.data.get("notes", "") if verdict else "",
        returns=returns,
    )
    object.__setattr__(history, "_authors", frozenset(authors))
    object.__setattr__(history, "_reviewers", frozenset(reviewers))
    object.__setattr__(history, "_author_seq", author.seq if author else 0)
    return history


def current(engine, ib: str) -> LeanHistory:
    """Absent history has empty skeletons and no passing floor."""
    return _history(engine.record(engine.contract(ib).ib_id).events())


def _contract(engine, ib):
    c = engine.contract(ib)
    if not c.is_lean:
        raise _ExecutionError(f"{c.ib_id} is not lean")
    problems = c.contract_problems(settings=engine.settings)
    if problems:
        raise _ExecutionError("; ".join(problems))
    if c.status != "ACCEPTED":
        raise _ExecutionError(f"{c.ib_id} must be ACCEPTED")
    return c


def _git(engine, *args, problem, raw=False):
    result = _subprocess.run(["git", *args], cwd=engine.repo_root, capture_output=True, text=True)
    if result.returncode:
        raise _ExecutionError(problem)
    return result.stdout if raw else result.stdout.strip()


def _ancestor(engine, old, new):
    return _subprocess.run(["git", "merge-base", "--is-ancestor", old, new],
                           cwd=engine.repo_root, capture_output=True).returncode == 0


def _role_identities(events, kind, key):
    return {e.data.get(key, e.actor) for e in events if e.type == kind}


def _return_block(engine, events, history, commit, base):
    if not any(e.type == "attempt.started" and
               (history.counts(e) or history.commit is None) for e in events):
        return None
    state = _fold(events)
    blockers = state.blockers
    if (history.commit is None or len(blockers) != 1
            or blockers[0].get("reason") != "acceptance-invalid"
            or not blockers[0].get("detail", "").startswith("interface:")
            or blockers[0].get("raised_by") not in state.builder_identities):
        raise _ExecutionError("return requires the only open block to be a builder's interface: acceptance-invalid block")
    if history.returns >= 2:
        raise _ExecutionError("at most two returns may be recorded")
    if _git(engine, "merge-base", base, commit,
            problem=f"cannot find a common ancestor for commits {base} and {commit}") != _git(
                engine, "merge-base", base, history.commit,
                problem=f"cannot find a common ancestor for commits {base} and {history.commit}"):
        raise _ExecutionError("return changed the merge base; base was merged since the test-author commit")
    parent = _git(engine, "rev-parse", "--verify", commit + "^",
                  problem=f"cannot read the first parent of commit {commit}")
    changed = _git(engine, "diff", "--name-only", history.commit, parent, "--", ".",
                   ":(exclude).dekspec/execution",
                   problem=f"cannot compare commits {history.commit} and {parent}")
    if changed:
        raise _ExecutionError("return first parent contains content outside the current test-author commit: " + changed)
    return blockers[0]


def _skeletons(engine, c, commit, base, paths):
    ancestor = _git(engine, "merge-base", base, commit,
                    problem=f"cannot find a common ancestor for commits {base} and {commit}")
    changed = set(_git(engine, "diff", "--name-only", "-z", ancestor, commit, raw=True,
                       problem=f"cannot compare commits {ancestor} and {commit}").split("\0"))
    protected = set(c.acceptance_asset_paths())
    result = sorted(set(paths or ()))
    for path in result:
        parsed = _Path(path)
        if (parsed.is_absolute() or ".." in parsed.parts or path != parsed.as_posix()
                or path not in changed or path in protected
                or parsed.name == "conftest.py" or path.startswith(".dekspec/execution/")):
            raise _ExecutionError(f"skeleton {path}: must be a changed implementation file, not a protected acceptance asset or record")
        if path.endswith(".py"):
            source = _git(engine, "show", f"{commit}:{path}", raw=True,
                          problem=f"skeleton {path}: cannot read content at commit {commit}")
            try:
                note = _ast.get_docstring(_ast.parse(source))
            except (SyntaxError, ValueError):
                note = None
            if not note or not note.strip():
                raise _ExecutionError(f"skeleton {path}: missing, blank or unparseable module docstring")
    return result


def record_tests_authored(engine, ib: str, *, commit: str, author: str, actor: str,
                          skeletons: list[str] | None = None) -> dict:
    """Record an author commit, or refuse atomically under BS-045."""
    c = _contract(engine, ib)
    rec = engine.record(c.ib_id)
    with rec.locked():
        c = _contract(engine, ib)
        events = rec.events()
        history = _history(events)
        state = _fold(events)
        if not author.strip() or not actor.strip():
            raise _ExecutionError("author and actor must name an identity")
        forbidden = (state.builder_identities | _role_identities(events, "floor.verdict", "reviewer")
                     | _role_identities(events, "verdict.recorded", "reviewer"))
        if author in forbidden:
            raise _ExecutionError(f"{author} is a builder or reviewer and cannot author tests")
        resolved = _git(engine, "rev-parse", "--verify", commit + "^{commit}",
                        problem=f"commit {commit} cannot be resolved")
        if resolved != commit:
            raise _ExecutionError("commit must be a full commit id")
        if not _ancestor(engine, commit, "HEAD"):
            raise _ExecutionError(f"commit {commit} is not reachable from HEAD")
        try:
            base = _resolve_base(engine.repo_root, engine.base)
        except _ScopeError as exc:
            raise _ExecutionError(str(exc)) from exc
        if _ancestor(engine, commit, base):
            raise _ExecutionError(f"commit {commit} is already reachable from the base")
        paths = _skeletons(engine, c, commit, base, skeletons)
        block = _return_block(engine, events, history, commit, base)
        data = {"commit": commit, "actor": author, "skeletons": paths}
        event = _Record.append(rec, "tests.authored", actor, data)
        if block:
            rec.append("blocker.resolved", actor, {
                "decision": f"test-author return {commit} resolves interface block",
                "resolved": [block["reason"]], "extra_attempts": 0})
        return {"ib": c.ib_id, "seq": event.seq, **data}


def record_floor_verdict(engine, ib: str, *, commit: str, verdict: str, reviewer: str,
                         criteria: list[str], notes: str = "",
                         policy_revision: int | None = None) -> dict:
    """Record the independent current floor verdict under BS-045."""
    c = _contract(engine, ib)
    rec = engine.record(c.ib_id)
    with rec.locked():
        c = _contract(engine, ib)
        events = rec.events()
        history = _history(events)
        if not history.commit or commit != history.commit:
            raise _ExecutionError("floor verdict commit must be the current test-author commit")
        if not reviewer.strip():
            raise _ExecutionError("reviewer must name an identity")
        forbidden = _fold(events).builder_identities | _role_identities(events, "tests.authored", "actor")
        if reviewer in forbidden:
            raise _ExecutionError(f"{reviewer} is a test-author or builder; floor reviewer must be independent")
        if verdict not in ("pass", "fail"):
            raise _ExecutionError("verdict must be pass or fail")
        allowed = {c.id for c in c.acceptance} | _DESIGN_CRITERIA
        unknown = set(criteria) - allowed
        if unknown:
            raise _ExecutionError("unknown criteria: " + ", ".join(sorted(unknown)))
        required = {c.id for c in c.acceptance if c.kind == "pytest"} | {"tests-through-interface"}
        if history.skeletons:
            required |= _DESIGN_CRITERIA
        if verdict == "pass" and required - set(criteria):
            raise _ExecutionError("passing floor verdict omits: " + ", ".join(sorted(required - set(criteria))))
        data = {"commit": commit, "verdict": verdict, "reviewer": reviewer,
                "criteria": sorted(set(criteria)), "agent_role": _role_stamp("spec-reviewer", policy_revision)}
        if notes:
            data["notes"] = notes
        event = _Record.append(rec, "floor.verdict", reviewer, data)
        return {"ib": c.ib_id, "seq": event.seq, **data}
