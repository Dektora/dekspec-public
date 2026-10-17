"""The implementation driver (ADR-059): decide, and where possible take, the
next step of an Implementation Run.

`next_step` is a function of durable state — the IB, Intent and run records of
each delivery, git and the forge. It performs every mechanical step itself and
returns the single step only the agent harness can take (dispatch a builder,
reviewer, conflict resolver or intent reviewer; wait for the forge), or a
terminal result. The harness loops ``next`` → act → ``ack`` → ``next``.

Stages per delivery, re-derived on every call:

1. prepare — delivery worktree and branch, run record with the authorization;
2. update — merge a moved base into the branch (conflicts → resolver);
3. construct — start each IB run in dependency order; builders build and
   repair until each IB's acceptance evidence passes at the current content;
4. verify the delivery — `delivery verify` (every IB plus the base's
   integration command) and each target Intent's outcome verification. An IB
   whose passing evidence the driver itself recorded at the identical binding
   (fingerprint, contract hash, baseline, context manifest, base) is not
   executed again; a builder's evidence always is. It runs again whenever the
   binding changes, after completion too;
5. review — an independent reviewer per IB; a failed verdict goes back to the
   builder with its findings;
6. forge checks (``github``) — push the reviewed head and read the pull
   request's required checks *before* completion, so a failing check goes back
   to a builder with its evidence while the work can still be repaired;
7. complete — `ib complete` in dependency order, then `intent complete`;
8. land — `delivery check --rerun`, recorded as ``landing.verified`` at the
   content fingerprint and base. It re-executes acceptance and the integration
   command except where the driver's own passing delivery verification stands
   at the identical binding, and the record names what it relied on; integrate;
   confirm the integrated content is the verified content; with ``push: true``,
   the remote must hold it too.

A delivery counts as landed only from that evidence. Its head being in the
base (someone merged a partial branch, or the process died after merging) is
an observation, not a verification: without a landing record for the current
content, the run keeps going.

Recovery events (failing tests, failed reviews, failed integration or outcome
checks, merge conflicts, lost dispatches) turn into the next dispatch.
Repeated failure without new evidence triggers at most two recorded strategy
changes per IB before it becomes a genuine blocker. Genuine blockers are
recorded; independent deliveries keep going.
"""

from __future__ import annotations

import hashlib
import subprocess
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from dekbuilder._spec import require_spec

from dekspec import builder_compat as spec
from dekspec.api import parse_intent
from dekspec.builder_compat import delivery_failure_reasons, delivery_check, delivery_verify, dependency_ready, verify_integration
from dekspec.builder_compat import (
    CODE_REVIEWER_ROLE,
    VERIFIER_ROLE,
    Blocked,
    Engine as SpecEngine,
    ExecutionError,
    probe_blocker,
    probe_prerequisites,
    check_test_interpreter,
    verdict_policy_problem,
)
from dekspec.builder_compat import (
    intent_children,
    intent_complete,
    intent_evaluate,
    intent_reopen,
    intent_verify,
)
from dekspec.builder_compat import EXECUTION_DIRNAME
from dekspec.builder_compat import ScopeError, resolve_base
from dekspec.builder_compat import fold
from dekbuilder.implement import integration as integ
from dekspec.builder_compat import AgentRole, RoleDefinitionError, load_role
from dekbuilder.implement import lean, prompts
from dekbuilder.implement.config import IntegrationSettings, load_integration
from dekbuilder.implement.environment import (
    EnvironmentUnavailable, _entered_environment, checkout_environment, coordinator_packages, copy_provenance,
    run_operation,
)
from dekbuilder.implement.readiness import assess
from dekbuilder.implement.targets import resolve

__all__ = ["DRIVER", "ack", "find_deliveries", "next_step", "status"]

DRIVER = "implement-driver"
MAX_STRATEGIES = 2
#: Reviewer dispatches in a row that returned without recording a verdict
#: before the run stops with a blocker instead of dispatching another.
MAX_SILENT_REVIEWS = 3
MAX_FORGE_FAILURES = 3
MAX_REOPENS = 3
MAX_STEPS = 400

_CONSTRUCTION = {"investigation-recorded", "attempt-recorded", "evidence-present", "acceptance-passed",
                 "scope-and-protected-surfaces", "acceptance-integrity", "no-stalled-attempt"}
_GENUINE_GATE = {"obligations-resolve", "delegated-contract", "authorized", "record-integrity"}
_RECOVERABLE_BLOCKERS = {"attempts-exhausted", "no-progress", "stalled"}


class DriverError(RuntimeError):
    """The request cannot be driven (usage or repository problem)."""


_provenance: ContextVar[dict] = ContextVar("delivery_provenance", default={})


class _RunRecord:
    """Add operational provenance; the provider remains the only record writer."""

    def __init__(self, record):
        self.record = record

    def __getattr__(self, name):
        return getattr(self.record, name)

    def append(self, kind, actor, data):
        return self.record.append(kind, actor, {**_provenance.get(), **data})


class Engine(SpecEngine):
    """Provider client with delivery interpreter selection and run provenance."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _provenance.get():
            environment = checkout_environment(self.repo_root, configured_python=self.settings.python)
            self.settings = replace(self.settings, python=environment.python)

    def record(self, artifact_id):
        record = super().record(artifact_id)
        return _RunRecord(record) if artifact_id.startswith("RUN-") else record


# ------------------------------------------------------------------ plumbing
def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), env=checkout_environment(cwd).env,
                          capture_output=True, text=True)


def _main_worktree(root: Path) -> Path:
    for line in _git(root, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree "):])
    return Path(root)


def _branch_path(root: Path, branch: str) -> Path | None:
    path = None
    for line in _git(root, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def _dirty(path: Path) -> bool:
    return bool(_git(path, "status", "--porcelain").stdout.strip())


def _commit(path: Path, message: str) -> str | None:
    if not _dirty(path):
        return None
    if _git(path, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0 and \
            _git(path, "diff", "--name-only", "--diff-filter=U").stdout.strip():
        # Never checkpoint a merge that still has conflicts: `add -A` would commit the
        # markers. The pending record events are committed with the merge's conclusion.
        return None
    _git(path, "add", "-A")
    proc = _git(path, "commit", "-q", "-m", message)
    if proc.returncode != 0:
        raise DriverError(f"committing in {path} failed: {(proc.stderr or proc.stdout).strip()[-400:]}")
    return _git(path, "rev-parse", "HEAD").stdout.strip()


# ------------------------------------------------------------------ deliveries
@dataclass
class Delivery:
    slug: str
    targets: list[str]
    branch: str
    path: Path
    base: str
    run_id: str
    exists: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"slug": self.slug, "targets": self.targets, "branch": self.branch, "worktree": str(self.path),
                "base": self.base, "run": self.run_id}


def _slug(targets: list[str]) -> str:
    return "-".join(sorted(t.lower() for t in targets))


def _delivery(root: Path, targets: list[str], base: str) -> Delivery:
    main = _main_worktree(root)
    slug = _slug(targets)
    branch = f"implement/{slug}"
    path = _branch_path(root, branch) or main.parent / f"{main.name}-implement-{slug}"
    exists = _git(root, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").returncode == 0
    return Delivery(slug, sorted(targets), branch, path, base, f"RUN-{slug.upper()}", exists)


def find_deliveries(root: Path) -> list[str]:
    """Branches of existing Implementation Runs."""
    out = _git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads/implement/").stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


@dataclass
class RunView:
    auth: dict[str, Any]
    issued: dict[str, dict[str, Any]] = field(default_factory=dict)
    returned: set[str] = field(default_factory=set)
    lost: set[str] = field(default_factory=set)
    strategies: dict[str, int] = field(default_factory=dict)
    blockers: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_strategy: dict[str, str] = field(default_factory=dict)
    done: dict[str, Any] | None = None
    landing: dict[str, Any] | None = None
    forge_passed: dict[str, Any] | None = None
    forge_failures: list[dict[str, Any]] = field(default_factory=list)
    issued_at: dict[str, int] = field(default_factory=dict)
    integrated_at: int = 0

    @property
    def outstanding(self) -> list[str]:
        return [d for d in self.issued if d not in self.returned and d not in self.lost]

    def last_dispatch(self, key: str) -> dict[str, Any] | None:
        matching = [d for d in self.issued.values() if d.get("key") == key]
        return matching[-1] if matching else None


def _view(engine: Engine, run_id: str, *, strict: bool = False) -> RunView:
    events = engine.record(run_id).events(strict=strict)
    view = RunView(auth={})
    for ev in events:
        d = ev.data
        if ev.type == "run.requested":
            view.auth = d
        elif ev.type == "dispatch.issued":
            view.issued[d["id"]] = d
            view.issued_at[d["id"]] = ev.seq
        elif ev.type == "dispatch.returned":
            view.returned.add(d["id"])
        elif ev.type == "dispatch.lost":
            view.lost.add(d["id"])
        elif ev.type == "strategy.changed":
            view.strategies[d["ib"]] = view.strategies.get(d["ib"], 0) + 1
            view.last_strategy[d["ib"]] = d.get("note", "")
        elif ev.type == "blocker.recorded":
            view.blockers[d["key"]] = d
        elif ev.type == "blocker.cleared":
            view.blockers.pop(d["key"], None)
        elif ev.type == "run.integrated":
            view.done = d
            view.integrated_at = ev.seq
        elif ev.type == "landing.verified":
            view.landing = d
        elif ev.type == "forge.checks-passed":
            view.forge_passed = d
        elif ev.type == "forge.checks-failed":
            view.forge_failures.append(d)
    return view


def _clean_but_records(path: Path) -> bool:
    return not [ln for ln in _git(path, "status", "--porcelain").stdout.splitlines()
                if not ln[3:].startswith(EXECUTION_DIRNAME + "/")]


def _intent_path(engine: Engine, intent: str) -> Path | None:
    return next(iter(sorted((engine.repo_root / engine.spec_root / "intents").glob(f"{intent}-*.md"))), None)


def _landed(engine: Engine, view: RunView, ibs: list[str], intents: list[str], base_ref: str) -> tuple[bool, str]:
    """Is the delivery's current content the content that passed the landing
    gate, with every target completed through its gate? Durable evidence only:
    where the head sits relative to the base proves nothing by itself."""
    if not view.landing:
        return False, "the delivery never passed its landing gate (`delivery check --rerun`)"
    if view.landing.get("fingerprint") != engine.fingerprint() or not _clean_but_records(engine.repo_root):
        return False, "the delivery's content changed after its landing gate passed"
    landing_fp = view.landing.get("fingerprint")
    incomplete = [ib for ib in ibs if not engine.is_complete(ib, base=base_ref)
                  or (engine.current_completion(ib) or {}).get("fingerprint") != landing_fp]
    for intent in intents:
        path = _intent_path(engine, intent)
        if not path or parse_intent(path).get("status") != "COMPLETE" or \
                (engine.current_completion(intent) or {}).get("fingerprint") != landing_fp:
            incomplete.append(intent)
    if incomplete:
        return False, f"not completed through their gates: {', '.join(incomplete)}"
    return True, "landing gate passed at the current content"


def _spec_hashes(engine: Engine, targets: list[str], ibs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in targets:
        if t.startswith("INT-"):
            path = next(iter(sorted((engine.repo_root / engine.spec_root / "intents").glob(f"{t}-*.md"))), None)
            if path:
                out[t] = hashlib.sha256(path.read_bytes()).hexdigest()
    for ib in ibs:
        out[ib] = engine.contract(ib).contract_hash()
    return out


def _bind_session(d: Delivery) -> None:
    """With DekSpec commit hooks installed, commits need a session bound to
    the work; bind the delivery's worktree to its single target."""
    from dekspec.builder_compat import hooks_installed

    try:
        installed = hooks_installed(d.path)
    except Exception:  # noqa: BLE001 — a probe; absence of hooks is the common case
        installed = False
    if installed and len(d.targets) == 1:
        from dekbuilder.implement.environment import run_module

        run_module(checkout_environment(d.path, configured_python=SpecEngine(d.path).settings.python),
                   "dekspec.cli", ["session", "start", d.targets[0], "--branch", d.branch])


def _prepare(root: Path, d: Delivery, request: str, actor: str, ibs: list[str],
             settings: IntegrationSettings) -> None:
    created = not d.path.exists()
    if created:
        if d.exists:
            proc = _git(root, "worktree", "add", "-q", str(d.path), d.branch)
        else:
            proc = _git(root, "worktree", "add", "-q", "-b", d.branch, str(d.path), "HEAD")
        if proc.returncode != 0:
            raise DriverError(f"creating the delivery worktree failed: {proc.stderr.strip()[-400:]}")
    token = _provenance.set({"copy": copy_provenance(coordinator_packages(), "coordinator")})
    try:
        engine = Engine(d.path, base=integ.base_ref(d.path, d.base, settings, fetch=False))
        rec = engine.record(d.run_id)
        if not rec.exists():
            scopes = {ib: list(engine.contract(ib).scope) for ib in ibs}
            rec.append("run.requested", actor, {
                "request": request, "requested_by": actor, "targets": d.targets, "ibs": ibs, "scopes": scopes,
                "base": d.base, "branch": d.branch, "method": settings.method,
                "operations": ["construct", "test", "review", "repair", "integrate"],
                "excludes": ["change acceptance conditions or obligations", "approve specifications",
                             "bypass branch protection or required checks", "deploy", "production operations"],
                "specs": _spec_hashes(engine, d.targets, ibs), "started_at": _git(d.path, "rev-parse", "HEAD").stdout.strip()})

        events = rec.events()
        setup = next((e for e in events if e.type == "checkout.setup"), None)
        if created or setup is None:
            environment = checkout_environment(d.path)
            command = settings.worktree_setup
            try:
                proc = subprocess.run(command, shell=True, cwd=environment.cwd, env=environment.env,
                                      capture_output=True, text=True) if command else None
                detail = (proc.stderr or proc.stdout)[-1500:] if proc else ""
                ok = proc is None or proc.returncode == 0
            except OSError as exc:
                ok, detail = False, str(exc)
            rec.append("checkout.setup", DRIVER, {"checkout": str(d.path), "command": command,
                                                 "ok": ok, "detail": detail})
            if ok:
                try:
                    _bind_session(d)
                except EnvironmentUnavailable:
                    pass  # the delivery entry records the unavailable copy before any judgment
                else:
                    _commit(d.path, f"implement({d.slug}): start run and worktree setup — {request}")
    finally:
        _provenance.reset(token)


# ------------------------------------------------------------------ step result
def _action(kind: str, d: Delivery | None, **payload: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"action": kind}
    if d is not None:
        out["delivery"] = d.as_dict()
    out.update(payload)
    out.update(_provenance.get())
    return out


@dataclass
class _Ctx:
    root: Path
    d: Delivery
    engine: Engine
    settings: IntegrationSettings
    base_ref: str
    ibs: list[str]
    intents: list[str]
    view: RunView


def _dispatch(ctx: _Ctx, role: str, key: str, actor: str, prompt: str, *, agent_role: AgentRole,
              **info: Any) -> dict[str, Any]:
    """Issue one dispatch. ``agent_role`` is the Agent Role Specification the
    prompt was composed from (ADR-061); its stamp — id, policy revision and
    content hash — is recorded with the prompt's hash, so the record names the
    exact role definition every worker received."""
    rec = ctx.engine.record(ctx.d.run_id)
    n = len(ctx.view.issued) + 1
    ident = f"D-{n}"
    stamp = agent_role.stamp()
    rec.append("dispatch.issued", DRIVER, {"id": ident, "role": role, "key": key, "actor": actor,
                                           "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                                           "agent_role": stamp, **info})
    _commit(ctx.d.path, f"implement({ctx.d.slug}): dispatch {ident} {role} {key}")
    return _action("dispatch", ctx.d, id=ident, role=role, key=key, actor=actor, worktree=str(ctx.d.path),
                   prompt=prompt, agent_role=stamp, **info)


def _role(dispatch_role: str) -> AgentRole:
    """The role a dispatch runs under — fixed by the driver, never by a worker.
    A missing or malformed definition stops the run with an actionable error
    before anything is dispatched."""
    try:
        return load_role(prompts.DISPATCH_ROLES[dispatch_role])
    except RoleDefinitionError as exc:
        raise DriverError(f"cannot dispatch the {dispatch_role}: {exc}") from exc


def _block(ctx: _Ctx, key: str, kind: str, detail: str, **extra: Any) -> None:
    if key in ctx.view.blockers and ctx.view.blockers[key].get("detail") == detail:
        return
    data = {"key": key, "kind": kind, "detail": detail, **extra}
    ctx.engine.record(ctx.d.run_id).append("blocker.recorded", DRIVER, data)
    ctx.view.blockers[key] = data


def _clear(ctx: _Ctx, key: str) -> None:
    if key in ctx.view.blockers:
        ctx.engine.record(ctx.d.run_id).append("blocker.cleared", DRIVER, {"key": key})
        ctx.view.blockers.pop(key, None)


# ------------------------------------------------------------------ IB phase
@dataclass
class _IB:
    id: str
    phase: str
    detail: str = ""
    failing: dict[str, str] = field(default_factory=dict)
    st: Any = None


def _ib(ctx: _Ctx, ib: str) -> _IB:
    eng = ctx.engine
    c = eng.contract(ib)
    _rec, _events, st = eng.state(c.ib_id)
    if not st.started and not st.completions:
        deps = [dep for dep in c.depends_on if not dependency_ready(eng, dep)]
        return _IB(ib, "waiting" if deps else "not-started", ", ".join(deps), st=st)
    if st.blockers:
        reasons = {b.get("reason") for b in st.blockers}
        if reasons <= _RECOVERABLE_BLOCKERS:
            return _IB(ib, "stuck", "; ".join(f"{b['reason']}: {b.get('detail', '')}" for b in st.blockers), st=st)
        if all(probe_blocker(b) for b in st.blockers):  # the engine's own failed probe: re-probe later
            return _IB(ib, "prerequisite", "; ".join(b.get("detail", "") for b in st.blockers), st=st)
        return _IB(ib, "blocked", "; ".join(f"{b['reason']}: {b.get('detail', '')}" for b in st.blockers), st=st)
    gate = eng.evaluate_completion(ib, readonly=True, base=ctx.base_ref)
    failing = {ch.name: ch.detail for ch in gate.checks if not ch.ok}
    if st.completions:
        if not failing:
            return _IB(ib, "complete", st=st)
        if "evidence-current" in failing or "evidence-present" in failing:
            return _IB(ib, "reverify", failing=failing, st=st)
        if set(failing) <= {"independent-review", "dependencies-complete"}:
            # Needs a fresh review, or waits for a reopened dependency to complete again:
            # neither is a reason to rebuild it.
            if "independent-review" in failing:
                return _IB(ib, "review", failing=failing, st=st)
            return _IB(ib, "complete", "waiting for " + failing["dependencies-complete"], failing=failing, st=st)
        return _IB(ib, "broken", "; ".join(f"{k}: {v}" for k, v in failing.items()), failing, st)
    if failing.keys() & _GENUINE_GATE:
        return _IB(ib, "blocked", "; ".join(f"{k}: {failing[k]}" for k in failing.keys() & _GENUINE_GATE),
                   failing, st)
    latest = st.latest_evidence("ib")
    if "evidence-current" in failing and latest and latest[1].get("overall") == "passed" \
            and not (failing.keys() & (_CONSTRUCTION - {"investigation-recorded"})):
        return _IB(ib, "reverify", failing=failing, st=st)
    if failing.keys() & (_CONSTRUCTION | {"evidence-current"}) or st.open_attempt:
        return _IB(ib, "build", failing=failing, st=st)
    if "independent-review" in failing:
        return _IB(ib, "review", failing=failing, st=st)
    if "dependencies-complete" in failing:
        return _IB(ib, "verified", failing=failing, st=st)
    return _IB(ib, "completable", failing=failing, st=st)


def _build_reasons(ctx: _Ctx, v: _IB) -> tuple[str, list[str]]:
    st = v.st
    latest = st.latest_evidence("ib")
    reasons: list[str] = []
    if latest and latest[1].get("overall") != "passed":
        reasons += delivery_failure_reasons(latest[1])
    for name in ("scope-and-protected-surfaces", "acceptance-integrity"):
        if name in v.failing:
            reasons.append(f"{name}: {v.failing[name]}")
    if st.verdicts and st.verdicts[-1][1].get("verdict") == "fail":
        reasons.append(f"independent review ({st.verdicts[-1][1].get('reviewer')}) failed: "
                       f"{st.verdicts[-1][1].get('notes', '')}")
    last = ctx.view.last_dispatch(f"build:{v.id}")
    if last and last["id"] in ctx.view.lost:
        return "resume", reasons
    return ("repair" if reasons else "build"), reasons


def _dispatch_builder(ctx: _Ctx, v: _IB, *, task: str | None = None, reasons: list[str] | None = None) -> dict:
    auto_task, auto_reasons = _build_reasons(ctx, v)
    task = task or auto_task
    reasons = (reasons or []) + auto_reasons
    actor = f"builder-{v.id}"
    packet = ctx.engine.context(v.id).render_markdown()
    strategy = ctx.view.last_strategy.get(v.id)
    role = _role("builder")
    prompt = prompts.builder(ctx.d.path, v.id, actor, ctx.view.auth, packet, base_ref=ctx.base_ref, task=task,
                             reasons=reasons,
                             strategy=strategy, open_attempt=v.st.open_attempt.number if v.st.open_attempt else None,
                             role=role)
    return _dispatch(ctx, "builder", f"build:{v.id}", actor, prompt, agent_role=role, ib=v.id, task=task,
                     reasons=reasons)


def _dispatch_reviewer(ctx: _Ctx, v: _IB) -> dict:
    actor = f"reviewer-{v.id}"
    latest = v.st.latest_evidence("ib")
    attention = sorted(latest[1].get("attention", [])) if latest else []
    previous = None
    if v.st.verdicts and v.st.verdicts[-1][1].get("verdict") == "fail":
        previous = v.st.verdicts[-1][1].get("notes", "")
    role = _role("reviewer")
    # The reviewer gets the recorded facts, never the builder's report, which is
    # not written to the branch at all (ADR-061 — independence).
    facts = prompts.review_facts(latest[1] if latest else None, v.st.deviations)
    prompt = prompts.reviewer(ctx.d.path, v.id, actor, ctx.view.auth, ctx.engine.context(v.id).render_markdown(),
                              base_ref=ctx.base_ref, attention=attention, previous=previous, facts=facts, role=role,
                              own_gates=_changes_gates(ctx))
    return _dispatch(ctx, "reviewer", f"review:{v.id}", actor, prompt, agent_role=role, ib=v.id,
                     attention=attention, verdicts=len(v.st.verdicts))


def _changes_gates(ctx: _Ctx) -> bool:
    copy = _provenance.get().get("copy", {})
    if copy.get("source") != "delivery":
        return False
    changed = _git(ctx.d.path, "diff", "--no-renames", "--name-only", f"{ctx.base_ref}...HEAD").stdout.splitlines()
    packages = [Path(copy[name]["path"]).resolve().parent for name in ("dekbuilder", "dekspec")]
    return any((ctx.d.path / rel).resolve().is_relative_to(package) for rel in changed for package in packages)


def _attestation_current(eng: Engine, intent: str) -> bool:
    """Whether an Intent's manual-verification attestation (if it needs one) still
    holds — in particular under the verifier's current policy revision (ADR-061).
    The driver asks this only of its own, not yet integrated, Intents; the gate
    itself exempts integrated completions."""
    gate = intent_evaluate(eng, intent)
    return all(ch.ok for ch in gate.checks if ch.name == "manual-verification-attested")


def _change_strategy(ctx: _Ctx, v: _IB, detail: str) -> bool:
    """Share the two-change budget across construction and review recovery.

    Review can exhaust attempts even though deterministic checks passed. Raise
    that exhaustion through the engine before granting its existing allowance;
    never clear another kind of blocker or reset any consumed attempts.
    """
    used = ctx.view.strategies.get(v.id, 0)
    if used >= MAX_STRATEGIES or any(b.get("reason") not in _RECOVERABLE_BLOCKERS for b in v.st.blockers):
        return False
    approach = (
        "Reproduce the failing condition or review finding at its public boundary. Trace the "
        "observed behavior back to the violated obligation, compare it with the previous diagnosis, "
        "and repair the demonstrated root cause within Scope instead of repeating the earlier patch."
        if used == 0 else
        "Reassess the implementation hypothesis using the accumulated failures and review findings. "
        "Identify the shared assumption the earlier repairs left intact; choose a different in-scope "
        "implementation approach that removes it, and verify it against all affected obligations. "
        "If that requires changing the contract or Scope, record a blocker instead."
    )
    note = f"Strategy change {used + 1} of {MAX_STRATEGIES}: {detail}. {approach}"
    if not v.st.blockers:
        ctx.engine.block(v.id, DRIVER, "attempts-exhausted", detail)
    ctx.engine.unblock(v.id, DRIVER, f"implement driver: {note}", extra_attempts=2)
    ctx.engine.record(ctx.d.run_id).append("strategy.changed", DRIVER, {"ib": v.id, "note": note})
    _commit(ctx.d.path, f"implement({ctx.d.slug}): strategy change for {v.id}")
    ctx.view = _view(ctx.engine, ctx.d.run_id)
    return True


def _reconcile_review_blocker(ctx: _Ctx, v: _IB) -> None:
    """Resolve silence on a verdict, non-convergence only on a validated PASS."""
    key = f"review:{v.id}"
    blocker = ctx.view.blockers.get(key)
    if not blocker:
        return
    if blocker.get("kind") == "review-not-recorded":
        if len(v.st.verdicts) > blocker.get("verdicts", 0):
            last = v.st.verdicts[-1][1]
            if last.get("reviewer") not in v.st.builder_identities \
                    and not verdict_policy_problem(CODE_REVIEWER_ROLE, last):
                _clear(ctx, key)
    elif blocker.get("kind") == "review-not-converging":
        gate = ctx.engine.evaluate_completion(v.id, readonly=True, base=ctx.base_ref)
        checks = {ch.name: ch.ok for ch in gate.checks}
        if all(checks.get(name) for name in ("independent-review", "evidence-current", "acceptance-passed")):
            _clear(ctx, key)


def _repair_review(ctx: _Ctx, v: _IB) -> dict[str, Any] | None:
    """Offer a counted repair for a current FAIL, or record why none remains.

    Reopening, allowance and strategy decisions belong together: a builder must
    receive active work with a real remaining opportunity, never a completion or
    a dispatch that exists only to discover exhaustion.
    """
    notes = v.st.verdicts[-1][1].get("notes", "")
    if v.st.completions:
        problem = _reopen_for_repair(ctx, v.id, f"independent re-review failed: {notes}")
        if problem:
            _block(ctx, f"review:{v.id}", "cannot-reopen", f"{v.id}'s re-review failed — {problem}")
            return None
        _commit(ctx.d.path, f"implement({ctx.d.slug}): reopen {v.id} to repair its failed re-review")
        v = _ib(ctx, v.id)
    allowed = ctx.engine.settings.max_attempts + v.st.extra_attempts
    if v.st.attempts_used >= allowed:
        detail = (f"{v.id} used {v.st.attempts_used} of {allowed} attempts and still fails "
                  f"independent review; last findings: {notes}")
        if not _change_strategy(ctx, v, detail):
            _block(ctx, f"review:{v.id}", "review-not-converging",
                   f"{detail}; exhausted {MAX_STRATEGIES} strategy changes")
            return None
        v = _ib(ctx, v.id)
    return _dispatch_builder(ctx, v, task="repair")


def _silent_reviews(ctx: _Ctx, v: _IB) -> int:
    return _silent(ctx, f"review:{v.id}", len(v.st.verdicts))


def _silent(ctx: _Ctx, key: str, verdicts_now: int) -> int:
    """Dispatches under ``key`` in a row, most recent first, that returned without
    a verdict being recorded after them (reviews and Intent attestations alike)."""
    returned = [d for d in ctx.view.issued.values() if d.get("key") == key and d["id"] in ctx.view.returned]
    silent, after = 0, verdicts_now
    for d in reversed(returned):
        before = d.get("verdicts")
        if before is None or after > before:  # a verdict followed this dispatch (or no count was recorded)
            break
        silent += 1
        after = before
    return silent


# ------------------------------------------------------------------ one delivery
def _latest_passing(engine: Engine, artifact: str, kind: str, fp: str, cover: list[str] | None = None,
                    base_commit: str | None = None) -> bool:
    st = fold(engine.record(artifact).events(strict=False))
    latest = st.latest_evidence(kind)
    return bool(latest) and latest[1].get("fingerprint") == fp and latest[1].get("overall") == "passed" and \
        (cover is None or set(cover) <= set(latest[1].get("ibs", []))) and \
        (base_commit is None or latest[1].get("base_commit") == base_commit)


def _landing_current(view: RunView, fp: str, base_commit: str) -> bool:
    """Did the landing gate pass at this binding — this content and this base?
    The base is part of the binding (ADR-059 stage 6): a base that moved, even
    without changing the delivered content, needs the gate again."""
    return bool(view.landing and view.landing.get("fingerprint") == fp
                and view.landing.get("base_commit") == base_commit)


def _integrated(ctx: _Ctx) -> bool:
    """Is any IB's completion already integrated in the base (history that
    takes no more evidence, ADR-057)?"""
    eng = ctx.engine
    for ib in ctx.ibs:
        c = eng.contract(ib)
        if eng.current_completion(c.ib_id) is not None and \
                eng.integration_state(c.ib_id, c.rel_path, ctx.base_ref)[0] == "integrated":
            return True
    return False


def _downstream(ctx: _Ctx, views: dict[str, _IB], among: list[str]) -> _IB | None:
    candidates = [views[ib] for ib in reversed(ctx.ibs) if ib in among and views[ib].phase not in ("complete",)]
    return candidates[0] if candidates else None


def _start(ctx: _Ctx, ib: str) -> None:
    before = len(ctx.engine.record(ib).events())
    try:
        ctx.engine.start(ib, f"builder-{ib}")
    finally:
        for event in ctx.engine.record(ib).events()[before:]:
            if event.type == "prerequisites.checked":
                results = [{**p, "environment": _provenance.get()["environment"]}
                           for p in event.data["results"]]
                ctx.engine.record(ctx.d.run_id).append("prerequisites.checked", DRIVER,
                                                       {"ib": ib, "results": results})


def _verification(ctx: _Ctx, kind: str, result: dict, *, artifact: str | None = None) -> None:
    """Operational report of a provider decision; never substitutes for its evidence."""
    ctx.engine.record(ctx.d.run_id).append("verification.reported", DRIVER,
                                         {"kind": kind, "artifact": artifact, "result": result})


def _advance(ctx: _Ctx) -> dict[str, Any]:  # noqa: C901 — one decision table, kept in one place
    eng, d = ctx.engine, ctx.d
    for _ in range(MAX_STEPS):
        ctx.view = _view(eng, d.run_id)
        # A dispatch still open when `next` runs again was lost (the harness only calls `next`
        # after its workers returned): record it, and reissue the step below.
        for ident in ctx.view.outstanding:
            eng.record(d.run_id).append("dispatch.lost", DRIVER, {"id": ident})
            ctx.view.lost.add(ident)

        observed = integ.observe(d.path, d.base, ctx.settings)
        # Without its base nothing here can be verified (scope is judged against it),
        # integrated, or told apart from history: block once, naming the fix, rather than
        # dispatch work that cannot pass. The blocker clears when the base resolves.
        try:
            base_commit = resolve_base(d.path, ctx.base_ref)
        except ScopeError as exc:
            _block(ctx, "base", "base-unavailable",
                   f"the delivery base `{d.base}` does not resolve here ({exc}): fetch it, or correct "
                   "`integration.base` in `.dekspec/config.yaml`")
            return _blocked(ctx, {})
        _clear(ctx, "base")
        lean_ibs = [ib for ib in ctx.ibs if eng.contract(ib).is_lean]
        if lean_ibs:
            if len(ctx.ibs) != 1:
                _block(ctx, "lean-delivery", "cannot-start",
                       f"{', '.join(lean_ibs)}: a lean brief must be delivered alone")
                return _blocked(ctx, {})
            action = _advance_lean(ctx, lean_ibs[0])
            if action is not None:
                return action
            continue

        if observed.state == "merged" and ctx.view.done is not None:
            return _finish(ctx, observed)  # already reconciled: the recorded outcome stands
        if observed.state in ("merged", "push-pending") and \
                _landed(eng, ctx.view, ctx.ibs, ctx.intents, ctx.base_ref)[0]:
            if observed.state == "push-pending":
                pushed = _push(ctx)
                if pushed is not None:
                    return pushed
                continue
            return _finish(ctx, observed)
        # Otherwise the head being in the base is not evidence of anything (another actor
        # merged a partial branch): carry on — the branch moves past the base and lands
        # through the gates below.

        # -- update from a moved base (any time before landing) ------------------------
        in_merge = _git(d.path, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0
        conflicted = [f for f in _git(d.path, "diff", "--name-only", "--diff-filter=U").stdout.split() if f]
        if in_merge and conflicted:
            role = _role("resolver")
            return _dispatch(ctx, "resolver", "resolve:base", f"resolver-{d.slug}",
                             prompts.resolver(d.path, f"resolver-{d.slug}", ctx.view.auth,
                                              base_ref=ctx.base_ref, files=conflicted, role=role),
                             agent_role=role, files=conflicted)
        if in_merge:
            _git(d.path, "add", "-A")
            proc = _git(d.path, "commit", "-q", "--no-edit")
            if proc.returncode != 0:
                raise DriverError(f"concluding the merge failed: {(proc.stderr or proc.stdout).strip()[-300:]}")
            continue
        if observed.state == "behind":
            _commit(d.path, f"implement({d.slug}): checkpoint before updating from {d.base}")
            merge = _git(d.path, "merge", "--no-edit", "-q", ctx.base_ref)
            if merge.returncode != 0 and not _git(d.path, "diff", "--name-only", "--diff-filter=U").stdout.strip():
                raise DriverError(f"merging {ctx.base_ref} failed: {(merge.stderr or merge.stdout).strip()[-300:]}")
            continue

        # -- per-IB state --------------------------------------------------------------
        views = {ib: _ib(ctx, ib) for ib in ctx.ibs}
        progressed = False
        for ib in ctx.ibs:
            v = views[ib]
            if v.phase == "not-started":
                try:
                    _start(ctx, ib)
                    _clear(ctx, f"prereq:{ib}")
                except Blocked as exc:
                    _block(ctx, f"prereq:{ib}", "prerequisite-unavailable",
                           f"{exc} (interpreter: {eng.settings.python})",
                           environment=_provenance.get().get("environment"))
                except ExecutionError as exc:
                    _block(ctx, f"start:{ib}", "cannot-start", str(exc))
                else:
                    progressed = True
                _commit(d.path, f"implement({d.slug}): start {ib}")
            elif v.phase == "prerequisite":
                try:
                    _start(ctx, ib)  # re-probe: clears the blocker when the probe passes
                    _clear(ctx, f"prereq:{ib}")
                    progressed = True
                except (Blocked, ExecutionError) as exc:
                    _block(ctx, f"prereq:{ib}", "prerequisite-unavailable",
                           f"{exc} (interpreter: {eng.settings.python})",
                           environment=_provenance.get().get("environment"))
                _commit(d.path, f"implement({d.slug}): re-probe {ib}")
            elif v.phase == "stuck":
                if _change_strategy(ctx, v, v.detail):
                    progressed = True
                else:
                    _block(ctx, f"converge:{ib}", "no-convergence",
                           f"{ib} did not converge after {MAX_STRATEGIES} strategy changes: {v.detail}")
            elif v.phase == "reverify":
                evidence = eng.verify(ib, DRIVER, base=ctx.base_ref)
                _verification(ctx, "ib", evidence, artifact=ib)
                _commit(d.path, f"implement({d.slug}): re-verify {ib} at the current content")
                progressed = True
            elif v.phase == "broken" and v.st.completions and not (v.failing.keys() & _GENUINE_GATE):
                # A later change (a repair, a moved base) broke completed, unintegrated work:
                # reopen it and repair it — never send a builder to a completed IB.
                problem = _reopen_for_repair(ctx, ib, f"{ib} no longer verifies at the delivered content: {v.detail}")
                if problem:
                    _block(ctx, f"ib:{ib}", "cannot-reopen", f"{ib}: {v.detail} — {problem}")
                else:
                    _commit(d.path, f"implement({d.slug}): reopen {ib} to repair it")
                    return _dispatch_builder(ctx, _ib(ctx, ib), task="repair",
                                             reasons=[f"{ib} no longer verifies at the delivered content: {v.detail}"])
            elif v.phase in ("blocked", "broken"):
                _block(ctx, f"ib:{ib}", v.phase, f"{ib}: {v.detail}")
            if progressed:
                break
        if progressed:
            continue

        for ib in ctx.ibs:  # construction, in dependency order
            v = views[ib]
            if v.phase == "build":
                return _dispatch_builder(ctx, v)

        if any(views[ib].phase in ("not-started", "waiting", "prerequisite", "stuck", "blocked", "broken", "build")
               for ib in ctx.ibs):
            return _blocked(ctx, views)

        # -- every IB verified: verify the delivery and each target Intent -----------
        # At every binding (content and base) the landing gate relies on, stage 2 has run —
        # also after completion, when a moved base or a repair changed the binding — so the
        # gate never has to execute what the driver just executed. Stage 2 itself relies on
        # the driver's own per-IB re-verification at the identical binding (ADR-059 stage 2);
        # a builder's evidence is always executed again.
        fp = eng.fingerprint()
        pending = [ib for ib in ctx.ibs if views[ib].phase != "complete"]
        stale = pending or not (_landing_current(ctx.view, fp, base_commit) or _integrated(ctx))
        if stale and not any(_latest_passing(eng, ib, "delivery", fp, ctx.ibs, base_commit) for ib in ctx.ibs):
            out = delivery_verify(eng, ctx.ibs, DRIVER, base=ctx.base_ref, reuse_own=True)
            _verification(ctx, "delivery", out)
            _commit(d.path, f"implement({d.slug}): delivery verification")
            if out["delivery"]["overall"] != "passed":
                failed_ibs = [ib for ib, overall in out["ibs"].items() if overall != "passed"]
                if failed_ibs:
                    continue  # the per-IB phases now show the failure and dispatch its builder
                tail = (out["delivery"].get("integration") or {}).get("tail", "")
                target = _downstream(ctx, views, ctx.ibs)
                if target is None:
                    _block(ctx, "integration", "integration-failed",
                           f"the integration command fails after completion: {tail[-400:]}")
                    return _blocked(ctx, views)
                return _dispatch_builder(ctx, _ib(ctx, target.id), task="repair",
                                         reasons=[f"the delivery's integration command fails: {tail[-800:]}"])
            continue
        for intent in ctx.intents:
            ir = parse_intent(next((eng.repo_root / eng.spec_root / "intents").glob(f"{intent}-*.md")))
            if ir.get("status") == "COMPLETE" and (eng.current_completion(intent) or {}).get("fingerprint") == fp \
                    and _attestation_current(eng, intent):
                continue  # completed at exactly this content, under the current verifier policy
            if not _latest_passing(eng, intent, "intent", fp):
                # Also for a COMPLETE Intent whose content changed (a repair, a moved base): its outcome
                # is a claim about what lands, so it is verified again at what lands.
                ev = intent_verify(eng, intent, DRIVER)
                _verification(ctx, "intent", ev, artifact=intent)
                _commit(d.path, f"implement({d.slug}): outcome verification of {intent}")
                if ev["overall"] != "passed":
                    children = [c.ib_id for c in intent_children(eng, intent)]
                    failures = [f"{r['id']} {r['status']}: {r.get('detail', '')}" for r in ev["results"]
                                if r["status"] not in ("passed", "needs-review")]
                    why = f"{intent}'s outcome verification fails at the delivered content: " + "; ".join(failures)
                    target = _downstream(ctx, views, children)
                    if target is None:
                        last = next((ib for ib in reversed(ctx.ibs) if ib in children), None)
                        problem = _reopen_for_repair(ctx, last, why) if last else "it has no IB in this delivery"
                        if problem:
                            _block(ctx, f"outcome:{intent}", "outcome-failed", f"{why} — {problem}")
                            return _blocked(ctx, views)
                        _commit(d.path, f"implement({d.slug}): reopen {last} to repair {intent}'s outcome")
                        target = _ib(ctx, last)
                    return _dispatch_builder(ctx, _ib(ctx, target.id), task="repair", reasons=[why])
                continue
            gate = intent_evaluate(eng, intent)
            manual = next((ch for ch in gate.checks if ch.name == "manual-verification-attested" and not ch.ok), None)
            if manual is None:
                _clear(ctx, f"attest:{intent}")
            if manual is not None:
                st = fold(eng.record(intent).events(strict=False))
                quiet = ctx.view.blockers.get(f"attest:{intent}")
                if quiet and len(st.verdicts) > quiet.get("verdicts", 0):
                    _clear(ctx, f"attest:{intent}")
                if st.verdicts and st.verdicts[-1][1].get("verdict") == "fail" \
                        and st.verdicts[-1][1].get("fingerprint") == fp \
                        and not verdict_policy_problem(VERIFIER_ROLE, st.verdicts[-1][1]):
                    children = [c.ib_id for c in intent_children(eng, intent)]
                    why = f"{intent}'s manual verification failed: {st.verdicts[-1][1].get('notes', '')}"
                    target = _downstream(ctx, views, children)
                    if target is None:  # its IBs are complete: reopen the last one, as for an automated outcome
                        last = next((ib for ib in reversed(ctx.ibs) if ib in children), None)
                        problem = _reopen_for_repair(ctx, last, why) if last else "it has no IB in this delivery"
                        if problem:
                            _block(ctx, f"outcome:{intent}", "outcome-failed", f"{why} — {problem}")
                            return _blocked(ctx, views)
                        _commit(d.path, f"implement({d.slug}): reopen {last} to repair {intent}'s outcome")
                        target = _ib(ctx, last)
                    return _dispatch_builder(ctx, _ib(ctx, target.id), task="repair", reasons=[why])
                entries = [f"{v['name']} — {v.get('manual_rationale') or v.get('cmd') or 'no rationale given'}"
                           for v in ir.get("verification") or [] if v.get("manual")]
                latest = fold(eng.record(intent).events(strict=False)).latest_evidence("intent")
                results = [f"{r['id']} {r['status']}" for r in (latest[1].get("results") or [])] if latest else []
                intent_path = next((eng.repo_root / eng.spec_root / "intents").glob(f"{intent}-*.md"))
                silent = _silent(ctx, f"attest:{intent}", len(st.verdicts))
                if silent >= MAX_SILENT_REVIEWS:
                    _block(ctx, f"attest:{intent}", "review-not-recorded",
                           f"{intent}: {silent} attestations in a row returned without recording a verdict; a verifier "
                           "that cannot decide an entry must record FAIL naming it. Resolve it by recording an "
                           f"independent verdict (`dekspec intent review {intent} …`), then repeat the request",
                           verdicts=len(st.verdicts))
                    return _blocked(ctx, views)
                actor = f"reviewer-{intent}"
                role = _role("intent-reviewer")
                return _dispatch(ctx, "intent-reviewer", f"attest:{intent}", actor,
                                 prompts.intent_reviewer(d.path, intent, actor, ctx.view.auth, base_ref=ctx.base_ref,
                                                         entries=entries, role=role,
                                                         intent_path=str(intent_path.relative_to(eng.repo_root)),
                                                         results=results),
                                 agent_role=role, intent=intent, verdicts=len(st.verdicts))

        # -- reviews ---------------------------------------------------------------------
        for ib in ctx.ibs:
            v = views[ib]
            _reconcile_review_blocker(ctx, v)
            if v.phase != "review":
                continue
            verdicts = v.st.verdicts
            last = verdicts[-1][1] if verdicts else None
            if last and last.get("verdict") == "fail" and last.get("fingerprint") == fp \
                    and not verdict_policy_problem(CODE_REVIEWER_ROLE, last):
                repair = _repair_review(ctx, v)
                if repair is not None:
                    return repair
                continue
            silent = _silent_reviews(ctx, v)
            if silent >= MAX_SILENT_REVIEWS:
                _block(ctx, f"review:{ib}", "review-not-recorded",
                       f"{ib}: {silent} independent reviews in a row returned without recording a verdict; a reviewer "
                       "that cannot judge must record FAIL naming the missing evidence. Resolve it by recording an "
                       f"independent verdict (`dekspec ib review {ib} …`), then repeat the request",
                       verdicts=len(v.st.verdicts))
                continue
            return _dispatch_reviewer(ctx, v)
        if any(k.startswith("review:") for k in ctx.view.blockers):
            return _blocked(ctx, views)

        # -- a repair builder lost to a restart is reissued once -------------------------
        for ib in ctx.ibs:
            builds = [x for x in ctx.view.issued.values() if x.get("key") == f"build:{ib}"]
            last = builds[-1] if builds else None
            since_returned = []
            for x in builds:
                since_returned = [] if x["id"] in ctx.view.returned else since_returned + [x]
            lost = [x for x in since_returned if x["id"] in ctx.view.lost]
            if last and last["id"] in ctx.view.lost and len(lost) == 1 and not views[ib].st.completions \
                    and views[ib].phase in ("completable", "verified"):
                return _dispatch_builder(ctx, views[ib], task="resume", reasons=list(last.get("reasons") or []))

        # -- forge checks, while the work can still be repaired (github) ---------------
        if ctx.settings.method == "github" and pending and not (
                ctx.view.forge_passed and ctx.view.forge_passed.get("fingerprint") == fp):
            step = _forge_checks(ctx, views, fp)
            if step is not None:
                return step
            continue

        # -- completion ------------------------------------------------------------------
        for ib in ctx.ibs:
            if views[ib].phase == "completable" or (views[ib].phase == "verified" and all(
                    views[dep].phase == "complete" for dep in eng.contract(ib).depends_on if dep in views)):
                gate = eng.complete(ib, DRIVER, base=ctx.base_ref)
                _commit(d.path, f"implement({d.slug}): complete {ib}")
                if not gate.ok:
                    _block(ctx, f"complete:{ib}", "completion-refused",
                           "; ".join(f"{c.name}: {c.detail}" for c in gate.failures()))
                    return _blocked(ctx, views)
                progressed = True
                break
            current = eng.current_completion(ib) or {}
            latest_verdict = views[ib].st.verdicts[-1][0] if views[ib].st.verdicts else None
            if views[ib].phase == "complete" and not views[ib].failing and \
                    (current.get("fingerprint") != fp or current.get("verdict_seq") != latest_verdict):
                # Re-verified and re-reviewed at new content (a repair, a moved base): record the
                # completion at the content that lands, keeping the earlier one in the record.
                gate = eng.complete(ib, DRIVER, base=ctx.base_ref)
                _commit(d.path, f"implement({d.slug}): refresh {ib}'s completion at the delivered content")
                if not gate.ok:
                    _block(ctx, f"complete:{ib}", "completion-refused",
                           "; ".join(f"{c.name}: {c.detail}" for c in gate.failures()))
                    return _blocked(ctx, views)
                progressed = True
                break
        if progressed:
            continue
        for intent in ctx.intents:
            ir = parse_intent(next((eng.repo_root / eng.spec_root / "intents").glob(f"{intent}-*.md")))
            if ir.get("status") == "COMPLETE" and (eng.current_completion(intent) or {}).get("fingerprint") != fp:
                gate = intent_complete(eng, intent, DRIVER)  # refresh at the delivered content
                _commit(d.path, f"implement({d.slug}): refresh {intent}'s completion at the delivered content")
                if not gate.ok or (eng.current_completion(intent) or {}).get("fingerprint") != fp:
                    _block(ctx, f"complete:{intent}", "completion-refused",
                           "; ".join(f"{c.name}: {c.detail}" for c in gate.failures()) or "refresh not recorded")
                    return _blocked(ctx, views)
                progressed = True
                break
            if ir.get("status") == "ACCEPTED":
                gate = intent_complete(eng, intent, DRIVER)
                _commit(d.path, f"implement({d.slug}): complete {intent}")
                if not gate.ok:
                    _block(ctx, f"complete:{intent}", "completion-refused",
                           "; ".join(f"{c.name}: {c.detail}" for c in gate.failures()))
                    return _blocked(ctx, views)
                progressed = True
                break
        if progressed:
            continue

        # -- land ------------------------------------------------------------------------
        fp = eng.fingerprint()
        if not _landing_current(ctx.view, fp, base_commit):
            _commit(d.path, f"implement({d.slug}): checkpoint")
            # Re-executes acceptance and the integration command except where the driver's own
            # passing delivery verification stands at the identical binding (ADR-059 stage 6);
            # CI's command-line `delivery check --rerun` always re-executes (ADR-058).
            check = delivery_check(Engine(d.path, base=ctx.base_ref), base=ctx.base_ref, rerun=True,
                                   reuse_actor=DRIVER)
            if not check.ok:
                failing = [f"{c.name}: {c.detail}" for c in check.checks if not c.ok] + \
                          [f"{g.ib}/{c.name}: {c.detail}" for g in check.gates for c in g.failures()]
                if any("branch-current-with-base" in f for f in failing):
                    continue
                _block(ctx, "landing", "landing-gate", "; ".join(failing)[:1500])
                return _blocked(ctx, views)
            _clear(ctx, "landing")
            eng.record(d.run_id).append("landing.verified", DRIVER, {
                "fingerprint": fp, "commit": _git(d.path, "rev-parse", "HEAD").stdout.strip(),
                "base_commit": base_commit, "ibs": ctx.ibs, "intents": ctx.intents,
                # O-4: what the gate relied on instead of executing, and what it executed.
                "relies_on": check.relied_on, "executed": check.executed})
            _commit(d.path, f"implement({d.slug}): landing gate passed")
            continue
        landed, why = _landed(eng, ctx.view, ctx.ibs, ctx.intents, ctx.base_ref)
        if not landed:
            _block(ctx, "landing", "landing-gate", why)
            return _blocked(ctx, views)
        if _checks_exhausted_here(ctx, fp):
            return _blocked(ctx, views)
        result = integ.integrate(d.path, d.base, ctx.settings, title=f"implement: {', '.join(d.targets)}",
                                 body=_pr_body(ctx))
        if result.state == "merged":
            _clear(ctx, "integration")
            return _finish(ctx, result)
        if result.state == "push-pending":
            _block(ctx, "push", "push-failed", result.detail)
            return _action("blocked", d, result=_result(ctx, "push-pending", result, result.detail))
        if result.state == "behind":
            continue
        if result.state == "wait":
            return _action("wait", d, seconds=60, reason=result.detail)
        if result.state == "failed":
            return _repair_landing_failure(ctx, views, result)
        _block(ctx, "integration", "checks-requirement-unreadable"
               if result.detail.startswith("checks-requirement-unreadable:") else "integration-blocked", result.detail)
        return _blocked(ctx, views)
    raise DriverError(f"no stable next step after {MAX_STEPS} mechanical steps in {d.path}")



def _advance_lean(ctx: _Ctx, ib: str) -> dict[str, Any] | None:
    """Execute one derived action; the lean module owns order and recovery choice."""
    eng, d = ctx.engine, ctx.d
    state = eng.state(ib)[2]
    if not state.started and not state.completions:
        try:
            _start(ctx, ib)
        except (Blocked, ExecutionError) as exc:
            _block(ctx, f"lean:{ib}", "cannot-start", str(exc))
            return _blocked(ctx, {})
        _commit(d.path, f"implement({d.slug}): start {ib}")
    # A resolver owns its partial work until acknowledged, even if it has
    # already concluded the merge. Reissue from the durable dispatch on restart.
    events = eng.record(d.run_id).events()
    departure = next((e for e in reversed(events)
                      if e.type == "queue.left" and e.data.get("brief") == ib), None)
    if departure and departure.data.get("reason") == "conflict":
        resolver = next((e for e in reversed(events) if e.type == "dispatch.issued"
                         and e.data.get("role") == "resolver" and e.seq > departure.seq), None)
        returned = {e.data["id"] for e in events if e.type == "dispatch.returned"}
        conflicted = _git(d.path, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        if conflicted or (resolver and resolver.data["id"] not in returned):
            role = _role("resolver")
            files = conflicted or resolver.data.get("files", [])
            actor = f"resolver-{d.slug}"
            return _dispatch(ctx, "resolver", "resolve:base", actor,
                             prompts.resolver(d.path, actor, ctx.view.auth, base_ref=ctx.base_ref,
                                              files=files, role=role), agent_role=role, files=files)
    step = lean.next_step(eng, d.run_id, ib, base_ref=ctx.base_ref)
    if step.operation != "stop":
        _clear(ctx, f"lean:{ib}")
    # A provider refusal is returned intact to the decision module. No driver
    # event encodes a verdict or a second interpretation of a completion gate.
    if step.operation == "record-tests":
        try:
            spec.record_tests_authored(eng, ib, commit=step.commit, author=step.author,
                                       actor=DRIVER, skeletons=list(step.skeletons))
        except ExecutionError as exc:
            step = lean.next_step(eng, d.run_id, ib, base_ref=ctx.base_ref, record_error=exc)
        else:
            _commit(d.path, f"implement({d.slug}): record authored tests for {ib}")
            return None
    if step.operation == "complete":
        try:
            result = eng.complete(ib, DRIVER, base=ctx.base_ref)
        except ExecutionError as exc:
            step = lean.next_step(eng, d.run_id, ib, base_ref=ctx.base_ref, record_error=exc)
        else:
            if result.ok:
                _commit(d.path, f"implement({d.slug}): complete {ib}")
                return None
            step = lean.next_step(eng, d.run_id, ib, base_ref=ctx.base_ref,
                                  record_error=ExecutionError(result))
    if step.operation == "stop":
        if step.kind == "review-not-converging" and not state.blockers:
            eng.block(ib, DRIVER, "other", "review-not-converging: " + step.detail)
        _block(ctx, f"lean:{ib}", step.kind, step.detail)
        return _blocked(ctx, {})
    if step.operation == "land":
        return _lean_landing(ctx)
    if step.operation == "reset":
        if state.open_attempt:
            eng.attempt_end(ib, f"builder-{ib}", outcome="abandoned", summary="return to the test author")
        restored = _git(d.path, "restore", "--source", step.commit, "--staged", "--worktree", "--", ".",
                        ":(exclude).dekspec/execution", ":(exclude).dekbuilder")
        if restored.returncode:
            _block(ctx, f"lean:{ib}", "interface-not-returned", (restored.stderr or restored.stdout).strip())
            return _blocked(ctx, {})
        _commit(d.path, f"implement({d.slug}): restore test-author content for {ib}")
        return None
    if step.operation == "verify":
        result = eng.verify(ib, DRIVER, base=ctx.base_ref)
        _verification(ctx, "ib", result, artifact=ib)
        _commit(d.path, f"implement({d.slug}): own verification of {ib}")
        return None
    if step.operation != "dispatch":
        raise DriverError(f"unknown lean operation: {step.operation}")
    if step.strategy_reason:
        if not _change_strategy(ctx, _IB(ib, "build", st=state), step.strategy_reason):
            _block(ctx, f"lean:{ib}", step.kind,
                   f"{ib} exhausted {MAX_STRATEGIES} strategy changes: {step.strategy_reason}")
            return _blocked(ctx, {})
        state = eng.state(ib)[2]
    actor = f"{step.worker}-{ib}"
    role = _role(step.worker)
    packet = eng.context(ib).render_markdown()
    common = dict(base_ref=ctx.base_ref, role=role,
                  **prompts._loop_arguments(step.floor_loop if step.worker in ("test-author", "floor-reviewer")
                                            else step.code_loop,
                                            step.floor_loop if step.worker in ("builder", "reviewer") else None))
    if step.worker in ("test-author", "floor-reviewer"):
        common["_test_runners"] = tuple(dict.fromkeys(
            condition.kind for condition in eng.contract(ib).acceptance if condition.nodes))
    info = {"ib": ib}
    if step.worker == "test-author":
        author_facts = step.findings
        if step.task == "repair" and step.commit:
            author_facts = (f"Current test-author commit to repair: {step.commit}", *author_facts)
        prompt = prompts.test_author(d.path, ib, actor, ctx.view.auth, packet, **common,
                                     findings=author_facts, interface_problem=step.interface_problem)
        key = f"author:{ib}"
        info.update(task=step.task, commit=step.commit, findings=list(step.findings),
                    interface_problem=step.interface_problem)
    elif step.worker == "floor-reviewer":
        prompt = prompts.floor_reviewer(d.path, ib, actor, ctx.view.auth, packet, **common,
                                        commit=step.commit, skeletons=step.skeletons)
        key = f"floor:{ib}"
        info.update(commit=step.commit)
    elif step.worker == "builder":
        prompt = prompts.builder(d.path, ib, actor, ctx.view.auth, packet, **common,
                                 task=step.task, reasons=list(step.findings), strategy=ctx.view.last_strategy.get(ib),
                                 open_attempt=state.open_attempt.number if state.open_attempt else None,
                                 own_nodes=step.own_nodes, skeletons=step.skeletons)
        key = f"build:{ib}"
        info.update(task=step.task, reasons=list(step.findings))
    else:
        latest = state.latest_evidence("ib")
        attention = sorted(latest[1].get("attention", [])) if latest else []
        prompt = prompts.reviewer(d.path, ib, actor, ctx.view.auth, packet, **common,
                                  attention=attention, previous=None,
                                  facts=prompts.review_facts(latest[1] if latest else None, state.deviations),
                                  own_gates=_changes_gates(ctx), own_nodes=step.own_nodes, skeletons=step.skeletons)
        key = f"review:{ib}"
        info.update(attention=attention, verdicts=step.verdicts)
    return _dispatch(ctx, step.worker, key, actor, prompt, agent_role=role, **info)


def _lean_landing(ctx: _Ctx) -> dict[str, Any]:
    """Land a completed lean brief against its durable candidate and forge evidence."""
    import fcntl

    from dekbuilder.implement import landing_queue

    d, eng = ctx.d, ctx.engine
    ib = ctx.ibs[0]
    line = landing_queue.LandingQueue(d.path, d.base)

    def stop(kind, detail):
        _block(ctx, "integration", kind, detail)
        # Candidate records must not move a published branch while it is waiting.
        return _action("blocked", d, result=_result(ctx, "blocked", detail=detail))

    def wait(detail):
        return _action("wait", d, seconds=60, reason=detail)

    def repair(reason, detail, *, failures=None, pr=None, head=None):
        line.leave(ib, reason=reason)
        exhausted = False
        if failures is not None:
            exhausted = _record_check_failure(ctx, head, eng.fingerprint(), pr, detail,
                                               failures, stage="candidate")
        problem = _reopen_for_repair(ctx, ib, detail)
        if problem:
            if exhausted:
                return _action("blocked", d, result=_result(ctx, "blocked", detail=detail))
            return stop("cannot-reopen", problem)
        _commit(d.path, f"implement({d.slug}): reopen for {reason}")
        if exhausted:
            # The lean construction decision also needs the durable stop after reopening.
            eng.block(ib, DRIVER, "other", f"checks-not-converging: {detail}")
            return _blocked(ctx, {})
        if reason in ("conflict", "base-touched"):
            merged = _git(d.path, "merge", "--no-edit", "-q", ctx.base_ref)
            conflicted = _git(d.path, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
            if conflicted:
                role = _role("resolver")
                return _dispatch(ctx, "resolver", "resolve:base", f"resolver-{d.slug}",
                                 prompts.resolver(d.path, f"resolver-{d.slug}", ctx.view.auth,
                                                  base_ref=ctx.base_ref, files=conflicted, role=role),
                                 agent_role=role, files=conflicted)
            if merged.returncode:
                return stop("integration-failed", (merged.stderr or merged.stdout).strip())
        history = spec.lean_state(eng, ib)
        state = eng.state(ib)[2]
        nodes = spec.own_tests(eng, ib)
        actor, role = f"builder-{ib}", _role("builder")
        prompt = prompts.builder(
            d.path, ib, actor, ctx.view.auth, eng.context(ib).render_markdown(),
            base_ref=ctx.base_ref, task="repair", reasons=[detail], role=role,
            strategy=ctx.view.last_strategy.get(ib),
            open_attempt=state.open_attempt.number if state.open_attempt else None,
            own_nodes=nodes, skeletons=history.skeletons)
        return _dispatch(ctx, "builder", f"build:{ib}", actor, prompt,
                         agent_role=role, ib=ib, task="repair", reasons=[detail])

    def checks(pr, head):
        result = integ._lean_checks(d.path, pr, head)
        state, _, detail = result
        if state == "passed" and not any(
                e.type == "forge.checks-passed" and e.data.get("commit") == head
                for e in eng.record(d.run_id).events()):
            eng.record(d.run_id).append("forge.checks-passed", DRIVER, {
                "fingerprint": eng.fingerprint(), "commit": head,
                "pr": pr["number"], "detail": detail})
        return result

    def reconcile(pr, head, tested_base):
        revision = integ._tested_merge(d.path, pr)
        if not revision or not tested_base:
            return stop("integration-blocked", "merged candidate has no known revision or tested base")
        fetched = _git(d.path, "fetch", "-q", ctx.settings.remote, d.base)
        if fetched.returncode:
            return stop("base-unavailable", fetched.stderr.strip())
        parents = _git(d.path, "show", "-s", "--format=%P", revision).stdout.split()
        if not parents or parents[0] != tested_base:
            data = {"brief": ib, "head": head, "tested_base": tested_base,
                    "revision": revision, "first_parent": parents[0] if parents else None}
            if not any(e.type == "landing.base-raced" and e.data.get("revision") == revision
                       for e in eng.record(d.run_id).events()):
                eng.record(d.run_id).append("landing.base-raced", DRIVER, data)
            return stop("integration-failed", "landing.base-raced: merge first parent differs from tested base")
        expected = _git(d.path, "merge-tree", "--write-tree", tested_base, head)
        tree = expected.stdout.splitlines()[0] if expected.stdout else None
        actual = integ.tree_of(d.path, revision)
        if expected.returncode or not tree or actual != tree or head not in parents[1:]:
            return stop("integration-failed", "integrated content differs from the tested candidate")
        observed = integ.Integration("merged", f"pull request #{pr['number']} merged",
                                     revision, actual, pr)
        line.leave(ib, reason="landed")
        if ctx.view.done is None:
            eng.record(d.run_id).append("run.integrated", DRIVER, {
                "revision": revision, "tree": actual, "verified_tree": tree,
                "landing": None, "content_identical": True, "integrated_verified": True,
                "problems": [], "method": ctx.settings.method, "detail": observed.detail,
                "pr": pr, "recheck": None})
            ctx.view = _view(eng, d.run_id)
        return _action("done", d, result=_result(ctx, "complete", observed))

    def advance():
        ctx.view = _view(eng, d.run_id)
        if (_checks_exhausted_here(ctx, eng.fingerprint())
                or ctx.view.blockers.get("integration", {}).get("kind") == "cannot-reopen"):
            return _action("blocked", d, result=_result(ctx, "blocked"))
        admission = line.join(d.path, ib)
        _clear(ctx, "integration")
        head = _git(d.path, "rev-parse", "HEAD").stdout.strip()
        if not admission.at_head and admission.state != "candidate":
            return wait(f"{ib} is waiting in the landing line")
        pr = integ._find_pr(d.path, d.base, ctx.settings)
        if pr and pr.get("state") == "MERGED" and pr.get("headRefOid") == head:
            state, _, detail = checks(pr, head)
            if state == "pending":
                return wait(detail)
            if state != "passed":
                return stop("integration-failed", f"merged candidate lacks passing checks: {detail}")
            return reconcile(pr, head, admission.tested_base)
        if not admission.at_head:
            return wait(f"{ib} is waiting in the landing line")
        fetched = _git(d.path, "fetch", "-q", ctx.settings.remote, d.base)
        if fetched.returncode:
            return stop("base-unavailable", fetched.stderr.strip())
        remote_base = _git(d.path, "rev-parse", ctx.base_ref).stdout.strip()
        old = _git(d.path, "merge-base", head, remote_base).stdout.strip()
        probe = _git(d.path, "merge-tree", "--write-tree", remote_base, head)
        if probe.returncode == 1:
            return repair("conflict", f"{ib}: candidate conflicts with {d.base}")
        if probe.returncode:
            return stop("integration-blocked", (probe.stderr or probe.stdout).strip())
        try:
            touched = spec.base_move_touches(eng, ib, old, remote_base)
        except (ExecutionError, AttributeError) as exc:
            return stop("integration-blocked", str(exc))
        if touched:
            return repair("base-touched", "base-touched: " + ", ".join(touched))

        remote = _git(d.path, "ls-remote", ctx.settings.remote, f"refs/heads/{d.branch}")
        if remote.returncode:
            return stop("integration-blocked", remote.stderr.strip())
        pushed_head = remote.stdout.split()[0] if remote.stdout.strip() else None
        known = admission.head == head and admission.tested_base is not None
        moved = known and admission.tested_base != remote_base
        if moved or (not known and pushed_head == head):
            # A pushed head without its own binding cannot reuse old green checks.
            # A harmless base move preserves evidence and place, but gets a new head.
            _commit(d.path, f"implement({d.slug}): checkpoint previous candidate")
            if moved:
                merged = _git(d.path, "merge", "--no-edit", "-q", ctx.base_ref)
                if merged.returncode:
                    return stop("integration-failed", (merged.stderr or merged.stdout).strip())
            if _git(d.path, "rev-parse", "HEAD").stdout.strip() == head:
                renewed = _git(d.path, "commit", "--allow-empty", "-q", "-m",
                               f"implement({d.slug}): renew candidate")
                if renewed.returncode:
                    return stop("setup-failed", renewed.stderr.strip())
            head = _git(d.path, "rev-parse", "HEAD").stdout.strip()
            known = False
        if not known:
            admission = line.candidate(ib, head=head, pr=pr, tested_base=remote_base)
        # The binding is durable before this first external mutation. A restart
        # observes the remote head rather than repeating a successful push.
        if pushed_head != head:
            prepared, pr = integ.prepare_pr(d.path, d.base, ctx.settings,
                                            title=f"implement: {ib}",
                                            body=f"Completed lean brief {ib}; candidate CI judges the merged result.")
            if pr is None:
                return stop("integration-blocked", prepared.detail)
            line.candidate(ib, head=head, pr=pr, tested_base=admission.tested_base)
            return wait(f"candidate for {ib} pushed; waiting for checks")
        if pr is None:
            created = integ._gh(d.path, "pr", "create", "--base", d.base, "--head", d.branch,
                                 "--title", f"implement: {ib}",
                                 "--body", f"Completed lean brief {ib}; candidate CI judges the merged result.")
            if created.returncode:
                return stop("integration-blocked", (created.stderr or created.stdout).strip())
            pr = integ._find_pr(d.path, d.base, ctx.settings)
        if pr is None:
            return stop("integration-blocked", "candidate pull request cannot be read")
        if pr.get("headRefOid") != head:
            return wait("waiting for the forge to report the candidate head")
        state, failures, detail = checks(pr, head)
        if state == "pending":
            return wait(detail)
        if state == "unavailable":
            kind = "checks-requirement-unreadable" if detail.startswith("checks-requirement-unreadable:") else "integration-blocked"
            return stop(kind, detail)
        if state == "failed":
            return repair("candidate-failed", detail, failures=failures, pr=pr, head=head)
        # Checks can take time to read. Observe the remote tip again at the
        # merge boundary, retaining the forge's independent head-match guard.
        latest = _git(d.path, "ls-remote", ctx.settings.remote, f"refs/heads/{d.base}")
        if latest.returncode or not latest.stdout.strip():
            return stop("base-unavailable", "cannot read the remote base before merge")
        if latest.stdout.split()[0] != admission.tested_base:
            return wait("base moved during the check read; a new candidate is needed")
        merged = integ._gh(d.path, "pr", "merge", str(pr["number"]), "--merge",
                            "--match-head-commit", head)
        if merged.returncode:
            return stop("integration-blocked", (merged.stderr or merged.stdout).strip())
        return reconcile(pr, head, admission.tested_base)

    # Serialize competing sessions of this delivery, separately from the queue
    # lock. Queue mutations release their own lock before any forge call.
    common = _git(d.path, "rev-parse", "--git-common-dir").stdout.strip()
    lock_path = (d.path / common).resolve() / "dekbuilder" / f"delivery-{d.slug}.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return advance()
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    except OSError as exc:
        return stop("setup-failed", str(exc))


def _push(ctx: _Ctx) -> dict[str, Any] | None:
    """Discharge an outstanding push of the integrated base (never forced).
    ``None`` once the remote holds it; otherwise the blocked result."""
    pushed = integ.push_base(ctx.d.path, ctx.d.base, ctx.settings)
    if pushed.state == "merged":
        _clear(ctx, "push")
        return None
    _block(ctx, "push", "push-failed", pushed.detail)
    return _action("blocked", ctx.d, result=_result(ctx, "push-pending", pushed, pushed.detail))


def _forge_checks(ctx: _Ctx, views: dict[str, _IB], fp: str) -> dict[str, Any] | None:
    """Run the pull request's required checks on the reviewed head before any
    IB completes. A readable failure is a recovery event: a builder repairs it
    with the checks' evidence, and verification, review and these checks run
    again on the repaired head. ``None`` means the checks passed (recorded)."""
    d, eng = ctx.d, ctx.engine
    if _checks_exhausted_here(ctx, fp):
        return _blocked(ctx, views)
    _commit(d.path, f"implement({d.slug}): checkpoint for the required checks")
    prepared, pr = integ.prepare_pr(d.path, d.base, ctx.settings, title=f"implement: {', '.join(d.targets)}",
                                    body=_pr_body(ctx))
    if pr is None:
        _block(ctx, "forge", "integration-blocked", prepared.detail)
        return _blocked(ctx, views)
    head = _git(d.path, "rev-parse", "HEAD").stdout.strip()
    if pr.get("headRefOid") and pr["headRefOid"] != head:
        return _action("wait", d, seconds=30, reason=f"pull request #{pr['number']} does not show {head[:12]} yet")
    state, failures, detail = integ.required_checks(d.path, pr)
    if state == "pending":
        return _action("wait", d, seconds=60, reason=detail)
    if state == "unavailable":
        _block(ctx, "forge", "checks-requirement-unreadable"
               if detail.startswith("checks-requirement-unreadable:") else "integration-blocked", detail)
        return _blocked(ctx, views)
    _clear(ctx, "forge")
    if state == "passed":
        eng.record(d.run_id).append("forge.checks-passed", DRIVER,
                                    {"fingerprint": fp, "commit": head, "pr": pr.get("number"), "detail": detail})
        _commit(d.path, f"implement({d.slug}): required checks passed")
        return None
    if _record_check_failure(ctx, head, fp, pr, detail, failures, stage="reviewed-head"):
        return _blocked(ctx, views)
    target = _downstream(ctx, views, ctx.ibs)
    if target is None:
        _block(ctx, "forge", "required-checks-failed", detail)
        return _blocked(ctx, views)
    return _dispatch_builder(ctx, _ib(ctx, target.id), task="repair", reasons=[
        f"the pull request's required checks fail on {head[:12]} (the delivery's reviewed head): {detail}"])


def _checks_exhausted_here(ctx: _Ctx, fp: str) -> bool:
    """A `checks-not-converging` blocker stands while the content it was
    recorded at is unchanged: repeating the request must not push another
    bookkeeping head just to watch the same checks fail again."""
    blocker = ctx.view.blockers.get("forge")
    return bool(blocker and blocker.get("kind") in ("checks-not-converging", "required-checks-failed")
                and blocker.get("fingerprint") == fp)


def _record_check_failure(ctx: _Ctx, head: str, fp: str, pr: dict[str, Any] | None, detail: str,
                          failures: list[dict[str, Any]], *, stage: str) -> bool:
    """Record a failing required-check result once per head. True when the
    bounded recovery is spent (the blocker is recorded)."""
    if not any(f.get("commit") == head for f in ctx.view.forge_failures):
        ctx.engine.record(ctx.d.run_id).append("forge.checks-failed", DRIVER, {
            "fingerprint": fp, "commit": head, "pr": (pr or {}).get("number"), "detail": detail,
            "failures": failures, "stage": stage})
        ctx.view.forge_failures.append({"commit": head, "fingerprint": fp})
    if len(ctx.view.forge_failures) >= MAX_FORGE_FAILURES:
        _block(ctx, "forge", "checks-not-converging",
               f"the required checks failed {len(ctx.view.forge_failures)} times; last: {detail}", fingerprint=fp)
        return True
    return False


def _reopen_for_repair(ctx: _Ctx, ib: str, reason: str) -> str | None:
    """Reopen ``ib`` (when complete) and every completed target Intent so a
    builder can repair them — all or nothing: nothing changes unless every
    completion can be reopened (none integrated in the base, within the
    bound). Returns why not, or ``None`` once reopened."""
    eng = ctx.engine
    reopen: list[tuple[str, str, str]] = []
    if eng.is_complete(ib, base=ctx.base_ref):
        reopen.append(("ib", ib, eng.contract(ib).rel_path))
    for intent in ctx.intents:
        path = _intent_path(eng, intent)
        if path and parse_intent(path).get("status") == "COMPLETE" and eng.current_completion(intent) is not None:
            reopen.append(("intent", intent, str(path.relative_to(eng.repo_root))))
    for _kind, ident, rel in reopen:
        state, why = eng.integration_state(ident, rel, ctx.base_ref)
        if state == "unknown":
            return f"cannot tell whether {ident}'s completion is already integrated in {ctx.d.base}: {why}"
        if state == "integrated":
            return f"{ident}'s completion is already integrated in {ctx.d.base}"
    used = len(fold(eng.record(ib).events(strict=False)).reopenings)
    if used >= MAX_REOPENS:
        return f"{ib} was already reopened {used} times without converging"
    try:
        for kind, ident, _rel in reopen:
            if kind == "ib":
                eng.reopen(ident, DRIVER, reason[:900], base=ctx.base_ref)
            else:
                intent_reopen(eng, ident, DRIVER, reason[:900], base=ctx.base_ref)
    except ExecutionError as exc:
        return str(exc)
    return None


def _repair_landing_failure(ctx: _Ctx, views: dict[str, _IB], result: integ.Integration) -> dict[str, Any]:
    """The required checks failed on the head that carries the completion and
    landing records. A passing check earlier proves nothing about this one, so
    the failure is a recovery event like any other: the downstream IB and the
    target Intents are reopened (their completions stay in the records), a
    builder repairs with the failing checks as evidence, and verification,
    applicable review, the checks and completion run again before the single
    merge. The same bound applies; a completion that cannot be reopened is
    reported."""
    d, eng = ctx.d, ctx.engine
    head = _git(d.path, "rev-parse", "HEAD").stdout.strip()
    fp = eng.fingerprint()
    failures = (result.pr or {}).get("failures", [])
    if _record_check_failure(ctx, head, fp, result.pr, result.detail, failures, stage="landing-head"):
        return _blocked(ctx, views)
    target = ctx.ibs[-1]
    reason = f"required checks failed on the landing head {head[:12]}: {result.detail}"[:900]
    problem = _reopen_for_repair(ctx, target, reason)
    if problem:
        _block(ctx, "forge", "required-checks-failed", f"{result.detail} — cannot reopen for repair: {problem}",
               fingerprint=fp)
        return _blocked(ctx, views)
    _commit(d.path, f"implement({d.slug}): reopen {target} to repair the failing required checks")
    return _dispatch_builder(ctx, _ib(ctx, target), task="repair", reasons=[
        f"the pull request's required checks fail on the landing head {head[:12]}: {result.detail}"])


def _pr_body(ctx: _Ctx) -> str:
    return (f"Implementation Run {ctx.d.run_id} — `/implement {ctx.view.auth.get('request', '')}` "
            f"requested by {ctx.view.auth.get('requested_by', '?')} (ADR-059).\n\n"
            f"Targets: {', '.join(ctx.d.targets)}. IBs: {', '.join(ctx.ibs)}.\n"
            "Each IB passed its acceptance conditions, an independent review and `dekspec ib complete`; "
            "`dekspec delivery check --rerun` passed at this head.")


def _verify_integrated(ctx: _Ctx, revision: str) -> tuple[bool, list[str]]:
    """Re-run every IB's acceptance and the integration command on the
    integrated revision itself, in a scratch worktree (nothing is recorded)."""
    import tempfile


    with tempfile.TemporaryDirectory(prefix="dekspec-integrated-") as tmp:
        path = Path(tmp) / "integrated"
        if _git(ctx.d.path, "worktree", "add", "-q", "--detach", str(path), revision).returncode != 0:
            return False, [f"cannot check out {revision[:12]}"]
        try:
            environment = checkout_environment(path)
            command = ctx.settings.worktree_setup
            if command:
                setup = subprocess.run(command, shell=True, cwd=environment.cwd, env=environment.env,
                                       capture_output=True, text=True)
                if setup.returncode:
                    _block(ctx, "recheck", "setup-failed",
                           f"{path}: setup `{command}` failed: {(setup.stderr or setup.stdout)[-1500:]}")
                    return False, [f"{path}: setup `{command}` failed"]
            environment = checkout_environment(path, configured_python=SpecEngine(path).settings.python)
            try:
                result = run_operation(environment, {"verb": "recheck", "root": str(ctx.root),
                                       "delivery": {**ctx.d.as_dict(), "worktree": str(path)},
                                       "base_ref": ctx.base_ref, "ibs": ctx.ibs, "intents": ctx.intents})
            except EnvironmentUnavailable as exc:
                _block(ctx, "recheck", exc.kind, str(exc), environment=environment.as_dict())
                return False, [str(exc)]
            ctx.engine.record(ctx.d.run_id).append("integration.rechecked", DRIVER, result)
            return result["ok"], result["problems"]
        finally:
            _git(ctx.d.path, "worktree", "remove", "--force", str(path))


def _recheck(path: Path, base_ref: str, ibs: list[str], intents: list[str]) -> dict:
    eng = Engine(path, base=base_ref)
    problems = []
    for ib in ibs:
        ev = eng.verify(ib, DRIVER, base=base_ref, record=False)
        if ev["overall"] != "passed":
            problems.append(f"{ib}: " + "; ".join(delivery_failure_reasons(ev)))
    ran = verify_integration(eng)
    if ran and ran["status"] != "passed":
        problems.append(f"integration command: exit {ran['exit_code']}")
    for intent in intents:
        ev = intent_verify(eng, intent, DRIVER, record=False)
        if ev["overall"] != "passed":
            problems.append(f"{intent} outcome: " + "; ".join(
                f"{r['id']} {r['status']}" for r in ev["results"] if r["status"] not in ("passed", "needs-review")))
    return {"ok": not problems, "problems": problems, **_provenance.get()}


def _finish(ctx: _Ctx, observed: integ.Integration) -> dict[str, Any]:
    """Reconcile an integrated delivery, once. Callers establish `_landed` first:
    the head's content is the content that passed the landing gate, so its tree
    is a verified tree. An integrated revision with any other content is
    re-verified on that revision itself."""
    d, eng = ctx.d, ctx.engine
    problems: list[str] = []
    if ctx.view.done is None:
        head_tree = integ.tree_of(d.path, "HEAD")
        same = observed.tree == head_tree
        if not same and observed.revision:
            same_behaviour, problems = _verify_integrated(ctx, observed.revision)
        else:
            same_behaviour = same
        eng.record(d.run_id).append("run.integrated", DRIVER, {
            "revision": observed.revision, "tree": observed.tree, "verified_tree": head_tree,
            "landing": (ctx.view.landing or {}).get("fingerprint"),
            "content_identical": same, "integrated_verified": same_behaviour, "problems": problems,
            "method": ctx.settings.method, "detail": observed.detail, "pr": observed.pr,
            "recheck": next((e.data for e in reversed(eng.record(d.run_id).events())
                             if e.type == "integration.rechecked"), None) if not same else None})
        ctx.view = _view(eng, d.run_id)
    verified = bool(ctx.view.done and ctx.view.done.get("integrated_verified"))
    outcome = "complete" if verified else "integrated-unverified"
    detail = None if verified else ("the integrated revision fails verification: "
                                    + "; ".join(ctx.view.done.get("problems", []) if ctx.view.done else problems))
    return _action("done" if verified else "blocked", d, result=_result(ctx, outcome, observed, detail))


def _result(ctx: _Ctx, outcome: str, observed: integ.Integration | None = None, detail: str | None = None) -> dict:
    eng = ctx.engine
    ibs = {}
    for ib in ctx.ibs:
        try:
            c = eng.contract(ib)
            _r, _e, st = eng.state(c.ib_id)
            ibs[ib] = {"status": c.status, "completion": st.completions[-1][0] if st.completions else None}
        except ExecutionError as exc:
            ibs[ib] = {"status": "unreadable", "detail": str(exc)}
    targets = {}
    for t in ctx.d.targets:
        if t.startswith("INT-"):
            path = _intent_path(eng, t)
            status = parse_intent(path).get("status") if path else "missing"
        else:
            status = ibs.get(t, {}).get("status")
        targets[t] = status
    return {**_provenance.get(), "recheck": (ctx.view.done or {}).get("recheck"), "outcome": outcome, "detail": detail, "targets": targets, "ibs": ibs,
            "integration": observed.as_dict() if observed else None,
            "blockers": list(ctx.view.blockers.values()), "delivery": ctx.d.as_dict()}


def _blocked(ctx: _Ctx, views: dict[str, _IB]) -> dict[str, Any]:
    waiting = {ib: v.detail for ib, v in views.items() if v.phase == "waiting"}
    result = _result(ctx, "blocked")
    result["waiting"] = waiting
    _commit(ctx.d.path, f"implement({ctx.d.slug}): blocked")
    return _action("blocked", ctx.d, result=result)


# ------------------------------------------------------------------ entry points
def _plan(root: Path, request: str, *, strict: bool = False) -> tuple[Any, Any, list[Delivery], IntegrationSettings]:
    require_spec()
    resolution = resolve(root, request)
    settings = load_integration(root)
    if not resolution.targets or resolution.problems:
        return resolution, None, [], settings
    readiness = assess(root, resolution.targets, check_environment=False)
    base = settings.base or readiness.base or _default_base(root)
    deliveries = [_delivery(root, group, base) for group in readiness.groups]
    # A target already complete here but delivered by an earlier run keeps its
    # delivery in the report (with its integrated revision).
    grouped = {t for g in readiness.groups for t in g}
    for t in readiness.targets:
        # A target whose only gap is a stale completion (ADR-061) resumes its earlier
        # delivery, where the driver re-reviews it; without one it stays not-ready.
        stale_only = t.outcome == "not-ready" and t.missing and all(
            m.code == "completion-not-current" for m in t.missing)
        if (t.outcome == "complete" or stale_only) and t.id not in grouped:
            d = _delivery(root, [t.id], base)
            if d.exists and (strict or d.path.exists()):
                deliveries.append(d)
    return resolution, readiness, deliveries, settings


def _default_base(root: Path) -> str:
    for b in ("main", "master"):
        if _git(root, "rev-parse", "-q", "--verify", f"refs/heads/{b}").returncode == 0:
            return b
    return "main"


def _ctx(root: Path, d: Delivery, readiness: Any, settings: IntegrationSettings) -> _Ctx:
    base_ref = integ.base_ref(d.path, d.base, settings)
    engine = Engine(d.path, base=base_ref)
    view = _view(engine, d.run_id)
    ibs = view.auth.get("ibs") or [ib for ib in readiness.order if any(
        ib in t.ibs for t in readiness.targets if t.id in d.targets)]
    return _Ctx(root, d, engine, settings, base_ref, ibs,
                [t for t in d.targets if t.startswith("INT-")], view)


def next_step(root: Path, request: str, *, actor: str) -> dict[str, Any]:
    """Take every mechanical step available and return the next action."""
    root = Path(root)
    resolution, readiness, deliveries, settings = _plan(root, request)
    if readiness is None:
        return _action("not-ready", None, resolution=resolution.as_dict())
    complete = [t for t in readiness.targets if t.outcome == "complete"]
    started = [d for d in deliveries if d.exists]
    if not started:
        entry = assess(root, resolution.targets, check_environment=True)
        if not entry.ready:
            if complete and len(complete) == len(readiness.targets):
                return _action("done", None, result={"outcome": "complete", "detail": "already complete — nothing "
                                                     "to implement", "targets": {t.id: t.status for t in complete}})
            return _action("not-ready", None, readiness=entry.as_dict())
        readiness = entry
    results: list[dict[str, Any]] = []
    for d in deliveries:
        if not d.exists or not d.path.exists():
            ibs = [ib for ib in readiness.order if any(ib in t.ibs for t in readiness.targets if t.id in d.targets)]
            _prepare(root, d, request, actor, ibs, settings)
            d.exists = True
        step = _delivery_operation(root, d, "advance")
        if step["action"] in ("dispatch", "wait"):
            step["advisories"] = [m.as_dict() for m in readiness.all_advisories]
            step["pending_deliveries"] = [x.slug for x in deliveries if x is not d]
            return step
        results.append(step)
    # Every resolved target is accounted for. A target that could form no delivery
    # (not ready — e.g. a completion that no longer holds, ADR-061) keeps the request
    # from being done: independent work has finished, and what it still needs is named.
    unready = _unready(readiness, deliveries)
    outcome = "complete" if all(r["action"] == "done" for r in results) and not unready else "blocked"
    per_target: dict[str, str] = {t.id: "complete" for t in complete}
    for r in results:
        res = r.get("result") or {}
        for target in (res.get("delivery") or {}).get("targets", []):
            per_target[target] = res.get("outcome", "blocked")
    per_target.update({t.id: "not-ready" for t in unready})
    result: dict[str, Any] = {
        "outcome": outcome, "targets": per_target, "deliveries": [r.get("result") for r in results],
        "already_complete": [t.id for t in complete if t.id not in {x for d in deliveries for x in d.targets}]}
    if unready:
        result["not_ready"] = [m.as_dict() for t in unready for m in t.missing]
    return _action("done" if outcome == "complete" else "blocked", None, result=result)


def _delivery_operation(root: Path, d: Delivery, verb: str, **arguments) -> dict:
    engine = SpecEngine(d.path)
    setup = next((e for e in reversed(engine.record(d.run_id).events()) if e.type == "checkout.setup"), None)
    environment = checkout_environment(d.path, configured_python=engine.settings.python)
    if verb == "advance" and _view(engine, d.run_id).done is not None:
        # Observing a recorded completion is not a new judgment or delivery step.
        # Do not require its old interpreter, bind a session, or append a blocker.
        with _coordinator_observation(environment):
            ctx = _ctx(root, d, None, load_integration(root))
            observed = integ.observe(d.path, d.base, ctx.settings)
            if observed.state == "merged":
                return _finish(ctx, observed)
    try:
        if setup is not None and not setup.data["ok"]:
            raise EnvironmentUnavailable("setup-failed",
                                         f"{d.path}: setup `{setup.data['command']}` failed: {setup.data['detail']}")
        return run_operation(environment, {"verb": verb, "root": str(root), "delivery": d.as_dict(), **arguments})
    except EnvironmentUnavailable as exc:
        token = _provenance.set({"environment": environment.as_dict(),
                                 "copy": copy_provenance(coordinator_packages(), "coordinator")})
        try:
            settings = load_integration(root)
            ctx = _ctx(root, d, None, settings)
            _block(ctx, "environment", exc.kind, str(exc), environment=environment.as_dict())
            return _blocked(ctx, {})
        finally:
            _provenance.reset(token)


def _operation(payload: dict) -> dict:
    """Run a prepared delivery step or coordinator admission with bound provenance."""
    token = _provenance.set({"environment": payload["environment"], "copy": payload["copy"]})
    try:
        if payload["verb"] in ("probes", "test-interpreter", "runners-unable"):
            engine = Engine(Path(payload["root"]))
            if payload["verb"] == "runners-unable":
                probe = getattr(spec, "runners_unable", None)
                if not callable(probe):
                    raise EnvironmentUnavailable("prerequisite-unavailable",
                                                 "runners_unable is missing from dekspec.builder_compat")
                try:
                    return {"unable": probe(engine, payload["ib"])}
                except Exception as exc:
                    raise EnvironmentUnavailable("prerequisite-unavailable", f"runners_unable: {exc}") from exc
            if payload["verb"] == "test-interpreter":
                return {"ok": check_test_interpreter(engine)}
            return {"results": probe_prerequisites(engine, engine.contract(payload["ib"])),
                    "environment": payload["environment"]}
        raw = payload["delivery"]
        d = Delivery(raw["slug"], raw["targets"], raw["branch"], Path(raw["worktree"]),
                     raw["base"], raw["run"], True)
        root = Path(payload["root"])
        settings = load_integration(root)
        if payload["verb"] == "status":
            return _status_delivery(d, settings)
        if payload["verb"] == "ack":
            return _ack_delivery(d, payload["dispatch_id"], payload.get("summary", ""))
        if payload["verb"] == "recheck":
            return _recheck(d.path, payload["base_ref"], payload["ibs"], payload["intents"])
        ctx = _ctx(root, d, None, settings)
        _clear(ctx, "environment")
        _bind_session(d)
        return _advance(ctx)
    finally:
        _provenance.reset(token)


def _unready(readiness: Any, deliveries: list[Delivery]) -> list[Any]:
    """Requested targets that are neither complete nor carried by any delivery."""
    carried = {x for d in deliveries for x in d.targets}
    return [t for t in readiness.targets if t.outcome != "complete" and t.id not in carried]


def ack(root: Path, request: str, dispatch_id: str, *, summary: str = "") -> dict[str, Any]:
    """Acknowledge through the same copy that runs the delivery."""
    _resolution, _readiness, deliveries, _settings = _plan(Path(root), request)
    for d in deliveries:
        if d.exists and d.path.exists() and dispatch_id in _view(Engine(d.path), d.run_id).issued:
            return _delivery_operation(Path(root), d, "ack", dispatch_id=dispatch_id, summary=summary)
    raise DriverError(f"no delivery of `{request}` issued dispatch {dispatch_id}")


def _dispatch_items(view: RunView, delivery: Delivery) -> list[dict[str, Any]]:
    """Project dispatch identity and state from the ordered run record alone."""
    worktree = str(delivery.path.resolve())
    latest_by_key = {info["key"]: view.issued_at[ident] for ident, info in view.issued.items()}
    items = []
    for ident, info in view.issued.items():
        issued_at = view.issued_at[ident]
        if issued_at < view.integrated_at:
            state = "completed-run"
        elif ident in view.returned:
            state = "acknowledged"
        elif ident in view.lost:
            state = "superseded" if latest_by_key[info["key"]] > issued_at else "lost"
        else:
            state = "outstanding"
        items.append({"worktree": worktree, "run": delivery.run_id, "dispatch": ident,
                      "role": info["role"], "key": info["key"],
                      "prompt_sha256": info["prompt_sha256"], "state": state})
    return items


def _ack_delivery(d: Delivery, dispatch_id: str, summary: str) -> dict:
    engine = Engine(d.path)
    view = _view(engine, d.run_id)
    if dispatch_id in view.returned:
        return {"ack": dispatch_id, "already": True, **_provenance.get()}
    info = view.issued[dispatch_id]
    # Lean authors alone report a bounded factual path list (BS-046 BR 37).
    extra = {}
    if info["role"] == "test-author":
        paths = [line.partition("SKELETON:")[2].strip()
                 for line in summary.splitlines() if line.startswith("SKELETON:")]
        extra["skeletons"] = []
        for path in paths:
            parsed = Path(path)
            if parsed.is_absolute() and parsed.is_relative_to(d.path):
                path = parsed.relative_to(d.path).as_posix()
            extra["skeletons"].append(path)
    # Reports remain inert hashes and sizes, never reviewer evidence or commit messages.
    engine.record(d.run_id).append("dispatch.returned", DRIVER, {
        "id": dispatch_id, "summary_sha256": hashlib.sha256(summary.encode()).hexdigest(),
        "summary_chars": len(summary), **extra})
    info = view.issued[dispatch_id]
    in_merge = _git(d.path, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0
    unresolved = _git(d.path, "diff", "--name-only", "--diff-filter=U").stdout.strip()
    if not (in_merge and unresolved):
        _git(d.path, "add", "-A")
        msg = f"implement({d.slug}): {info['role']} {info['key']} returned ({dispatch_id})"
        empty = ["--allow-empty"] if info["role"] == "test-author" else []
        proc = _git(d.path, "commit", "-q", *empty, "--no-edit" if in_merge else "-m", *([] if in_merge else [msg]))
        if proc.returncode != 0 and _dirty(d.path):
            raise DriverError(f"checkpoint commit failed: {(proc.stderr or proc.stdout).strip()[-300:]}")
    return {"ack": dispatch_id, "delivery": d.slug, **_provenance.get()}


def status(root: Path, request: str) -> dict[str, Any]:
    """Read-only view of a request: resolution, readiness and each delivery's state."""
    root = Path(root)
    resolution, readiness, deliveries, settings = _plan(root, request)
    if readiness is None:
        return {"outcome": "not-ready", "resolution": resolution.as_dict()}
    out: dict[str, Any] = {"targets": [t.as_dict() for t in readiness.targets], "deliveries": []}
    for d in deliveries:
        entry: dict[str, Any] = {**d.as_dict(), "dispatches": []}
        if d.exists and d.path.exists():
            engine = Engine(d.path)
            environment = checkout_environment(d.path, configured_python=engine.settings.python)
            try:
                setup = next((e for e in reversed(engine.record(d.run_id).events())
                              if e.type == "checkout.setup"), None)
                if setup is not None and not setup.data["ok"]:
                    raise EnvironmentUnavailable("setup-failed",
                                                 f"{d.path}: setup `{setup.data['command']}` failed: {setup.data['detail']}")
                entry = run_operation(environment, {"verb": "status", "root": str(root), "delivery": d.as_dict()})
            except EnvironmentUnavailable as exc:
                # Keep the same read-only record/git/forge view when execution
                # is unavailable. No verification or completion runs here.
                with _coordinator_observation(environment):
                    entry = _status_delivery(d, settings)
                entry["blockers"].append({"kind": exc.kind, "detail": str(exc),
                                          "environment": environment.as_dict()})
                if entry["state"] != "complete":
                    entry["state"] = "blocked"
        else:
            entry["state"] = "not-started"
        out["deliveries"].append(entry)
    out.update(_status_summary(readiness, deliveries, out["deliveries"]))
    return out


@contextmanager
def _coordinator_observation(environment):
    """Read delivery state without starting its unavailable execution runtime."""
    token = _provenance.set({"environment": environment.as_dict(),
                             "copy": copy_provenance(coordinator_packages(), "coordinator")})
    try:
        with _entered_environment(environment):
            yield
    finally:
        _provenance.reset(token)


def _status_delivery(d: Delivery, settings: IntegrationSettings) -> dict:
    entry = {**d.as_dict(), **_provenance.get()}
    base_ref = integ.base_ref(d.path, d.base, settings, fetch=False)
    engine = Engine(d.path, base=base_ref)
    view = _view(engine, d.run_id)
    observed = integ.observe(d.path, d.base, settings, fetch=False)
    dispatches = _dispatch_items(view, d)
    entry.update({
        "integration": observed.as_dict(),
        "dispatches": dispatches,
        "outstanding_dispatches": [item["dispatch"] for item in dispatches
                                   if item["state"] == "outstanding"],
        "blockers": list(view.blockers.values()),
        "ibs": {ib: engine.contract(ib).status for ib in view.auth.get("ibs", [])},
        "state": _delivery_state(engine, view, d, settings, observed),
    })
    if view.done is not None:
        entry["integrated"] = _recorded_integration(view)
    return entry


def _status_summary(readiness: Any, deliveries: list[Delivery], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify the same observed states for status and the strict receipt."""
    out: dict[str, Any] = {}
    states = [e["state"] for e in entries]
    delivered = {t for e in entries if e["state"] == "complete" for t in e["targets"]}
    unready = _unready(readiness, deliveries)
    if unready:
        out["not_ready"] = [m.as_dict() for t in unready for m in t.missing]
    started = [s for s in states if s != "not-started"]
    if any(s in ("blocked", "integrated-unverified") for s in states):
        out["outcome"] = "blocked"
    elif readiness.targets and all(s == "complete" for s in states) and all(
            t.outcome == "complete" or t.id in delivered for t in readiness.targets):
        out["outcome"] = "complete"
    elif unready and not started:
        out["outcome"] = "not-ready"  # `next` refuses to start: readiness is an entry check
    elif unready and all(s == "complete" for s in started):
        out["outcome"] = "blocked"  # independent work is done; what remains is named in `not_ready`
    elif states and all(s == "not-started" for s in states):
        out["outcome"] = "not-started"
    else:
        out["outcome"] = "in-progress"
    return out


def _recorded_integration(view: RunView) -> dict[str, Any]:
    """The integration the run recorded (`run.integrated`), which stays put when the base moves
    on. It lives only in the delivery worktree's run record, which is never committed."""
    done = view.done or {}
    return {k: done.get(k) for k in ("revision", "tree", "verified_tree", "integrated_verified", "method")}


def _delivery_state(engine: Engine, view: RunView, d: Delivery, settings: IntegrationSettings,
                    observed: integ.Integration) -> str:
    """The delivery's state by the driver's own completion predicate (read-only)."""
    if observed.state == "merged" and view.done is not None:
        return "complete" if view.done.get("integrated_verified") else "integrated-unverified"
    base_ref = integ.base_ref(d.path, d.base, settings, fetch=False)
    intents = [t for t in d.targets if t.startswith("INT-")]
    if observed.state in ("merged", "push-pending") and \
            _landed(engine, view, view.auth.get("ibs", []), intents, base_ref)[0]:
        if observed.state == "push-pending":
            return "blocked" if view.blockers else "push-pending"
        # `next` records this; the verified content is integrated unchanged, or it re-verifies.
        return "complete" if observed.tree == integ.tree_of(d.path, "HEAD") else "integrating"
    return "blocked" if view.blockers else "active"


__all__ += ["DriverError", "EXECUTION_DIRNAME"]
