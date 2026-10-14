"""judge_change(engine, *, base=None, ibs=None) -> DeliveryResult is briefless.py's sole function; it hides kind precedence, path classes, bookkeeping, pin ownership, and review history.
The existing engine and optional base/explicit IB selection suffice; defaults use the engine's base and discovery. The result carries kind, optional intent, and finished checks; kind == 'briefs' tells delivery_check to continue its existing brief judgment over result.ibs.
Kinds are briefs, intent-completion, direct and none (IB-291 O-9); new kinds name themselves and their causes in checks, while briefs/none retain existing checks. Broken rules become failed checks, including ambiguous Intent completions, unauthorized bookkeeping, pinned edits, and missing, invalid, stale or failing reviews.
Callers never supply path classes, verdict keys, commits or merge bases, or reconstruct why a kind won; all observations come from the judged change. No files, records or refs are written, and neither new kind runs integration or requires base currency.
Missing review, stale review and failed review remain distinct named failures; absent optional selection means discovery, empty changes mean none, and bad verdict data becomes a diagnostic rather than an exception. Unreadable base briefs pin nothing and are named in delivery-kind diagnostics. Invalid repository/base errors retain the delivery gate's existing handling.
Alternatives: classify()+review() leaks ordering and policy to delivery_check; a DeliveryJudge object adds state/call order without a lifecycle. One judge_change call returning the existing named result wins for the caller: one request, a complete decision, no policy orchestration.
"""

from __future__ import annotations

import json as _json
import subprocess as _subprocess
from pathlib import Path as _Path

from dekspec.constraint_compiler.parser import IBParseError as _IBParseError, _parse_ib_text
from dekspec.diff_confinement import matches_any_glob as _matches
from dekspec.execution import delivery as _delivery
from dekspec.execution.artifact_edit import _H2_STATUS, _META_STATUS
from dekspec.execution.contract import AcceptanceCondition as _Condition, IBContract as _Contract
from dekspec.execution.engine import (
    Check as _Check, Engine as _Engine, ExecutionError as _ExecutionError,
    integrated_completion as _integrated_completion,
)
from dekspec.execution.fingerprint import is_tracker_record as _is_tracker_record
from dekspec.execution.history import delivery_commits as _delivery_commits
from dekspec.execution.intent_gate import intent_evaluate as _intent_evaluate
from dekspec.execution.lifecycle_bookkeeping import is_protection_bookkeeping as _bookkeeping
from dekspec.execution.ranges import resolve_ranges as _resolve_ranges
from dekspec.execution.record import (
    EXECUTION_DIRNAME as _RECORDS, RecordIntegrityError as _RecordError,
    is_record_file as _is_record_file,
)
from dekspec.execution.scope import (
    ScopeError as _ScopeError, changed_files as _changed_files, resolve_base as _resolve_base,
)

_DOCUMENTS = ("docs/**", "spec/**", "products/*/docs/**", "CHANGELOG.md",
              "products/*/CHANGELOG.md", "README.md", "RELEASING.md", "products/*/README.md")
_VERDICTS = ".dekspec/execution/direct-reviews/*.json"
_VERDICT_KEYS = {"reviewer", "commit", "verdict", "notes"}
_PINNED_STATUSES = {"DRAFT", "PROPOSED", "ACCEPTED"}


def _git(root, *args):
    """Read git objects and report failed reads without writing state."""
    proc = _subprocess.run(["git", *args], cwd=root, capture_output=True)
    if proc.returncode:
        raise _ScopeError(proc.stderr.decode("utf-8", errors="replace").strip())
    return proc.stdout.decode("utf-8", errors="surrogateescape")


def _is_verdict(path):
    return _matches(path, [_VERDICTS])


def _is_code(path, spec_root, pins):
    return path in pins or not (
        path.startswith(spec_root.rstrip("/") + "/") or _is_record_file(path)
        or _is_tracker_record(path) or _is_verdict(path) or _matches(path, _DOCUMENTS))


def _base_assets(engine, base):
    """Read ownership from base objects; unreadable historical briefs grant no pin."""
    pins, complete, unreadable = {}, {}, []
    folder = f"{engine.spec_root}/impl-briefs/"
    paths = _git(engine.repo_root, "ls-tree", "-r", "--name-only", "-z", base, "--", folder)
    for path in filter(None, paths.split("\0")):
        if not (_Path(path).name.startswith("IB-") and path.endswith(".md")):
            continue
        try:
            ir = _parse_ib_text(engine.repo_root / path, _git(engine.repo_root, "show", f"{base}:{path}"))
        except (_IBParseError, UnicodeError, ValueError) as exc:
            unreadable.append(f"{path}: unreadable at the base ({exc})")
            continue
        # A snapshot view uses the contract's one acceptance-asset definition.
        contract = _Contract(
            ib_id=ir["id"], path=engine.repo_root / path, rel_path=path, name=ir["name"],
            status=ir["status"], authority_policy=ir.get("authority_policy", "legacy"),
            parent=None, depends_on=(), spec_impact=(), scope=(), out_of_scope=(),
            obligations=(), protected=(), hypothesis=(), prerequisites=(), parse_warnings=(),
            acceptance=tuple(_Condition.from_ir(a) for a in ir.get("acceptance", [])),
            declared_assets=tuple(ir.get("acceptance_assets", [])), ir=ir)
        if contract.status == "COMPLETE":
            owners = complete
        elif contract.is_delegated and contract.status in _PINNED_STATUSES:
            owners = pins
        else:
            continue
        for asset in contract.acceptance_asset_paths():
            owners.setdefault(asset, []).append(contract.ib_id)
    return pins, complete, unreadable


def _status(text):
    match = _META_STATUS.search(text) or _H2_STATUS.search(text)
    return match.group(2).strip("`*_ ").upper() if match else None


def _intent_completions(engine, changes, base):
    completions = {}
    for change in changes:
        path = change.path
        if not (path.startswith(f"{engine.spec_root}/intents/")
                and _Path(path).name.startswith("INT-") and path.endswith(".md")):
            continue
        try:
            after = (engine.repo_root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        try:
            before = _git(engine.repo_root, "show", f"{base}:{change.old_path or path}")
        except _ScopeError:
            before = ""
        if _status(after) == "COMPLETE" and _status(before) != "COMPLETE":
            ident = "-".join(_Path(path).stem.split("-")[:2])
            completions[ident] = path
    return completions


def _judge_intent(engine, result, completions, changes, base):
    result.kind = "intent-completion"
    if len(completions) != 1:
        result.checks.append(_Check("delivery-kind", False,
                                    "intent-completion: multiple Intents became COMPLETE: "
                                    + ", ".join(sorted(completions))))
        return
    ident, path = next(iter(completions.items()))
    result.intent = ident
    result.checks.append(_Check("delivery-kind", True, f"intent-completion: {ident}"))
    outside = [ch.path for ch in changes if not (
        (ch.path == path or ch.path.startswith(f"{_RECORDS}/{ident}/"))
        and _bookkeeping(engine.repo_root, ch, {path}, base))]
    result.checks.append(_Check(f"{ident}:bookkeeping-only", not outside,
                                "only the Intent's lifecycle bookkeeping" if not outside else
                                "not the Intent's bookkeeping: " + ", ".join(outside)))
    try:
        completion = engine.current_completion(ident)
        gate = _intent_evaluate(engine, str(engine.repo_root / path))
        problems = [ch.detail for ch in gate.checks if not ch.ok]
        if completion is None:
            problems.insert(0, "missing current completion record")
        elif completion.get("fingerprint") != gate.fingerprint:
            problems.insert(0, "completion record is not current at the judged content")
    except (_ExecutionError, _RecordError, ValueError, OSError) as exc:
        problems = [str(exc)]
    result.checks.append(_Check(f"{ident}:completion-gate", not problems,
                                "; ".join(problems) or "current completion record and passing Intent gate"))


def _content(engine, commit, base, pins):
    """BR 62: changed paths and object identities, against this commit's merge base.

    Include both sides of renames and deletion markers. Comparing snapshots,
    rather than the intervening commits, admits restored content and detects
    content changed by a merge.
    """
    merge_base = _git(engine.repo_root, "merge-base", commit, base).strip()
    raw = _git(engine.repo_root, "diff", "--raw", "--no-abbrev", "--no-renames", "-z",
               merge_base, commit, "--").split("\0")
    content = {}
    for header, path in zip(raw[0::2], raw[1::2]):
        if (not path.startswith(engine.spec_root.rstrip("/") + "/")
                and not _is_record_file(path) and not _is_tracker_record(path) and not _is_verdict(path)
                and _is_code(path, engine.spec_root, pins)
                and not _matches(path, engine.settings.fingerprint_exclude)):
            fields = header.split()
            content[path] = (fields[1], fields[3])  # new mode and blob; zeroes represent deletion
    return content


def _review_check(engine, base, pins):
    """Validate every added verdict and its history before selecting current verdicts."""
    name = "direct:independent-review"
    root = engine.repo_root
    commits = _delivery_commits(root, base)
    identities, verdict_commits, additions, mutations = {}, set(), {}, set()
    for commit in commits:
        fields = _git(root, "show", "-s", "--format=%P%x00%an%x00%ae%x00%cn%x00%ce", commit).rstrip("\n").split("\0")
        parents = fields[0].split()
        identities[commit] = ((fields[1], fields[2]), (fields[3], fields[4]))
        differences = [_changed_files(root, parent, commit) for parent in parents]
        if len(parents) == 1 and differences[0] and all(
                _is_verdict(p) for ch in differences[0] for p in (ch.path, ch.old_path) if p):
            verdict_commits.add(commit)
        # A merge imports files from its parents; only files absent from every
        # parent are introduced by the merge itself (and cannot be valid verdicts).
        introduced = set.intersection(*[
            {ch.path for ch in diff if ch.status == "A" and _is_verdict(ch.path)}
            for diff in differences]) if differences else set()
        for path in introduced:
            additions.setdefault(path, []).append(commit)
        for diff in differences:
            for ch in diff:
                if ch.status != "A":
                    for path in (ch.path, ch.old_path):
                        if path and _is_verdict(path):
                            mutations.add((path, ch.status))
    for ch in _changed_files(root, base, "HEAD"):
        if ch.status != "A":
            for path in (ch.path, ch.old_path):
                if path and _is_verdict(path):
                    mutations.add((path, ch.status))

    change_identities = [identity for commit, pair in identities.items()
                         if commit not in verdict_commits for identity in pair]
    verdicts = []
    for path, authors in sorted(additions.items()):
        commit = authors[0]
        try:
            body = _json.loads(_git(root, "show", f"{commit}:{path}"))
        except (ValueError, _ScopeError) as exc:
            return _Check(name, False, f"{path}: invalid JSON: {exc}")
        problem = None
        if not isinstance(body, dict) or set(body) != _VERDICT_KEYS:
            problem = "must have exactly the reviewer, commit, verdict and notes keys"
        elif not all(isinstance(body[k], str) for k in _VERDICT_KEYS):
            problem = "reviewer, commit, verdict and notes fields must be strings"
        elif body["verdict"] not in ("pass", "fail"):
            problem = "verdict must be pass or fail"
        elif commit not in verdict_commits:
            problem = "must be added by a non-merge verdict commit changing only verdict files"
        elif body["reviewer"] != identities[commit][0][0]:
            problem = "reviewer does not match the verdict commit's author name"
        elif any(n == other_n or e == other_e for n, e in identities[commit]
                 for other_n, other_e in change_identities):
            problem = "not independent: author or committer shares a name or email with a change author or committer"
        elif body["commit"] not in commits:
            problem = "full reviewed commit is not a commit of the change"
        if problem:
            return _Check(name, False, f"{path}: {problem}")
        verdicts.append(body)
    if mutations:
        labels = {"D": "deleted or removed", "R": "renamed", "M": "edited or modified"}
        return _Check(name, False, "; ".join(
            f"{path}: verdict file {labels.get(status, 'edited')}" for path, status in sorted(mutations)))
    if not verdicts:
        return _Check(name, False, "no review on record")
    head = _content(engine, "HEAD", base, pins)
    current, moved = [], set()
    for verdict in verdicts:
        reviewed = _content(engine, verdict["commit"], base, pins)
        changed = {p for p in head.keys() | reviewed.keys() if head.get(p) != reviewed.get(p)}
        if changed:
            moved.update(changed)
        else:
            current.append(verdict)
    if not current:
        return _Check(name, False, "stale review; moved paths: " + ", ".join(sorted(moved)))
    failed = [v for v in current if v["verdict"] == "fail"]
    if failed:
        return _Check(name, False, "; ".join(f"fail: {v['reviewer']}: {v['notes']}" for v in failed))
    return _Check(name, True, "; ".join(f"pass: {v['reviewer']} reviewed {v['commit']}" for v in current))


def judge_change(engine: _Engine, *, base: str | None = None,
                 ibs: list[str] | None = None) -> _delivery.DeliveryResult:
    """Return the kind and finished common/briefless checks; never execute or write."""
    base = base or engine.base
    result = _delivery.DeliveryResult(ibs=[])
    try:
        base_commit = _resolve_base(engine.repo_root, base)
        discovered = engine.delivery_ibs(base)
        anomalies = engine.delivery_anomalies(base)
    except _ScopeError as exc:
        result.checks.append(_Check("base-resolvable", False, str(exc)))
        return result
    try:
        selected = [engine.contract(ib).ib_id for ib in ibs] if ibs else []
    except _ExecutionError as exc:
        result.checks.append(_Check("ib-selection", False, str(exc)))
        return result
    result.ibs = sorted(set(selected) | set(discovered))
    try:
        attribution = _resolve_ranges(engine, base)
    except _ScopeError as exc:
        result.checks.append(_Check("delivery-ranges", False, str(exc)))
        return result
    result.ranges = attribution.ranges
    if attribution.ranges or attribution.problems:
        result.checks.append(_Check("delivery-ranges", not attribution.problems,
                                    "; ".join(attribution.problems) or "constituent ranges account for the candidate"))
    result.checks.append(_Check("ib-file-integrity", not anomalies, "; ".join(anomalies) or "no refused IB-file changes"))
    result.checks.extend(_delivery._record_history_checks(engine, base_commit))
    omitted = sorted(set(discovered) - set(selected)) if selected else []
    if omitted:
        result.checks.append(_Check("delivery-coverage", False,
                                    f"the selection omits delivered IB(s) {', '.join(omitted)}; they were evaluated "
                                    "anyway, and a partial selection never lands"))
    carried = [ib for ib in discovered if _integrated_completion(engine.repo_root, ib, base_commit) is None]
    if selected or carried:
        result.kind = "briefs"
        return result
    changes = _changed_files(engine.repo_root, base_commit)
    completions = _intent_completions(engine, changes, base_commit)
    if completions:
        result.ibs = []
        # intent_evaluate takes its base from the engine, including for child
        # completions. Preserve an explicit selection made by this caller.
        intent_engine = _Engine(engine.repo_root, spec_root=engine.spec_root,
                                settings=engine.settings, base=base)
        _judge_intent(intent_engine, result, completions, changes, base_commit)
        return result
    if discovered:
        result.kind = "briefs"
        return result
    pins, complete, unreadable = _base_assets(engine, base_commit)
    paths = {p for ch in changes for p in (ch.path, ch.old_path) if p}
    if not any(_is_code(p, engine.spec_root, pins) for p in paths):
        result.checks.append(_Check("governed-ibs", True, "this change delivers no delegated IB"))
        return result
    result.kind = "direct"
    detail = ["direct"] + [f"COMPLETE acceptance file: {p} ({', '.join(complete[p])})"
                            for p in sorted(paths & complete.keys())] + unreadable
    result.checks.append(_Check("delivery-kind", True, "; ".join(detail)))
    pinned = [f"{p} ({', '.join(pins[p])})" for p in sorted(paths & pins.keys())]
    result.checks.append(_Check("direct:pinned-tests-untouched", not pinned,
                                "pinned acceptance files changed: " + ", ".join(pinned) if pinned else
                                "no acceptance files pinned by unfinished delegated briefs changed"))
    try:
        result.checks.append(_review_check(engine, base_commit, pins))
    except (_ScopeError, UnicodeError, OSError) as exc:
        result.checks.append(_Check("direct:independent-review", False, f"cannot read review history: {exc}"))
    return result
