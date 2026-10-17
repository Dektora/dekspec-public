"""guard(engine, *, base: str, head: str, ibs: list[str] | None = None) -> DeliveryResult judges committed head against base, unions added ibs with delivered briefs, and returns seven BR 29 checks naming faulty nodes/kinds, paths/names or identities; CLI prints them and maps ok to 0/1.
completion_checks(engine, ib: str) -> list[Check] gives the same judgement for working content without lean-single-brief; may_approve(engine, ib: str, path: str) -> bool answers protected membership, False for skeletons/outside paths, not reviewer eligibility (Engine.review owns that refusal).
These read-only queries hide current-author/floor selection, protected sets, red execution, name comparison and git cleanup: callers need no history, sequencing or cleanup; returns invalidate earlier floors/approvals, while identity separation reads all history.
Ordinary record/test/name/identity failures are checks; an unknown commit raises ExecutionError naming it, and unreadable history refuses. No lean delivery succeeds as lean-briefs: none; no skeleton succeeds as skeletons: none, and skeletons in a language no test runner adapter reads are unchecked: no caller recovery is needed.
Tests, their support files and skeletons are read only through the adapter of the runner a condition names (test_runners); a question an adapter cannot answer fails the check that asked.
Files, refs, worktrees and events stay unchanged; existing DeliveryResult/Check fields suffice, with no new public names, parameters, exceptions or return fields.
Alternatives: separate checks leak sequencing/cleanup; a stateful judge adds lifecycle work; the three queries keep both gates consistent and review membership independent, so are easiest for callers.
"""

from __future__ import annotations

import io as _io
import os as _os
import re as _re
import subprocess as _subprocess
import tarfile as _tarfile
from dataclasses import replace as _replace
from pathlib import Path as _Path, PurePosixPath as _PurePath
from tempfile import TemporaryDirectory as _TemporaryDirectory

from dekspec.execution import git_reads
from dekspec.execution import acceptance as _acceptance
from dekspec.execution.contract import load_contract as _load_contract, ContractError as _ContractError
from dekspec.execution.delivery import DeliveryResult as _DeliveryResult
from dekspec.execution.engine import (
    Check as _Check, ExecutionError as _ExecutionError, verdict_policy_problem as _policy_problem,
)
from dekspec.execution.fingerprint import (
    is_tracker_record as _is_tracker_record, normalize_governed_markdown as _normalize_governed,
)
from dekspec.execution.lean_records import _DESIGN_CRITERIA, _history
from dekspec.execution.record import ExecutionRecord as _Record, RecordIntegrityError as _RecordError, is_record_file as _is_record
from dekspec.execution.settings import (
    load_settings_at as _settings_at, resolve_python as _resolve_python,
    _worktree_setup_at,
)
from dekspec.execution.state import fold as _fold
from dekspec.execution.test_runners import (
    CannotAnswer as _CannotAnswer, adapter_for as _adapter_for, skeleton as _read_skeleton,
    _protected_paths,
)

__all__ = ["guard", "completion_checks", "may_approve"]


def _git(root, *args):
    result = git_reads.run(root, *args, capture_output=True)
    if result.returncode:
        raise _ExecutionError(f"git {' '.join(args)}: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def _commit(root, ref):
    return _git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def _base_commit(engine):
    # scope.resolve_base returns HEAD's merge base, but protection must also
    # see changes made on the base branch after the author started.
    refs = [engine.base] if engine.base else ["main", "origin/main", "master", "origin/master"]
    for ref in refs:
        try:
            return _commit(engine.repo_root, ref)
        except _ExecutionError:
            if engine.base:
                raise
    raise _ExecutionError("cannot resolve a base commit: " + ", ".join(refs))


class _View:
    """Read immutable git objects, or working bytes, without an index/worktree."""

    def __init__(self, engine, revision=None):
        self.engine, self.revision = engine, revision
        self.entries = {}
        if revision is not None:
            for row in _git(engine.repo_root, "ls-tree", "-r", "-z", revision).split(b"\0"):
                if row:
                    metadata, path = row.split(b"\t", 1)
                    self.entries[path.decode()] = metadata.split()

    def read(self, path):
        if self.revision is None:
            target = self.engine.repo_root / path
            if not target.resolve().is_relative_to(self.engine.repo_root.resolve()):
                raise _ExecutionError(f"{path}: working path leaves repository")
            return target.read_bytes() if target.is_file() else None
        entry = self.entries.get(path)
        if entry is None:
            return None
        if entry[1] != b"blob":
            raise _ExecutionError(f"{path}: not a readable file at {self.revision}")
        return _git(self.engine.repo_root, "cat-file", "blob", entry[2].decode())

    def contract(self, ib):
        if self.revision is None:
            return self.engine.contract(ib)
        # Keep the existing parser/identity resolver, without exporting code or
        # letting a checkout's specification stand in for the judged commit.
        with _TemporaryDirectory(prefix="dekspec-lean-contract-") as temp:
            root = _Path(temp)
            for path in self.entries:
                if (path.startswith(self.engine.spec_root + "/")
                        and _PurePath(path).name.startswith("IB-") and path.endswith(".md")):
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(self.read(path))
            try:
                return _load_contract(root, ib, spec_root=self.engine.spec_root)
            except _ContractError as exc:
                raise _ExecutionError(f"{ib} at {self.revision}: {exc}") from exc

    def events(self, ib):
        path = f".dekspec/execution/{ib}/record.jsonl"
        content = self.read(path)
        if content is None:
            return []
        try:
            if content and not content.endswith(b"\n"):
                raise ValueError("incomplete record tail")
            with _TemporaryDirectory(prefix="dekspec-lean-record-") as temp:
                record = _Record(_Path(temp), ib)
                record.dir.mkdir(parents=True)
                record.path.write_bytes(content)
                events = record.events()
                if any(not isinstance(e.data, dict) for e in events):
                    raise ValueError("event data is not an object")
                return events
        except (ValueError, KeyError, TypeError, AttributeError, _RecordError) as exc:
            raise _ExecutionError(f"{ib}: unreadable history: {exc}") from exc


def _origin(engine, author, base):
    return _git(engine.repo_root, "merge-base", author, base).decode().strip()


def _adapters(contract):
    """The adapter of each runner the brief's conditions name, once each."""
    found = {}
    for condition in contract.acceptance:
        if condition.nodes and condition.kind not in found:
            adapter = _adapter_for(condition.kind)
            if adapter is None:
                raise _ExecutionError(f"{contract.ib_id} {condition.id}: DekSpec has no adapter for "
                                      f"the test runner {condition.kind}")
            found[condition.kind] = adapter
    return list(found.values())


def _protected(engine, contract, author, base, skeletons):
    origin = _origin(engine, author, base)
    paths = set(_git(engine.repo_root, "diff", "--no-renames", "--name-only", "-z",
                     origin, author).decode().strip("\0").split("\0")) - {""}
    paths = {p for p in paths if not (_is_record(p) or _is_tracker_record(p))} - set(skeletons)
    # BR 25 / 68 (c): each runner closes the support files of these tests.
    read = _View(engine, author).read
    changed = sorted(paths)
    adapters = _adapters(contract)
    if adapters:
        paths = set().union(*(_protected_paths(adapter, changed, read) for adapter in adapters))
    return origin, paths - set(skeletons)


def _author(events, ib):
    event = next((e for e in reversed(events) if e.type == "tests.authored"), None)
    if event is None:
        return None
    data = event.data
    if (not isinstance(data.get("commit"), str) or not isinstance(data.get("actor"), str)
            or not isinstance(data.get("skeletons", []), list)
            or any(not isinstance(p, str) or _PurePath(p).is_absolute()
                   or ".." in _PurePath(p).parts or str(_PurePath(p)) != p
                   for p in data.get("skeletons", []))):
        raise _ExecutionError(f"{ib}: malformed tests.authored record")
    return event


def _identity_problems(events):
    builders = _fold(events).builder_identities
    roles = [builders]
    for kind, field in (("tests.authored", "actor"), ("floor.verdict", "reviewer"),
                        ("verdict.recorded", "reviewer")):
        roles.append({e.data.get(field, e.actor) for e in events if e.type == kind})
    clashes = set()
    for index, identities in enumerate(roles):
        for other in roles[index + 1:]:
            clashes |= identities & other
    return sorted(str(identity) for identity in clashes)


def _floor_check(contract, events, author):
    verdict = next((e for e in reversed(events) if author and e.seq > author.seq
                    and e.type == "floor.verdict" and e.data.get("commit") == author.data["commit"]), None)
    if verdict is None:
        return "no floor verdict after current tests.authored"
    data = verdict.data
    ended = _history(events).floor_loop.disposition == "ended"
    if _history(events).floor_loop.disposition == "stopped":
        return "floor review stopped for the owner; resolve with ib unblock"
    if data.get("verdict") != "pass" and not ended:
        return f"floor verdict {data.get('verdict')}: {data.get('reviewer')}"
    criteria = data.get("criteria")
    required = {c.id for c in contract.acceptance if c.nodes} | {"tests-through-interface"}
    if author.data.get("skeletons"):
        required |= _DESIGN_CRITERIA
    allowed = {c.id for c in contract.acceptance} | _DESIGN_CRITERIA
    if not isinstance(criteria, list) or any(not isinstance(c, str) for c in criteria):
        return "floor verdict has malformed criteria"
    if (not ended and required - set(criteria)) or set(criteria) - allowed:
        return "floor verdict criteria: " + ", ".join(sorted((required - set(criteria)) | (set(criteria) - allowed)))
    if not data.get("reviewer") or verdict.actor != data["reviewer"]:
        return "floor verdict actor does not match reviewer"
    return _policy_problem("spec-reviewer", data)


def _approvals(events, author):
    verdict = next((e for e in reversed(events) if e.type == "verdict.recorded"), None)
    if not verdict or not author or verdict.seq <= author.seq or verdict.data.get("verdict") != "pass":
        return set()
    entries = verdict.data.get("approved_test_changes", [])
    # Older imported records used a path/reason map; the verb writes the
    # contracted list. Both forms still require an exact path and a reason.
    if isinstance(entries, dict):
        entries = [{"path": p, "reason": r} for p, r in entries.items()]
    if not isinstance(entries, list):
        return set()
    return {e["path"] for e in entries if isinstance(e, dict) and isinstance(e.get("path"), str)
            and isinstance(e.get("reason"), str) and e["reason"].strip()}


def _skeleton_check(author_view, head_view, skeletons):
    problems, unchecked = [], []
    for path in skeletons:
        before = _read_skeleton(path, author_view.read(path) or b"")
        if before is None:
            unchecked.append(path + ": unchecked")
            continue
        source = head_view.read(path)
        after = _read_skeleton(path, source) if source is not None else None
        problem = before.problem if before.problem is not None else (after.problem if after else None)
        if problem is not None:
            problems.append(f"{path}: cannot parse skeleton: {problem}")
            continue
        after_names = after.names if after is not None else frozenset()
        if before.names != after_names or source is None:
            problems.append(f"{path}: added {', '.join(sorted(after_names - before.names)) or 'none'}; "
                            f"removed {', '.join(sorted(before.names - after_names)) or 'none'}"
                            + ("; missing" if source is None else ""))
    return _Check("skeleton-interface-kept", not problems,
                  "; ".join(problems + unchecked) or "skeletons: " + (", ".join(skeletons) or "none"))


def _red_environment(engine, root, base, settings):
    """Build the author's environment from base policy, or retain legacy selection.

    Returns the interpreter and timeout. Setup/selection failures name their cause
    through ExecutionError; callers turn them into a failed check, never evidence.
    The adapter judges whether this interpreter can run its tests.
    No caller-substituted interpreter participates when setup is configured.
    """
    command = _worktree_setup_at(engine.repo_root, base)
    if not command:
        return _resolve_python(engine.repo_root, settings.python), settings.command_timeout
    policy = _settings_at(engine.repo_root, base, spec_root=engine.spec_root)
    env = _acceptance.clean_env(PYTHONDONTWRITEBYTECODE="1")
    try:
        setup = _subprocess.run(command, shell=True, cwd=root, env=env,
                                capture_output=True, text=True, timeout=policy.command_timeout)
    except (OSError, _subprocess.SubprocessError) as exc:
        raise _ExecutionError(f"worktree setup failed: {exc}") from exc
    if setup.returncode:
        raise _ExecutionError(f"worktree setup failed (exit {setup.returncode}): "
                              + (setup.stdout + setup.stderr)[-1500:])
    configured = policy.python
    candidate = configured or (".venv/Scripts/python.exe" if _os.name == "nt" else ".venv/bin/python")
    python = _resolve_python(root, candidate)
    # An explicitly absolute policy is used as written. Every other selection
    # must stay in the checkout, including bare names that PATH could supply.
    if not _Path(candidate).expanduser().is_absolute() and not _Path(
            _os.path.abspath(python)).is_relative_to(root):
        raise _ExecutionError(f"checkout interpreter {python} is outside the checkout")
    return python, policy.command_timeout


def _red_check(engine, contract, author_view, base_view, settings, base):
    """BR 26 at the test author's commit, in a checkout outside the working
    tree; each runner's adapter runs and reads its own tests."""
    problems = []
    author = author_view.revision
    with _TemporaryDirectory(prefix="dekspec-lean-red-") as temp:
        root = _Path(temp).resolve()
        with _tarfile.open(fileobj=_io.BytesIO(_git(engine.repo_root, "archive", author))) as archive:
            archive.extractall(root, filter="data")
        try:
            python, timeout = _red_environment(engine, root, base, settings)
        except _ExecutionError as exc:
            return _Check("red-at-test-author-commit", False, str(exc))
        for condition in contract.acceptance:
            if not condition.nodes:
                continue
            adapter = _adapter_for(condition.kind)
            if adapter is None:
                problems.append(f"{condition.id}: DekSpec has no adapter for the test runner {condition.kind}")
                continue
            try:
                problems.extend(_red_problems(
                    engine, condition, adapter, author_view, base_view,
                    _replace(settings, python=python, command_timeout=timeout), root))
            except _CannotAnswer as exc:
                problems.append(f"{condition.id}: {exc}")
    return _Check("red-at-test-author-commit", not problems, "; ".join(problems) or "all nodes meet red/preservation rules")


def _red_problems(engine, condition, adapter, author_view, base_view, settings, checkout):
    """One condition's red-check findings: its new tests fail on their own
    assertion and declare a basis, its preserved tests pass, and the run has no fault."""
    run = adapter.run(condition.nodes, project=engine.repo_root, settings=settings,
                      timeout=condition.timeout or settings.command_timeout, checkout=checkout)
    if not run.outcomes:
        # The runner reported nothing about its tests: each one carries the run's faults.
        return [f"{node}: {fault}" for node in condition.nodes for fault in run.faults or ("no report",)]
    problems = []
    for outcome in run.outcomes:
        if not outcome.ran:
            problems.append(f"{outcome.test}: {outcome.result}")
            continue
        source = adapter.source(outcome.test, author_view.read)
        kind = "xfail" if source.expected_failure else outcome.result
        preserved = (source.text is not None
                     and source.text == adapter.source(outcome.test, base_view.read).text)
        expected = "passed" if preserved else "genuine-red"
        if kind != expected:
            problems.append(f"{outcome.test}: {kind} (expected {expected})")
        if not preserved and not source.bases:
            problems.append(f"{outcome.test}: missing basis")
    problems.extend(f"{condition.id}: {fault}" for fault in run.faults)
    return problems


def _judge(engine, contract, events, head_view, base, settings):
    author = _author(events, contract.ib_id)
    skeletons = author.data.get("skeletons", []) if author else []
    detail = "skeletons: " + (", ".join(skeletons) or "none")
    authored_problem = None
    commit = author.data["commit"] if author else None
    if not commit:
        authored_problem = "no current tests.authored commit"
    else:
        try:
            resolved = _commit(engine.repo_root, commit)
            if resolved != commit or not author.data["actor"].strip():
                authored_problem = f"invalid test-author commit/identity: {commit}"
            tip = head_view.revision or "HEAD"
            if _origin(engine, commit, tip) != commit:
                authored_problem = f"test-author commit {commit} is not reachable from {tip}"
        except _ExecutionError as exc:
            authored_problem = str(exc)
    author_available = bool(commit) and authored_problem is None
    if not contract.is_lean:
        authored_problem = f"{contract.ib_id}: lean authority policy was relabelled {contract.authority_policy}"
    checks = [_Check("tests-authored", authored_problem is None,
                     f"{contract.ib_id}: {authored_problem or commit}; {detail}")]
    floor_problem = _floor_check(contract, events, author)
    loop = _history(events).floor_loop
    floor_detail = ("ended floor loop: " + "; ".join(f"{f.level} {f.text}" for f in loop.findings)
                    if loop.disposition == "ended" else "current passing floor verdict")
    checks.append(_Check("floor-verdict", floor_problem is None, floor_problem or floor_detail))
    try:
        clashes = _identity_problems(events)
    except (KeyError, TypeError, AttributeError) as exc:
        raise _ExecutionError(f"{contract.ib_id}: unreadable identity history: {exc}") from exc
    checks.append(_Check("identities-distinct", not clashes, ", ".join(clashes) or "separate identities"))
    if not author_available:
        checks.extend(_Check(name, False, authored_problem or "no author commit") for name in (
            "red-at-test-author-commit", "test-files-unchanged", "skeleton-interface-kept"))
        return checks
    try:
        origin, protected = _protected(engine, contract, commit, base, skeletons)
    except _CannotAnswer as exc:
        origin, protected, unanswered = _origin(engine, commit, base), set(), str(exc)
    else:
        unanswered = None
    author_view, base_view, origin_view = _View(engine, commit), _View(engine, base), _View(engine, origin)
    changed = [unanswered] if unanswered else []
    approvals = _approvals(events, author)
    if origin == commit:
        changed.append(f"base contains test-author commit {commit}")
    for path in sorted(protected - approvals):
        current, authored = head_view.read(path), author_view.read(path)
        before, ancestor = base_view.read(path), origin_view.read(path)
        # Completing the brief changes only its lifecycle text, which the
        # delivery already treats as bookkeeping. Its authored contract stays fixed.
        if path == contract.rel_path and current is not None and authored is not None:
            if _normalize_governed(current.decode()) == _normalize_governed(authored.decode()):
                continue
        # Optional conftests absent everywhere are unchanged, but deleting an
        # authored path is excused only by a deletion on the base branch.
        if current == authored and (current is not None or ancestor is None):
            continue
        if current == before and before != ancestor:
            continue
        changed.append(path)
    checks.append(_Check("test-files-unchanged", not changed, "; ".join(changed) or "protected files unchanged or approved"))
    checks.append(_skeleton_check(author_view, head_view, skeletons))
    checks.append(_red_check(engine, contract, author_view, origin_view, settings, base))
    return checks


def guard(engine, *, base: str, head: str, ibs: list[str] | None = None):
    """Read-only DeliveryResult; unavailable judgement refuses."""
    base, head = _commit(engine.repo_root, base), _commit(engine.repo_root, head)
    merge_base = _origin(engine, head, base)
    before, after = _View(engine, merge_base), _View(engine, head)
    changed = _git(engine.repo_root, "diff", "--no-renames", "--name-only", "-z", merge_base, head).decode().split("\0")
    candidates = set()
    for path in changed:
        if path.startswith(".dekspec/execution/"):
            ident = path.split("/")[2]
            if _re.fullmatch(r"IB-\d+", ident):
                candidates.add(ident)
        elif path.startswith(engine.spec_root + "/"):
            match = _re.match(r"(IB-\d+)(?:-|\.)", _PurePath(path).name)
            if match:
                candidates.add(match[1])
    selected = {after.contract(ref).ib_id for ref in ibs or []}
    lean, contracts, histories = set(), {}, {}
    for ib in sorted(candidates | selected):
        old_events, events = before.events(ib), after.events(ib)
        old_hashes = {e.hash for e in old_events}
        if old_events and [e.hash for e in events[:len(old_events)]] != [e.hash for e in old_events]:
            raise _ExecutionError(f"{ib}: head does not extend the merge-base record")
        contract = after.contract(ib)
        try:
            old_contract = before.contract(ib)
        except _ExecutionError:
            old_contract = None
        was_lean = bool(old_contract and old_contract.is_lean) or any(e.type == "tests.authored" for e in events)
        relabelled = was_lean and not contract.is_lean
        delivered = any(e.hash not in old_hashes and e.type in ("tests.authored", "run.started") for e in events)
        delivered |= contract.status == "COMPLETE" and (old_contract is None or old_contract.status != "COMPLETE")
        if delivered or relabelled:
            selected.add(ib)
        contracts[ib], histories[ib] = contract, events
        if (contract.is_lean or was_lean) and ib in selected:
            lean.add(ib)
    result = _DeliveryResult(ibs=sorted(selected))
    if not lean:
        result.checks.append(_Check("lean-briefs", True, "none"))
        return result
    result.checks.append(_Check("lean-single-brief", len(selected) == 1, ", ".join(sorted(selected))))
    settings = _settings_at(engine.repo_root, base, spec_root=engine.spec_root)
    for ib in sorted(lean):
        result.checks.extend(_judge(engine, contracts[ib], histories[ib], after, base, settings))
    return result


def completion_checks(engine, ib: str):
    """Read-only list[Check] for one brief, excluding lean-single-brief."""
    try:
        base = _base_commit(engine)
        view = _View(engine)
        contract = view.contract(ib)
        return _judge(engine, contract, view.events(contract.ib_id), view, base, engine.settings)
    except OSError as exc:
        raise _ExecutionError(str(exc)) from exc


def may_approve(engine, ib: str, path: str) -> bool:
    """Whether path is reviewer-approvable; unavailable query refuses."""
    view = _View(engine)
    contract = view.contract(ib)
    author = _author(view.events(contract.ib_id), contract.ib_id)
    if author is None or not author.data["commit"] or not contract.is_lean:
        return False
    try:
        base = _base_commit(engine)
        commit = _commit(engine.repo_root, author.data["commit"])
        return path in _protected(engine, contract, commit, base, author.data.get("skeletons", []))[1]
    except OSError as exc:
        raise _ExecutionError(str(exc)) from exc
