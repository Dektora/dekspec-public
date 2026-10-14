"""guard(engine, *, base: str, head: str, ibs: list[str] | None = None) -> DeliveryResult judges committed head against base, unions added ibs with delivered briefs, and returns seven BR 29 checks naming faulty nodes/kinds, paths/names or identities; CLI prints them and maps ok to 0/1.
completion_checks(engine, ib: str) -> list[Check] gives the same judgement for working content without lean-single-brief; may_approve(engine, ib: str, path: str) -> bool answers protected membership, False for skeletons/outside paths, not reviewer eligibility (Engine.review owns that refusal).
These read-only queries hide current-author/floor selection, protected sets, red execution, name comparison and git cleanup: callers need no history, sequencing or cleanup; returns invalidate earlier floors/approvals, while identity separation reads all history.
Ordinary record/test/name/identity failures are checks; an unknown commit raises ExecutionError naming it, and unreadable history refuses. No lean delivery succeeds as lean-briefs: none; no skeleton succeeds as skeletons: none, and non-Python skeletons are unchecked: no caller recovery is needed.
Files, refs, worktrees and events stay unchanged; existing DeliveryResult/Check fields suffice, with no new public names, parameters, exceptions or return fields.
Alternatives: separate checks leak sequencing/cleanup; a stateful judge adds lifecycle work; the three queries keep both gates consistent and review membership independent, so are easiest for callers.
"""

from __future__ import annotations

import ast as _ast
import io as _io
import re as _re
import subprocess as _subprocess
import tarfile as _tarfile
from pathlib import Path as _Path, PurePosixPath as _PurePath
from tempfile import TemporaryDirectory as _TemporaryDirectory

from dekspec.execution import acceptance as _acceptance, floor as _floor
from dekspec.execution.contract import load_contract as _load_contract, ContractError as _ContractError
from dekspec.execution.delivery import DeliveryResult as _DeliveryResult
from dekspec.execution.engine import (
    Check as _Check, ExecutionError as _ExecutionError, verdict_policy_problem as _policy_problem,
)
from dekspec.execution.lean_records import _DESIGN_CRITERIA
from dekspec.execution.record import ExecutionRecord as _Record, RecordIntegrityError as _RecordError, is_record_file as _is_record
from dekspec.execution.settings import load_settings_at as _settings_at, resolve_python as _resolve_python
from dekspec.execution.state import fold as _fold

__all__ = ["guard", "completion_checks", "may_approve"]


def _git(root, *args):
    result = _subprocess.run(["git", *args], cwd=root, capture_output=True)
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


def _protected(engine, author, base, skeletons):
    origin = _origin(engine, author, base)
    paths = set(_git(engine.repo_root, "diff", "--no-renames", "--name-only", "-z",
                     origin, author).decode().strip("\0").split("\0")) - {""}
    paths = {p for p in paths if not _is_record(p)} - set(skeletons)
    for path in tuple(paths):
        for directory in _PurePath(path).parents:
            paths.add(str(directory / "conftest.py"))
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
    if data.get("verdict") != "pass":
        return f"floor verdict {data.get('verdict')}: {data.get('reviewer')}"
    criteria = data.get("criteria")
    required = {c.id for c in contract.acceptance if c.kind == "pytest"} | {"tests-through-interface"}
    if author.data.get("skeletons"):
        required |= _DESIGN_CRITERIA
    allowed = {c.id for c in contract.acceptance} | _DESIGN_CRITERIA
    if not isinstance(criteria, list) or any(not isinstance(c, str) for c in criteria):
        return "floor verdict has malformed criteria"
    if required - set(criteria) or set(criteria) - allowed:
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


def _names(source):
    tree = _ast.parse(source)

    def declared(body):
        names = set()
        for node in body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (_ast.Assign, _ast.AnnAssign)):
                targets = node.targets if isinstance(node, _ast.Assign) else [node.target]
                for target in targets:
                    names.update(n.id for n in _ast.walk(target) if isinstance(n, _ast.Name))
        return {n for n in names if not n.startswith("_")}

    names = declared(tree.body)
    for node in tree.body:
        if isinstance(node, (_ast.Assign, _ast.AnnAssign)):
            targets = node.targets if isinstance(node, _ast.Assign) else [node.target]
            if any(isinstance(t, _ast.Name) and t.id == "__all__" for t in targets):
                try:
                    exports = _ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(exports, (list, tuple)) and all(isinstance(n, str) for n in exports):
                    names = set(exports)
    for node in tree.body:
        if isinstance(node, _ast.ClassDef) and node.name in names:
            names |= {node.name + "." + n for n in declared(node.body)}
    return names


def _skeleton_check(author_view, head_view, skeletons):
    problems, unchecked = [], []
    for path in skeletons:
        if not path.endswith(".py"):
            unchecked.append(path + ": unchecked")
            continue
        try:
            before = _names(author_view.read(path) or b"")
            source = head_view.read(path)
            after = _names(source) if source is not None else set()
            if before != after or source is None:
                problems.append(f"{path}: added {', '.join(sorted(after - before)) or 'none'}; "
                                f"removed {', '.join(sorted(before - after)) or 'none'}"
                                + ("; missing" if source is None else ""))
        except (SyntaxError, ValueError, TypeError) as exc:
            problems.append(f"{path}: cannot parse skeleton: {exc}")
    return _Check("skeleton-interface-kept", not problems,
                  "; ".join(problems + unchecked) or "skeletons: " + (", ".join(skeletons) or "none"))


def _marked_xfail(source, names):
    """A disabled xfail marker is still forbidden on an acceptance node."""
    try:
        body = _ast.parse(source).body
    except (SyntaxError, ValueError):
        return False
    markers = []
    for name in [*names, None]:
        for node in body:
            if isinstance(node, (_ast.Assign, _ast.AnnAssign)):
                targets = node.targets if isinstance(node, _ast.Assign) else [node.target]
                if any(isinstance(t, _ast.Name) and t.id == "pytestmark" for t in targets):
                    markers.append(node.value)
        selected = next((n for n in body if isinstance(
            n, (_ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)) and n.name == name), None)
        if selected is None:
            break
        markers.extend(selected.decorator_list)
        body = selected.body if isinstance(selected, _ast.ClassDef) else []
    return any(isinstance(n, _ast.Attribute) and n.attr == "xfail"
               for marker in markers if marker is not None for n in _ast.walk(marker))


def _red_check(engine, contract, author_view, base_view, settings):
    problems = []
    author = author_view.revision
    python = _resolve_python(engine.repo_root, settings.python)
    if not _Path(python).is_absolute() and "/" in python:
        python = str(engine.repo_root / python)
    with _TemporaryDirectory(prefix="dekspec-lean-red-") as temp:
        root = _Path(temp)
        with _tarfile.open(fileobj=_io.BytesIO(_git(engine.repo_root, "archive", author))) as archive:
            archive.extractall(root, filter="data")
        for condition in contract.acceptance:
            if condition.kind != "pytest":
                continue
            try:
                run = _acceptance.run_pytest_detail(root, condition, python=python, timeout=settings.command_timeout)
            except OSError as exc:
                problems.extend(f"{node}: interpreter {python}: {exc}" for node in condition.nodes)
                continue
            report = run.get("report")
            if report is None:
                problems.extend(f"{node}: {run.get('detail', 'no pytest report')}" for node in condition.nodes)
                continue
            results = report["results"]
            for requested in condition.nodes:
                matched = [n for n in results if _acceptance._node_matches(requested, n)]
                dropped = [n for n in report["deselected"] if _acceptance._node_matches(requested, n)]
                problems.extend(f"{node}: deselected" for node in dropped)
                if not matched and not dropped:
                    kind = "collection-error (import/collection)" if report["collect_errors"] else "not-collected"
                    problems.append(f"{requested}: {kind}")
                for node in matched:
                    kind = _floor.failure_kind(results[node], report["failures"].get(node, {}),
                                               report["captured"].get(node, ""))
                    path, names = _floor.node_path(node)
                    source = (author_view.read(path) or b"").decode()
                    if _marked_xfail(source, names):
                        kind = "xfail"
                    old = (base_view.read(path) or b"").decode()
                    span = _floor.function_span(source, names)
                    preserved = span is not None and span == _floor.function_span(old, names)
                    expected = "passed" if preserved else _floor.GENUINE
                    if kind != expected:
                        problems.append(f"{node}: {kind} (expected {expected})")
                    if not preserved:
                        basis = _floor.declared_bases(source, names)
                        if not isinstance(basis, list) or not basis:
                            problems.append(f"{node}: missing basis")
            if report["collect_errors"]:
                problems.append(f"{condition.id}: collection-error (import/collection)")
            if run.get("exit_code") not in (0, 1):
                problems.append(f"{condition.id}: pytest exit {run.get('exit_code')}")
    return _Check("red-at-test-author-commit", not problems, "; ".join(problems) or "all nodes meet red/preservation rules")


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
    checks.append(_Check("floor-verdict", floor_problem is None, floor_problem or "current passing floor verdict"))
    try:
        clashes = _identity_problems(events)
    except (KeyError, TypeError, AttributeError) as exc:
        raise _ExecutionError(f"{contract.ib_id}: unreadable identity history: {exc}") from exc
    checks.append(_Check("identities-distinct", not clashes, ", ".join(clashes) or "separate identities"))
    if not author_available:
        checks.extend(_Check(name, False, authored_problem or "no author commit") for name in (
            "red-at-test-author-commit", "test-files-unchanged", "skeleton-interface-kept"))
        return checks
    origin, protected = _protected(engine, commit, base, skeletons)
    author_view, base_view, origin_view = _View(engine, commit), _View(engine, base), _View(engine, origin)
    changed = []
    approvals = _approvals(events, author)
    if origin == commit:
        changed.append(f"base contains test-author commit {commit}")
    for path in sorted(protected - approvals):
        current, authored = head_view.read(path), author_view.read(path)
        before, ancestor = base_view.read(path), origin_view.read(path)
        # Optional conftests absent everywhere are unchanged, but deleting an
        # authored path is excused only by a deletion on the base branch.
        if current == authored and (current is not None or ancestor is None):
            continue
        if current == before and before != ancestor:
            continue
        changed.append(path)
    checks.append(_Check("test-files-unchanged", not changed, "; ".join(changed) or "protected files unchanged or approved"))
    checks.append(_skeleton_check(author_view, head_view, skeletons))
    checks.append(_red_check(engine, contract, author_view, origin_view, settings))
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
        return path in _protected(engine, commit, base, author.data.get("skeletons", []))[1]
    except OSError as exc:
        raise _ExecutionError(str(exc)) from exc
