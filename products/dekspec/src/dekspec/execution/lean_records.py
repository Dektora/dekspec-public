"""record_tests_authored and record_floor_verdict atomically append lean records.
Invalid paths, findings and returns raise ExecutionError; current gives a read-only LeanHistory.
Its floor_loop and code_loop answer disposition, round, open findings and reviewed history.
Absent history is an empty view; callers never count records or know restart boundaries, identities or limits.
Alternatives: event helpers leak ordering; mutable sessions leak restart protocols; snapshots hide both.
"""
from __future__ import annotations

from dataclasses import dataclass as _dataclass, field as _field
from pathlib import PurePosixPath as _Path

from dekspec.execution import git_reads
from dekspec.execution.engine import ExecutionError as _ExecutionError, verdict_role_stamp as _role_stamp
from dekspec.execution.record import ExecutionRecord as _Record
from dekspec.execution.scope import resolve_base as _resolve_base, ScopeError as _ScopeError
from dekspec.execution.state import fold as _fold

__all__ = ["LeanHistory", "current", "record_tests_authored", "record_floor_verdict",
           "ReviewLoop", "ReviewFinding", "ReviewedRound"]

_DESIGN_CRITERIA = frozenset((
    "deep-interface", "information-hidden", "complexity-pulled-down",
    "errors-defined-out", "no-pass-through", "interface-note",
    "tests-through-interface", "design-before-tests", "note-tested", "serves-design-intent",
))


# Both review loops share the owner's five rounds plus one final round.
_REVIEW_ROUND_LIMIT = 6


@_dataclass(frozen=True)
class ReviewFinding:
    """One failing finding, with level P1 or P2 and the reviewer's text."""
    level: str
    text: str


@_dataclass(frozen=True)
class ReviewedRound:
    """A reviewed commit (empty when unrecorded), findings and uninterpreted notes."""
    commit: str
    findings: tuple[ReviewFinding, ...]
    notes: str


@_dataclass(frozen=True)
class ReviewLoop:
    """A review decision with its standing findings and all rounds in this loop.

    Disposition is continue (review again), passed, ended (proceed with findings),
    or stopped (an owner decision is required). Before a verdict, round is zero
    and history is empty; otherwise history includes the standing round.
    """
    round: int = 0
    disposition: str = "continue"
    findings: tuple[ReviewFinding, ...] = ()
    history: tuple[ReviewedRound, ...] = ()


def _findings(verdict, findings, *, lean=True):
    """Validate input before any write; historical missing findings need no migration."""
    result = []
    for finding in findings or ():
        if not lean:
            raise _ExecutionError(f"finding {finding!r}: findings are only available on lean briefs")
        if verdict != "fail":
            raise _ExecutionError(f"finding {finding!r}: a pass cannot have a failing finding")
        parts = finding.split(maxsplit=1) if isinstance(finding, str) else []
        if len(parts) != 2 or parts[0] not in ("P1", "P2") or not parts[1].strip():
            raise _ExecutionError(f"finding {finding!r}: use 'P1 <text>' or 'P2 <text>' with non-empty text")
        result.append({"level": parts[0], "text": parts[1].strip()})
    return result


def _loop(verdicts):
    history = []
    for data in verdicts:
        findings = ()
        if data["verdict"] == "fail":
            findings = tuple(ReviewFinding(**f) for f in data.get("findings", ())) or (
                ReviewFinding("P1", data.get("notes") or "Review failed without a finding"),)
        history.append(ReviewedRound(data.get("commit", ""), findings, data.get("notes", "")))
    if not history:
        return ReviewLoop()
    findings = history[-1].findings
    disposition = "continue"
    if verdicts[-1]["verdict"] == "pass":
        disposition = "passed"
    elif len(history) >= _REVIEW_ROUND_LIMIT:
        disposition = "stopped" if any(f.level == "P1" for f in findings) else "ended"
    return ReviewLoop(len(history), disposition, findings, tuple(history))


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

    _floor_loop: ReviewLoop | None = _field(default=None, init=False, repr=False, compare=False)
    _code_loop: ReviewLoop = _field(default=ReviewLoop(), init=False, repr=False, compare=False)
    _floor_loop_start: int = _field(default=0, init=False, repr=False, compare=False)
    _code_loop_start: int = _field(default=0, init=False, repr=False, compare=False)

    @property
    def floor_loop(self) -> ReviewLoop:
        """Floor review decision and history, including prior repair commits."""
        if self._floor_loop is not None:
            return self._floor_loop
        # Retain the five-field value constructor: a supplied standing verdict
        # describes one round when no richer recorded history was supplied.
        return _loop([dict(commit=self.commit or "", verdict=self.floor, notes=self.floor_notes)]
                     if self.floor else [])

    @property
    def code_loop(self) -> ReviewLoop:
        """Code review decision and history since its last restart."""
        return self._code_loop

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
    floor_rounds, code_rounds = [], []
    preceding = []
    for event in events:
        if event.type == "attempt.started":
            attempted = True
        elif event.type == "tests.authored":
            returning = author is not None and (attempted or _interface_block(_fold(preceding)) is not None)
            returns += int(returning)
            if author is None or returning or (_loop(floor_rounds).disposition == "passed"):
                floor_rounds = []
            code_rounds = []
            author, verdict, attempted = event, None, False
            authors.add(event.data.get("actor"))
        elif event.type == "floor.verdict":
            reviewers.add(event.data.get("reviewer"))
            if (author and event.seq > author.seq
                    and event.data.get("commit") == author.data["commit"]):
                # A revised verdict on this author commit replaces its round.
                if _loop(floor_rounds).disposition != "stopped":
                    if floor_rounds and floor_rounds[-1]["commit"] == event.data["commit"]:
                        floor_rounds[-1] = {**event.data, "_seq": event.seq}
                    else:
                        floor_rounds.append({**event.data, "_seq": event.seq})
                verdict = event
        elif event.type == "verdict.recorded" and author and event.seq > author.seq:
            if code_rounds and code_rounds[-1]["verdict"] == "pass":
                code_rounds = []
            if _loop(code_rounds).disposition != "stopped":
                code_rounds.append({**event.data, "_seq": event.seq})
        elif event.type == "completion.reopened":
            code_rounds = []
        elif (event.type == "blocker.resolved"
              and event.data.get("resolution") == "operator-decision"):
            # Only Engine.unblock records restart authority. Unmarked resolutions
            # (including older records) still clear blockers through fold, but
            # cannot authorize a new loop. Never infer authority from the actor.
            # The block must also have been raised after the stopping verdict;
            # its producer and wording have no bearing on the decision.
            blocks = _fold(preceding).blockers
            for rounds in (floor_rounds, code_rounds):
                if (_loop(rounds).disposition == "stopped"
                        and any(b["seq"] > rounds[-1]["_seq"] for b in blocks)):
                    rounds.clear()
        preceding.append(event)
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
    object.__setattr__(history, "_floor_loop", _loop(floor_rounds))
    object.__setattr__(history, "_code_loop", _loop(code_rounds))
    object.__setattr__(history, "_floor_loop_start", floor_rounds[0]["_seq"] if floor_rounds else 0)
    object.__setattr__(history, "_code_loop_start", code_rounds[0]["_seq"] if code_rounds else 0)
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
    result = git_reads.run(engine.repo_root, *args, capture_output=True, text=True)
    if result.returncode:
        raise _ExecutionError(problem)
    return result.stdout if raw else result.stdout.strip()


def _ancestor(engine, old, new):
    return git_reads.run(engine.repo_root, "merge-base", "--is-ancestor", old, new, capture_output=True).returncode == 0


def _role_identities(events, kind, key):
    return {e.data.get(key, e.actor) for e in events if e.type == kind}


def _interface_block(state):
    return next((b for b in state.blockers if b.get("reason") == "acceptance-invalid"
                 and b.get("detail", "").startswith("interface:")
                 and b.get("raised_by") in state.builder_identities), None)


def _return_block(engine, events, history, commit, base):
    state = _fold(events)
    block = _interface_block(state)
    if block is None and not any(e.type == "attempt.started" and
                                (history.counts(e) or history.commit is None) for e in events):
        return None
    if history.commit is None or len(state.blockers) != 1 or block is None:
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
    return block


def _blob(engine, commit, path):
    """The bytes of ``path`` at ``commit``; None when it is absent there."""
    result = git_reads.run(engine.repo_root, "cat-file", "blob", f"{commit}:{path}", capture_output=True)
    return result.stdout if result.returncode == 0 else None


def _support_files(c, paths, read):
    """Files the adapters of the brief's runners close for its tests and for
    ``paths`` beside them (BR 68 c)."""
    from dekspec.execution.test_runners import adapter_for

    closed = set()
    for runner in dict.fromkeys(a.kind for a in c.acceptance if a.nodes):
        adapter = adapter_for(runner)
        if adapter is None:
            raise _ExecutionError(f"{c.ib_id}: DekSpec has no adapter for the test runner {runner}")
        tests = [t for a in c.acceptance if a.kind == runner for t in a.nodes]
        files = {f for f in map(adapter.file_of, tests) if f is not None}
        closed |= adapter.support(sorted(files | set(paths)), read).closed
    return closed


def _skeletons(engine, c, commit, base, paths):
    from dekspec.execution.test_runners import skeleton as _read_skeleton

    ancestor = _git(engine, "merge-base", base, commit,
                    problem=f"cannot find a common ancestor for commits {base} and {commit}")
    changed = set(_git(engine, "diff", "--name-only", "-z", ancestor, commit, raw=True,
                       problem=f"cannot compare commits {ancestor} and {commit}").split("\0"))
    protected = set(c.acceptance_asset_paths())
    result = sorted(set(paths or ()))
    support = None
    for path in result:
        parsed = _Path(path)
        if parsed.is_absolute() or ".." in parsed.parts or path != parsed.as_posix():
            raise _ExecutionError(f"skeleton {path}: path must be repository-relative and stay inside the repository")
        if path not in changed:
            raise _ExecutionError(f"skeleton {path}: commit {commit} does not change this path from its merge base")
        if support is None:
            support = _support_files(c, result, lambda rel: _blob(engine, commit, rel))
        if path in protected or path in support or path.startswith(".dekspec/execution/"):
            raise _ExecutionError(f"skeleton {path}: protected acceptance asset, support file or execution record; choose an implementation file")
        source = _blob(engine, commit, path)
        read = _read_skeleton(path, source if source is not None else b"")
        if read is None:
            continue  # a language no adapter reads: unchecked (BR 39, 47)
        if source is None:
            raise _ExecutionError(f"skeleton {path}: cannot read content at commit {commit}")
        if read.problem is not None or not read.note.strip():
            raise _ExecutionError(f"skeleton {path}: missing, blank or unparseable interface note"
                                  + (f" ({read.problem})" if read.problem else ""))
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
                         policy_revision: int | None = None, findings: list[str] | None = None) -> dict:
    """Record the independent current floor verdict under BS-045."""
    normalized = _findings(verdict, findings, lean=engine.contract(ib).is_lean)
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
        required = {c.id for c in c.acceptance if c.nodes} | {"tests-through-interface"}
        if history.skeletons:
            required |= _DESIGN_CRITERIA
        if verdict == "pass" and required - set(criteria):
            raise _ExecutionError("passing floor verdict omits: " + ", ".join(sorted(required - set(criteria))))
        data = {"commit": commit, "verdict": verdict, "reviewer": reviewer,
                "criteria": sorted(set(criteria)), "agent_role": _role_stamp("spec-reviewer", policy_revision)}
        if normalized:
            data["findings"] = normalized
        if notes:
            data["notes"] = notes
        event = _Record.append(rec, "floor.verdict", reviewer, data)
        return {"ib": c.ib_id, "seq": event.seq, **data}
