"""The READY predicate (ADR-059): can this work be implemented without an
unresolved substantive decision?

Readiness is evaluated over the approved graph and its evidence, never over a
status word alone. The same predicate answers at the end of specification
(`spec-intent`) and at `/implement` entry. A target that is not ready gets the
specific missing preparation and how to supply it; a COMPLETE target is an
idempotent verification result, not work — but only when its completion has
provenance: a completion record (`dekspec intent complete`) over complete
IBs, or a historical completion that predates the execution engine. A status
word edited by hand is not evidence.

Readiness is an entry check only: the driver never re-uses it to stop a run
that has already started.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dekspec.constraint_compiler.parser import IntentParseError, parse_intent
from dekspec.execution.contract import IBContract
from dekspec.execution.engine import RETIRED_STATUSES, Engine, ExecutionError, IntegrationUnknown, probe_blocker
from dekspec.execution.intent_gate import intent_children, unintegrated_intent_completion_problem
from dekspec.execution.references import APPROVED_STATUSES, AmbiguousReference, artifact_path, artifact_status
from dekspec.execution.references import resolve_obligations
from dekspec.execution.history import LEGACY_TERMINAL_STATUSES, file_versions
from dekspec.execution.scope import ScopeError, resolve_base
from dekspec.execution.settings import _has_pytest, resolve_python
from dekspec.implement.config import IntegrationSettings, load_integration
from dekspec.implement.targets import Target

__all__ = ["AUTONOMOUS_LEVELS", "Missing", "Readiness", "TargetReadiness", "assess", "authoritative_base", "intent_completion"]

#: Intent autonomy levels that permit an autonomous run after acceptance
#: (intent template: `medium` — engineer approves at ACCEPTED only; `high` — full).
AUTONOMOUS_LEVELS = ("medium", "high")
_AUTONOMY_RANK = {"manual": 0, "low": 1, "medium": 2, "high": 3}
_BLOCKING_SEVERITIES = ("P0", "P1", "P2")
_DRIVER_RECOVERABLE = ("attempts-exhausted", "no-progress", "stalled")


@dataclass
class Missing:
    target: str
    code: str
    detail: str
    fix: str

    def as_dict(self) -> dict[str, str]:
        return {"target": self.target, "code": self.code, "detail": self.detail, "fix": self.fix}


@dataclass
class TargetReadiness:
    id: str
    kind: str
    status: str
    outcome: str  # "ready" | "not-ready" | "complete"
    ibs: list[str] = field(default_factory=list)
    missing: list[Missing] = field(default_factory=list)
    completion: str | None = None  # provenance of a complete target: "verified" | "historical"

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "status": self.status, "outcome": self.outcome,
                "ibs": self.ibs, "missing": [m.as_dict() for m in self.missing], "completion": self.completion}


@dataclass
class Readiness:
    targets: list[TargetReadiness] = field(default_factory=list)
    order: list[str] = field(default_factory=list)
    groups: list[list[str]] = field(default_factory=list)
    base: str | None = None
    integration: dict[str, Any] = field(default_factory=dict)
    missing: list[Missing] = field(default_factory=list)  # environment / package level

    @property
    def ready(self) -> bool:
        return (not self.missing and bool(self.targets)
                and all(t.outcome in ("ready", "complete") for t in self.targets)
                and any(t.outcome == "ready" for t in self.targets))

    @property
    def all_missing(self) -> list[Missing]:
        return [m for t in self.targets for m in t.missing] + self.missing

    def as_dict(self) -> dict[str, Any]:
        return {"ready": self.ready, "targets": [t.as_dict() for t in self.targets], "order": self.order,
                "groups": self.groups, "base": self.base, "integration": self.integration,
                "missing": [m.as_dict() for m in self.all_missing]}


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True)


def _spec_status(repo_root: Path, ref: str, spec_root: str) -> str | None:
    try:
        path = artifact_path(repo_root, ref, spec_root=spec_root)
    except AmbiguousReference:
        return "AMBIGUOUS"
    return artifact_status(path.read_text(encoding="utf-8")) if path else None


def _stale_completion(ident: str, problem: str, *, ib: bool) -> Missing:
    """A completion recorded on this branch, not yet integrated, that no longer
    holds (ADR-061): its review failed, or its review or attestation does not meet
    the current policy or content. Not complete, and nothing is rebuilt merely for
    a policy change — the named review or repair is what is missing."""
    if ib:
        fix = (f"if a review failed, repair {ident} within Scope and have it reviewed again; otherwise record a "
               f"fresh independent review under the current code-reviewer policy (`/dekspec:review-pr`, i.e. "
               f"`dekspec ib review {ident} --reviewer <you> --actor <you> --verdict pass|fail --policy-revision "
               f"<N>`), then `dekspec ib complete {ident}`. If the review policy cannot be loaded, reinstall "
               "DekSpec. A policy change alone never needs a rebuild.")
    else:
        fix = (f"resolve what it names: repair a failed attestation's finding, or record a fresh, passing, "
               f"independent attestation for the current content under the current policy (`dekspec intent review "
               f"{ident} --reviewer <you> --actor <you> --verdict pass|fail --policy-revision <N>`; `dekspec ib "
               f"review` for an IB), then `dekspec intent complete {ident}`. If the policy cannot be loaded, "
               "reinstall DekSpec. A policy change alone never needs a rebuild.")
    return Missing(ident, "completion-not-current",
                   f"{ident} is COMPLETE but not integrated, and its completion does not hold: {problem}", fix)


def _completion_gap(engine: Engine, ident: str, check: Callable[[], str | None], *, ib: bool) -> Missing | None:
    """What keeps a recorded completion from counting, or None (ADR-061). A completion
    the base holds is history; any other must meet the current rules. When the base
    does not resolve, one that fails them may or may not be history: it is not
    complete, nothing may reopen it, and the missing base is what to fix first."""
    try:
        problem = check()
    except IntegrationUnknown as exc:
        return _unknown_base(engine, ident, exc.why, f"its completion does not meet the current rules ({exc.problem})",
                             "it must meet the current rules: " + _stale_completion(ident, exc.problem, ib=ib).fix)
    return _stale_completion(ident, problem, ib=ib) if problem else None


def _unknown_base(engine: Engine, ident: str, why: str, claim: str, otherwise: str) -> Missing:
    """A COMPLETE target whose standing depends on history the authoritative base
    would show, while that base does not resolve here: not complete, not reopenable,
    and the base is what to fix first (ADR-061)."""
    base = _shown(engine.base or "main")
    return Missing(ident, "no-integration-base",
                   f"{ident} is COMPLETE, but {claim}, and whether it is integrated history cannot be told: {why}. "
                   "Until the base resolves it counts neither as complete nor as reopenable",
                   f"fetch the integration base `{base}` into this checkout, or correct `integration.base` in "
                   "`.dekspec/config.yaml` (a stacked or release branch must exist here), then re-run: an "
                   f"integrated completion is history and stands. If it is not integrated, {otherwise}")


def _base_problem(engine: Engine) -> str | None:
    """Why the authoritative base does not resolve here, or None."""
    try:
        resolve_base(engine.repo_root, engine.base)
    except ScopeError as exc:
        return str(exc)
    return None


def _blocking_issues(issues: Any) -> list[str]:
    return [i.get("text", "")[:160] for i in (issues or []) if i.get("severity") in _BLOCKING_SEVERITIES]


def _check_ib(engine: Engine, c: IBContract, tr: TargetReadiness, selected: set[str]) -> None:
    add = lambda code, detail, fix: tr.missing.append(Missing(c.ib_id, code, detail, fix))  # noqa: E731
    if not c.is_delegated:
        why = _base_problem(engine) if c.status == "COMPLETE" else None
        if why:  # complete only by history that the base would show
            tr.missing.append(_unknown_base(
                engine, c.ib_id, why, "it is complete only by its history (legacy authority policy)",
                f"it keeps the legacy authority policy: rewrite it with `/write-ibs --adopt`, then `dekspec ib adopt "
                f"{c.ib_id}`"))
            return
        add("ib-legacy", f"{c.ib_id} keeps the legacy authority policy",
            f"rewrite it with `/write-ibs --adopt`, then `dekspec ib adopt {c.ib_id}`")
        return
    if c.status == "COMPLETE":
        if not engine.is_complete(c.ib_id):
            add("ib-complete-without-record", f"{c.ib_id} is COMPLETE without a completion record",
                "restore the status the completion gate recorded; only `dekspec ib complete` writes COMPLETE")
        else:
            gap = _completion_gap(engine, c.ib_id, lambda: engine.unintegrated_completion_problem(c.ib_id), ib=True)
            if gap:
                tr.missing.append(gap)
        return
    if c.status != "ACCEPTED":
        add("ib-not-authorized", f"{c.ib_id} is {c.status}",
            f"`dekspec ib lint {c.ib_id}`, `dekspec ib propose {c.ib_id}`, then `dekspec ib accept {c.ib_id}`")
        return
    for problem in c.contract_problems():
        add("ib-contract-incomplete", f"{c.ib_id}: {problem}", f"complete the IB with `/write-ibs` ({c.rel_path})")
    for ob in resolve_obligations(engine.repo_root, c, spec_root=engine.spec_root):
        if ob.problem:
            add("obligation-unresolved", f"{c.ib_id} {ob.id}: {ob.problem}",
                "approve the referenced source or point the obligation at its in-force successor")
    try:
        _rec, _events, st = engine.state(c.ib_id)
    except ExecutionError as exc:
        add("record-unreadable", f"{c.ib_id}: {exc}", "restore the execution record from git history")
        return
    if st.baseline is None:
        add("ib-not-authorized", f"{c.ib_id} is ACCEPTED but has no acceptance baseline",
            f"authorize it with `dekspec ib accept {c.ib_id}`")
    elif st.baseline.get("contract_hash") != c.contract_hash():
        add("ib-changed-since-authorization",
            f"{c.ib_id}'s contract changed after it was authorized",
            f"re-authorize the current contract (`dekspec ib baseline {c.ib_id}` before execution, "
            f"`dekspec ib amend {c.ib_id}` by an independent reviewer after)")
    elif not st.started:
        _check_floor(c, st.baseline, add, engine.repo_root)
    for text in _blocking_issues(c.ir.get("open_issues")):
        add("blocking-open-issue", f"{c.ib_id} has an unresolved blocking Open Issue: {text}",
            "resolve it in the IB (check it off with the resolution) or lower its severity with a reason")
    for blocker in st.blockers:
        # A failed probe's own blocker is re-probed by the driver; a worker's escalation
        # (whatever reason it names) needs a recorded decision (ADR-061).
        if blocker.get("reason") not in _DRIVER_RECOVERABLE and not probe_blocker(blocker):
            add("ib-blocked", f"{c.ib_id} is blocked ({blocker.get('reason')}): {blocker.get('detail', '')}",
                "record the decision it needs (amend the contract, or `dekspec ib unblock`)")
    for dep in c.depends_on:
        if dep in selected:
            continue
        try:
            done = engine.is_complete(dep)
        except ExecutionError:
            done = False
        if not done:
            add("dependency-not-selected", f"{c.ib_id} depends on {dep}, which is not COMPLETE",
                f"include {dep}'s Intent in the request, or complete {dep} first")


_FLOOR_DIGEST = re.compile(r"\bdigest ([0-9a-f]{64})(?![0-9a-f])")
_FLOOR_ROW = "Floor reviewed:"
_FLOOR_PASS = "Floor reviewed: PASS"


def floor_reviews(text: str) -> set[str]:
    """Baseline digests named by the IB's recorded *passing* floor reviews:
    Amendment Log rows whose Change text starts `Floor reviewed: PASS` and
    contains `digest <64 hex>` (ADR-062, IB-143 O-4; read from the file — the
    IB IR carries no Amendment Log). Any other `Floor reviewed:` row, such as
    `Floor reviewed: FAIL …`, records no passing review and does not count."""
    return {d for change, digests in _floor_rows(text) if change.startswith(_FLOOR_PASS) for d in digests}


def _floor_rows(text: str) -> list[tuple[str, set[str]]]:
    """Every `Floor reviewed:` Amendment Log row: its Change text and the digests it names."""
    m = re.search(r"^## Amendment Log\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return []
    rows: list[tuple[str, set[str]]] = []
    change_col: int | None = None
    for line in m.group(1).splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line[1:-1])]
        if change_col is None:
            lowered = [cell.lower() for cell in cells]
            change_col = lowered.index("change") if "change" in lowered else 2
            continue
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell) or change_col >= len(cells):
            continue
        change = cells[change_col]
        if change.startswith(_FLOOR_ROW):
            rows.append((change, {hit.group(1) for hit in _FLOOR_DIGEST.finditer(change)}))
    return rows


def _hash_matches(path: Path, recorded: str | None) -> bool:
    """The file exists and hashes to the value the baseline recorded for it."""
    return bool(recorded) and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == recorded


def _baselined(rel: str, assets: dict[str, Any]) -> bool:
    """Does the baseline record a hash for ``rel`` (a file, or any file under a directory)?"""
    return bool(assets.get(rel)) or any(v for k, v in assets.items() if k.startswith(rel.rstrip("/") + "/"))


def _check_floor(c: IBContract, baseline: dict[str, Any], add: Any, root: Path) -> None:
    """ADR-062 entry checks for a run not yet started: every named node and
    declared asset is in the baseline, and a recorded floor review names the
    baseline's digest. Protected acceptance tests are never first written by
    the builder during an `/implement` run."""
    from dekspec.execution.acceptance import baseline_digest
    from dekspec.execution.floor import function_span, node_path

    nodes = [n for a in c.acceptance for n in a.nodes]
    if not nodes and not c.declared_assets:
        return
    assets = baseline.get("assets") or {}
    absent: list[str] = []
    for node in nodes:
        rel, names = node_path(node)
        path = root / rel
        if path.is_dir():
            # A directory node: the baseline holds each file under it (acceptance.asset_hashes).
            files = [p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
            if not files or not all(_hash_matches(p, assets.get(p.relative_to(root).as_posix()))
                                    for p in files):
                absent.append(node)
            continue
        if not _hash_matches(path, assets.get(rel)):
            absent.append(node)
            continue
        if names and function_span(path.read_text(encoding="utf-8", errors="replace"), names) is None:
            absent.append(node)
    absent += [a for a in c.declared_assets if not _baselined(a, assets)]
    if absent:
        add("acceptance-tests-missing",
            f"{c.ib_id}'s acceptance baseline does not hold " + ", ".join(absent[:6])
            + (" …" if len(absent) > 6 else "") + " — protected acceptance tests are written and baselined "
            "before the run, never first created by its builder",
            f"write them with `/dekspec:write-tests`, have them oracle-reviewed, then "
            f"`dekspec ib baseline {c.ib_id} --reason …`")
    digest = baseline_digest(baseline)
    text = c.path.read_text(encoding="utf-8")
    if digest not in floor_reviews(text):
        # IB-143 O-4: only a passing review counts, and the detail says so.
        other = any(digest in digests for _change, digests in _floor_rows(text))
        add("acceptance-floor-unreviewed",
            f"a passing floor review is required: no Amendment Log row in {c.rel_path} starting "
            f"`{_FLOOR_PASS}` names {c.ib_id}'s current baseline digest {digest}"
            + (" (a `Floor reviewed:` row names it but does not record a passing review)" if other else ""),
            f"run the independent oracle review of the floor (`dekspec ib floor {c.ib_id}`, `/review-ib`) and, "
            "on a pass, record it as an Amendment Log row `Floor reviewed: PASS — digest <baseline digest> — …`")


def _check_intent(engine: Engine, target: Target, tr: TargetReadiness, spec_root: str) -> list[IBContract]:
    add = lambda code, detail, fix: tr.missing.append(Missing(target.id, code, detail, fix))  # noqa: E731
    if target.provisional:
        add("intent-provisional", f"{target.path} is a provisional draft",
            f"specify it: `/spec-intent {target.path}` (analyze, accept, decompose, authorize)")
        return []
    try:
        ir = parse_intent(target.path)
    except IntentParseError as exc:
        add("intent-unparseable", str(exc), f"fix {target.path}")
        return []
    status = ir.get("status", "")
    tr.status = status
    if status == "COMPLETE":
        tr.ibs = [c.ib_id for c in intent_children(engine, target.id) if c.status not in RETIRED_STATUSES]
        try:
            provenance, detail = intent_completion(engine, target.id, target.path)
        except IntegrationUnknown as exc:
            tr.missing.append(_unknown_base(
                engine, target.id, exc.why, exc.problem,
                f"restore {target.id}'s Status to ACCEPTED (Amendment Log row) and run `/implement {target.id}`"))
            return []
        gap = _completion_gap(engine, target.id, lambda: unintegrated_intent_completion_problem(engine, target.id),
                              ib=False) if provenance == "verified" else None
        if gap:
            tr.missing.append(gap)
        elif provenance:
            tr.outcome, tr.completion = "complete", provenance
        else:
            add("intent-complete-unverified", f"{target.id} is COMPLETE, but {detail}",
                f"restore {target.id}'s Status to ACCEPTED (Amendment Log row) and run `/implement {target.id}`: "
                "the driver builds what is missing, verifies the outcome and records the completion "
                "(`dekspec intent complete` is the only writer of COMPLETE)")
        return []
    if status == "SUPERSEDED":
        add("intent-superseded", f"{target.id} is SUPERSEDED by {ir.get('superseded_by') or '?'}",
            "implement its successor")
        return []
    if status != "ACCEPTED":
        add("intent-not-accepted", f"{target.id} is {status}",
            f"specify and accept it: `/spec-intent {target.id}`")
    if not (ir.get("desired_outcome") or "").strip():
        add("intent-no-outcome", f"{target.id} has no Desired Outcome", "state the observable outcome")
    if not [v for v in ir.get("verification") or [] if not v.get("manual")]:
        add("intent-no-verification", f"{target.id} has no executable Verification command",
            "add at least one Verification command that proves the outcome (ADR-029)")
    autonomy = (ir.get("autonomy") or "").lower()
    if autonomy not in AUTONOMOUS_LEVELS:
        add("intent-autonomy", f"{target.id} declares autonomy `{autonomy or 'none'}` — an explicit restriction "
            "that gates steps an autonomous run takes (manual: every step; low: the merge)",
            f"if the restriction no longer reflects a decision a person must make, raise {target.id}'s Autonomy "
            "to `medium` (the default for new implementation Intents: acceptance is the approval) with an "
            "Amendment Log row; otherwise implement it manually (`/orchestrate-coding-session`, `/land-intent`)")
    for text in _blocking_issues(ir.get("open_issues")):
        add("blocking-open-issue", f"{target.id} has an unresolved blocking Open Issue: {text}",
            "resolve it (check it off with the resolution) before implementing")
    for ae in ir.get("linked_architecture_elements") or []:
        ref = ae.get("id") if isinstance(ae, dict) else str(ae)
        st = _spec_status(engine.repo_root, ref, spec_root) if ref else None
        if st not in APPROVED_STATUSES:
            add("spec-not-approved", f"{target.id} links {ref}, which is {st or 'missing'}",
                f"accept {ref} (`/write-ae --accept`) or unlink it")
    mission = (ir.get("mission") or {}).get("id") if isinstance(ir.get("mission"), dict) else None
    if mission:
        st = _spec_status(engine.repo_root, mission, spec_root)
        if st in ("KILLED", "SUPERSEDED") or st is None:
            add("mission-inactive", f"{target.id}'s Mission {mission} is {st or 'missing'}",
                "re-parent the Intent or supersede it")
        ceiling = _mission_ceiling(engine, mission)
        if ceiling and autonomy in AUTONOMOUS_LEVELS and \
                _AUTONOMY_RANK.get(ceiling, -1) < _AUTONOMY_RANK[autonomy] and ceiling not in AUTONOMOUS_LEVELS:
            add("mission-autonomy-ceiling", f"{target.id}'s Mission {mission} caps autonomy at `{ceiling}`, "
                "below an autonomous run", f"the Mission's owner raises {mission}'s Autonomy ceiling, or "
                f"implement {target.id} manually")
    children = [c for c in intent_children(engine, target.id) if c.status not in ("SUPERSEDED", "DEPRECATED")]
    if not children:
        add("intent-no-ibs", f"{target.id} has no executable IB (`**Parent:** {target.id}`)",
            f"decompose it: `/write-intent --decompose {target.id}`, then `/write-ibs` and `dekspec ib accept`")
    tr.ibs = [c.ib_id for c in children]
    return children


def _mission_ceiling(engine: Engine, mission: str) -> str | None:
    """The Mission's `**Autonomy ceiling:**` (read directly: a Mission that
    fails full validation still caps its Intents)."""
    try:
        path = artifact_path(engine.repo_root, mission, spec_root=engine.spec_root)
    except AmbiguousReference:
        return None
    if not path:
        return None
    m = re.search(r"^\*\*Autonomy ceiling:\*\*\s*`?([a-z]+)", path.read_text(encoding="utf-8"), re.M | re.I)
    return m.group(1).lower() if m and m.group(1).lower() in _AUTONOMY_RANK else None


def _completion_recorded(engine: Engine, ident: str) -> bool:
    return engine.current_completion(ident) is not None  # a reopened completion no longer counts


def intent_completion(engine: Engine, intent_id: str, path: Path) -> tuple[str | None, str]:
    """Provenance of an Intent's COMPLETE: ``("verified", …)`` — a completion
    record over complete IBs; ``("historical", …)`` — no delegated IBs, every
    legacy IB historically complete, and the Intent already terminal in the
    history at or before the delivery base; else ``(None, why not)``. Raises
    :class:`IntegrationUnknown` when the answer rests on history and the
    authoritative base does not resolve."""
    children = [c for c in intent_children(engine, intent_id) if c.status not in RETIRED_STATUSES]
    incomplete = []
    for c in children:
        try:
            if not engine.is_complete(c.ib_id):
                incomplete.append(c)
        except ExecutionError:
            incomplete.append(c)
    if incomplete:
        historical = [c.ib_id for c in incomplete if not c.is_delegated and c.status == "COMPLETE"]
        why = _base_problem(engine) if historical else None
        if why:
            raise IntegrationUnknown(intent_id, why, f"its legacy IB(s) {', '.join(historical)} are complete only "
                                                     "by their history")
        return None, f"its IB(s) {', '.join(c.ib_id for c in incomplete)} are not complete (no completion record)"
    if _completion_recorded(engine, intent_id):
        return "verified", "completion record over complete IBs"
    delegated = [c.ib_id for c in children if c.is_delegated]
    if delegated:
        return None, (f"it has no completion record, and its IBs ({', '.join(delegated)}) were delivered under "
                      "the execution engine — its outcome verification was never recorded")
    try:
        rel = str(Path(path).resolve().relative_to(engine.repo_root.resolve()))
    except ValueError:
        return None, "it has no completion record and its history cannot be read"
    try:
        rev = resolve_base(engine.repo_root, engine.base)
    except ScopeError as exc:
        raise IntegrationUnknown(intent_id, str(exc), "it has no completion record and is complete only by its "
                                                      "history") from exc
    for _commit, _p, text in file_versions(engine.repo_root, rel, rev=rev):
        if _intent_status_of(text) in LEGACY_TERMINAL_STATUSES | {"LOCKED"}:
            return "historical", "completed before execution records (legacy IBs only)"
    return None, "it has no completion record and was not COMPLETE at the delivery base"


def _intent_status_of(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    return nxt.strip().split()[0].strip("`*_").upper()
    return ""


def _order(contracts: dict[str, IBContract], rank: dict[str, int]) -> tuple[list[str], list[str] | None]:
    """Topological order of the selected IBs over their in-selection
    dependencies; returns (order, cycle)."""
    pending = {k: {d for d in c.depends_on if d in contracts} for k, c in contracts.items()}
    order: list[str] = []
    while pending:
        free = sorted((k for k, deps in pending.items() if not deps), key=lambda k: (rank.get(k, 0), k))
        if not free:
            return order, sorted(pending)
        for k in free:
            order.append(k)
            del pending[k]
        for deps in pending.values():
            deps.difference_update(free)
    return order, None


def _groups(targets: list[TargetReadiness], contracts: dict[str, IBContract]) -> list[list[str]]:
    owner = {ib: t.id for t in targets for ib in t.ibs}
    parent = {t.id: t.id for t in targets}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ib, c in contracts.items():
        for dep in c.depends_on:
            if dep in owner and ib in owner:
                a, b = find(owner[ib]), find(owner[dep])
                if a != b:
                    parent[a] = b
    groups: dict[str, list[str]] = {}
    for t in targets:
        groups.setdefault(find(t.id), []).append(t.id)
    return sorted(sorted(g) for g in groups.values())


def _resolves(root: Path, ref: str) -> bool:
    return _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode == 0


def authoritative_base(root: Path, integration: IntegrationSettings) -> tuple[str, str]:
    """The delivery base as the driver integrates into it: its branch name, and the
    ref that is authoritative for it — the local branch for `merge`, the configured
    remote's tracking branch for a forge method — returned whether or not it
    resolves here. Nothing is substituted for it: a local branch is not the forge's
    history, so an unfetched remote base is unknown, never local `main` (ADR-061).
    With no configured base the name is `main` or `master`, as the authoritative refs
    (else the local branches) show; the local branch names it, never its history."""
    from dekspec.implement.integration import base_ref

    name = integration.base or next(
        (b for b in ("main", "master") if _resolves(root, base_ref(root, b, integration, fetch=False))), None) or next(
        (b for b in ("main", "master") if _resolves(root, f"refs/heads/{b}")), "main")
    return name, base_ref(root, name, integration, fetch=False)


def _shown(ref: str) -> str:
    for prefix in ("refs/remotes/", "refs/heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _base_tip(root: Path, ref: str) -> str | None:
    """The commit the delivery integrates into, without fetching."""
    proc = _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    return proc.stdout.strip() if proc.returncode == 0 else None


def _implementation_ahead(engine: Engine, tip: str, contracts: dict[str, IBContract],
                          spec_paths: list[str]) -> list[str]:
    """Files this checkout changes relative to the base that are not the
    targets' specification material: governed specs, the targets' acceptance
    assets, execution and tracker records, workflow configuration."""
    from dekspec.execution.contract import ContractError, load_contract
    from dekspec.execution.scope import _bookkeeping_only, _is_lifecycle, _never_pre_run, changed_files, predates_run

    root = engine.repo_root
    merge_base = _git(root, "merge-base", "HEAD", tip).stdout.strip() or tip
    # Specification material: every authorized IB's contract and acceptance assets, not only the targets'.
    material = {c.rel_path for c in contracts.values()}
    briefs = root / engine.spec_root / "impl-briefs"
    for path in sorted(briefs.rglob("IB-*.md")) if briefs.is_dir() else []:
        try:
            other = load_contract(root, str(path), spec_root=engine.spec_root)
        except ContractError:
            continue
        if other.is_delegated and other.status in ("ACCEPTED", "COMPLETE"):
            material |= {other.rel_path, *other.acceptance_asset_paths()}
    # The run's own specification: the target Intents and IBs and those IBs' acceptance assets.
    own = set(spec_paths) | {a for c in contracts.values() for a in c.acceptance_asset_paths()}
    # What the engine attributes to before a target's authorization is not charged to the run.
    anchors = []
    for c in contracts.values():
        try:
            st = engine.state(c.ib_id)[2]
        except ExecutionError:
            continue
        anchors.append((st.pre_execution_baseline or st.baseline or {}).get("commit"))
    ahead = []
    for change in changed_files(root, merge_base):
        paths = [p for p in (change.path, change.old_path) if p]
        if all(p.startswith(engine.spec_root + "/") or _is_lifecycle(p, material, engine.spec_root) for p in paths):
            continue
        if _bookkeeping_only(root, merge_base, change, engine.spec_root):
            continue
        # An autonomous delivery carries only the specification's own companions: changes made
        # before the authorization in commits that also authored specification — never
        # unrelated earlier work, and never DekSpec state or test-runner configuration.
        if anchors and not any(_never_pre_run(p) for p in paths) and all(
                a and predates_run(root, merge_base, a, p, engine.spec_root, companions_of=own)
                for a in anchors for p in paths):
            continue
        ahead.append(change.path)
    return sorted(set(ahead))


def _environment(engine: Engine, integration: IntegrationSettings, contracts: dict[str, IBContract],
                 spec_paths: list[str], readiness: Readiness) -> None:
    root = engine.repo_root
    add = lambda code, detail, fix: readiness.missing.append(Missing("environment", code, detail, fix))  # noqa: E731
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        add("not-a-repository", f"{root} is not a git repository", "run `/implement` inside the repository")
        return
    tip = _base_tip(root, engine.base) if engine.base else None
    if tip is None:
        add("no-integration-base", f"the integration base `{readiness.base or 'main'}` does not resolve here"
            + (f" (the driver integrates into `{_shown(engine.base or '')}`)"
               if integration.method == "github" else ""),
            "fetch it, or set `integration.base` in `.dekspec/config.yaml`")
    elif _git(root, "merge-base", "--is-ancestor", tip, "HEAD").returncode != 0:
        add("checkout-behind-base", f"the current checkout does not contain the tip of `{readiness.base}`",
            f"update this checkout from `{readiness.base}` first")
    else:
        ahead = _implementation_ahead(engine, tip, contracts, spec_paths)
        if ahead:
            add("checkout-ahead-of-base",
                f"this checkout carries changes `{readiness.base}` does not have, and the delivery starts from it, "
                "so they would be charged to the run: " + ", ".join(ahead[:6]) + (" …" if len(ahead) > 6 else ""),
                f"run `/implement` from a checkout of `{readiness.base}` with the specifications committed, or "
                f"integrate these changes into `{readiness.base}` first")
    dirty = [line[3:] for line in _git(root, "status", "--porcelain", "--", *spec_paths).stdout.splitlines()]
    if dirty:
        add("uncommitted-spec", "specifications for the targets are not committed: " + ", ".join(dirty[:6]),
            "commit them — the delivery starts from the committed checkout")
    readiness.integration = {"method": integration.method, "base": readiness.base, "remote": integration.remote,
                             "push": integration.push}
    if integration.method == "github":
        if not shutil.which("gh"):
            add("forge-cli-missing", "integration.method is github but `gh` is not installed",
                "install the GitHub CLI, or set `integration.method: merge`")
        elif subprocess.run(["gh", "auth", "status"], cwd=str(root), capture_output=True).returncode != 0:
            add("forge-unauthenticated", "`gh auth status` fails", "authenticate: `gh auth login`")
        if _git(root, "remote", "get-url", integration.remote).returncode != 0:
            add("forge-remote-missing", f"no git remote `{integration.remote}`",
                "add the remote, or set `integration.remote`")
    elif integration.push and _git(root, "remote", "get-url", integration.remote).returncode != 0:
        add("push-remote-missing", f"integration.push is set but there is no remote `{integration.remote}`",
            "add the remote, or unset `integration.push`")
    if any(a.kind == "pytest" for c in contracts.values() for a in c.acceptance):
        python = resolve_python(root, engine.settings.python)
        if not _has_pytest(python, root):
            add("no-test-interpreter", f"no interpreter with pytest (tried {python})",
                "set `execution.python`, or install pytest into the project environment")
    for c in contracts.values():
        if c.status != "ACCEPTED":
            continue
        for probe in engine._probe(c):
            if probe["required"] and not probe["ok"]:
                add("prerequisite-unavailable", f"{c.ib_id} needs {probe['prerequisite']} "
                    f"(probe `{probe.get('probe', '')}` failed)", "make it available, then re-run `/implement`")


def assess(repo_root: Path, targets: list[Target], *, spec_root: str = "dekspec",
           check_environment: bool = True) -> Readiness:
    integration = load_integration(Path(repo_root))
    # Completion and dependency provenance are judged against the delivery's base (R5),
    # exactly as the driver integrates into it (a forge method: the remote's copy). An
    # authoritative base that does not resolve stays unknown; nothing stands in for it.
    name, ref = authoritative_base(Path(repo_root), integration)
    engine = Engine(Path(repo_root), spec_root=spec_root, base=ref)
    readiness = Readiness(base=name)
    rank: dict[str, int] = {}
    contracts: dict[str, IBContract] = {}
    per_target: list[tuple[TargetReadiness, list[IBContract]]] = []
    for i, target in enumerate(targets):
        tr = TargetReadiness(target.id, target.kind, target.status, "ready")
        if target.kind == "intent":
            children = _check_intent(engine, target, tr, spec_root)
        else:
            try:
                c = engine.contract(target.id)
            except ExecutionError as exc:
                tr.missing.append(Missing(target.id, "ib-unparseable", str(exc), f"fix {target.path}"))
                children = []
            else:
                tr.status = c.status
                children = [c]
                tr.ibs = [c.ib_id]
                if engine.is_complete(c.ib_id):
                    gap = _completion_gap(engine, c.ib_id, lambda: engine.unintegrated_completion_problem(c.ib_id),
                                          ib=True) if c.is_delegated else None
                    if gap:
                        tr.missing.append(gap)
                    else:
                        tr.outcome = "complete"
                        tr.completion = "verified" if c.is_delegated else "historical"
                    children = []
        for c in children:
            contracts[c.ib_id] = c
            rank.setdefault(c.ib_id, i)
        per_target.append((tr, children))
        readiness.targets.append(tr)
    selected = set(contracts)
    for tr, children in per_target:
        for c in children:
            _check_ib(engine, c, tr, selected)
    active = {k: c for k, c in contracts.items() if c.status != "COMPLETE"}
    readiness.order, cycle = _order(active, rank)
    if cycle:
        readiness.missing.append(Missing("package", "dependency-cycle",
                                         "the selected IBs depend on each other in a cycle: " + ", ".join(cycle),
                                         "break the cycle in the IBs' `Depends on`"))
    for tr in readiness.targets:
        if tr.outcome != "complete" and tr.missing:
            tr.outcome = "not-ready"
    readiness.groups = _groups([t for t in readiness.targets if t.outcome == "ready"], contracts)
    if check_environment and any(t.outcome == "ready" for t in readiness.targets):
        spec_paths = [str(t.path.relative_to(repo_root)) for t in targets if not t.provisional
                      and Path(t.path).is_relative_to(repo_root)] + [c.rel_path for c in contracts.values()]
        _environment(engine, integration, active, spec_paths, readiness)
    return readiness
