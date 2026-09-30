"""Thin CLI adapters for deterministic optional-tool helpers, never an executor."""
from __future__ import annotations

import json
from pathlib import Path

from .deepen_loop import assess
from .rotation_handoff import handoff_freshness, read_latest_handoff, write_handoff
from .rotation_handoff import identity, state_directory, target_root


def register_helpers(sub):
    handoff = sub.add_parser("handoff", help="Write/read continuity evidence.")
    handoff.add_argument("action", nargs="?", choices=("read", "write"), default="read")
    handoff.add_argument("--at", default=".")
    handoff.add_argument("--input", help="JSON record; required for write.")
    handoff.add_argument("--run-id")
    handoff.set_defaults(func=handoff_command)
    deepen = sub.add_parser(
        "deepen-record", help="Persist multi-pass evidence bound to core; no agent execution.",
        description=(
            "Actions: start (a run; --new-run archives it and carries its latest integration forward), begin "
            "(a pass, pending), append (its outcome), abandon (a pending pass without a run), status. begin "
            "reads the pass's input revision from the base branch itself and refuses a base that lacks the "
            "latest integrated revision. "
            "Pass JSON: pass_id (stable unique ID for retries), candidate (stable ID), targets (at most one "
            "IB or Intent; none for a dry reassessment), completed (count), evidence (list), rejected "
            "[{id,reason}], unresolved/resolved (ID lists), remaining (count), dry (bool), "
            "implementation_status (complete/not-needed/blocked/not-ready), blocker, cost; abandon takes "
            "pass_id and reason. A completion is recorded only when core reports the target complete with "
            "one integration recorded after begin; the pass then holds core's outcome, run id, delivery, "
            "integrated revision and tree, and per-IB completion references. blocked/not-ready need core to "
            "report it; abandon is refused while core shows an unintegrated run. A caller revision must "
            "equal core's; revision and verified are never stored. Outcomes: continue, interrupted (a pass is pending), convergence, stalled, "
            "budget, blocker. Refusals are JSON {error} and leave the record unchanged; status adds "
            "core_error when core cannot be read."),
    )
    deepen.add_argument("action", nargs="?", choices=("status", "start", "append", "begin", "abandon"),
                        default="status")
    deepen.add_argument("--at", default=".")
    deepen.add_argument("--scope", default="whole-repo")
    deepen.add_argument("--input")
    deepen.add_argument("--new-run", action="store_true", help="Archive an ended run and begin new authorized work.")
    deepen.add_argument("--max-passes", type=int, default=12, help="Host safety budget, not a single-pass limit.")
    deepen.set_defaults(func=deepen_command)


def _error(exc, code=1):
    print(f"error: {json.dumps(str(exc))}")
    return code


def handoff_command(args):
    root = target_root(Path(args.at))
    try:
        if args.action == "write":
            if not args.input:
                return _error("write needs --input", 2)
            record = json.loads(Path(args.input).read_text())
            if not isinstance(record, dict):
                return _error("record must be an object", 2)
            if args.run_id:
                record["run_id"] = args.run_id
            print(f"written: {json.dumps(str(write_handoff(root, record)))}")
        else:
            record = read_latest_handoff(root)
            print(json.dumps({"record": record, "stale": handoff_freshness(root, record, run_id=args.run_id) if record else [],
                              "count": int(record is not None)}))
        return 0
    except (OSError, ValueError) as exc:
        return _error(exc)


class _Refused(Exception):
    """A deepen-record request refused by rule; the record is left as it was."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


class _CoreUnavailable(Exception):
    """Core's status or its recorded integration cannot be read (IB-139 O-8)."""


#: Pass keys the tool owns; a caller cannot supply them.
_TOOL_KEYS = ("state", "begin", "core", "abandon", "revision", "verified")
_BLOCKED = ("blocked", "not-ready")


def _git_out(root: Path, *args: str) -> str | None:
    import subprocess
    proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    import subprocess
    return subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=str(root),
                          capture_output=True).returncode == 0


def _input_revision(root: Path) -> tuple[str, str]:
    """The base branch's tip, read by the tool (callers never supply it)."""
    from .implement.config import load_integration
    from .implement.integration import base_ref
    settings = load_integration(root)
    base = settings.base or next((b for b in ("main", "master")
                                  if _git_out(root, "rev-parse", "-q", "--verify", f"refs/heads/{b}")), "main")
    ref = base_ref(root, base, settings, fetch=False)
    revision = _git_out(root, "rev-parse", "-q", "--verify", f"{ref}^{{commit}}")
    if not revision:
        raise _Refused(f"cannot read the base branch {ref} to take the pass's input revision")
    return ref, revision


def _read_record(worktree: Path, ident: str, what: str):
    """Events of one of core's execution records, with its hash chain verified."""
    from .execution.record import ExecutionRecord
    record = ExecutionRecord(worktree, ident)
    problems = record.verify_chain()
    if problems:
        raise _CoreUnavailable(f"{what} {record.path} fails its hash chain: {problems[0]}")
    return record.events(strict=True)


def _core(root: Path, target: str) -> dict:
    """Core's view of one target: its resolution, outcome and deliveries, each with its run's last
    sequence and recorded integration, read from the run record with the hash chain verified.
    Read-only; raises `_CoreUnavailable` naming the cause."""
    from .implement import driver
    try:
        view = driver.status(root, target)
    except Exception as exc:  # noqa: BLE001 — any core failure is reported, never swallowed
        raise _CoreUnavailable(f"core `implement status {target}` failed: {type(exc).__name__}: {exc}") from exc
    resolved = [t["id"] for t in view.get("targets", [])]
    deliveries = []
    for entry in view.get("deliveries", []):
        if entry.get("state") == "not-started":
            continue
        worktree = Path(entry["worktree"])
        events = _read_record(worktree, entry["run"], f"the run record of {entry['slug']}")
        integrated = [e for e in events if e.type == "run.integrated"]
        deliveries.append({"slug": entry["slug"], "run": entry["run"], "worktree": worktree,
                           "state": entry.get("state"), "ibs": list(entry.get("ibs") or {}),
                           "outstanding": list(entry.get("outstanding_dispatches") or []),
                           "last_seq": events[-1].seq if events else 0,
                           "integration": integrated[-1] if integrated else None,
                           "reported": entry.get("integrated")})
    # A delivery whose worktree is gone drops out of core's report: its recorded integration
    # lived only there, so it cannot be read (IB-139 O-8).
    listing = (_git_out(root, "worktree", "list", "--porcelain") or "").splitlines()
    for ident in resolved:
        branch = f"implement/{ident.lower()}"
        if not _git_out(root, "rev-parse", "-q", "--verify", f"refs/heads/{branch}"):
            continue
        holder = current = None
        for line in listing:
            if line.startswith("worktree "):
                current = Path(line[len("worktree "):])
            elif line == f"branch refs/heads/{branch}":
                holder = current
        if holder is None or not holder.exists():
            raise _CoreUnavailable(f"the delivery worktree of {branch} ({holder or 'none'}) no longer exists, "
                                   "so its recorded integration cannot be read")
    return {"outcome": view.get("outcome"), "resolved": resolved, "deliveries": deliveries}


def _completion_refs(delivery: dict) -> dict:
    """Per IB: its current completion record's sequence and event hash, and the evidence and
    verdict that completion's gate cited — read from the IB's record with its chain verified."""
    from .execution.state import fold
    refs = {}
    for ib in delivery["ibs"]:
        events = _read_record(delivery["worktree"], ib, f"the execution record of {ib}")
        completions = fold(events).completions
        if not completions:
            raise _Refused(f"{ib} has no current completion record in {delivery['slug']}")
        seq, data = completions[-1]
        by_seq = {e.seq: e for e in events}
        evidence, verdict = by_seq.get(data.get("evidence_seq")), by_seq.get(data.get("verdict_seq"))
        if not (evidence and evidence.type == "evidence.recorded" and evidence.data.get("overall") == "passed"):
            raise _Refused(f"{ib}'s completion does not cite passing verification evidence")
        if not (verdict and verdict.type == "verdict.recorded" and verdict.data.get("verdict") == "pass"):
            raise _Refused(f"{ib}'s completion does not cite a passing independent verdict")
        refs[ib] = {"seq": seq, "hash": by_seq[seq].hash, "evidence_seq": evidence.seq,
                    "verdict_seq": verdict.seq}
    return refs


def _latest_integration(passes: list[dict]) -> str | None:
    done = [p["core"]["revision"] for p in passes if p.get("state") == "complete" and p.get("core")]
    return done[-1] if done else None


def _pending(record: dict) -> dict | None:
    passes = record.get("passes", [])
    return passes[-1] if passes and passes[-1].get("state") == "pending" else None


def _load_pass(args) -> dict:
    if not args.input:
        raise _Refused(f"{args.action} needs --input", 2)
    payload = json.loads(Path(args.input).read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("pass_id"), str) or not payload["pass_id"]:
        raise _Refused("pass must be an object with a pass_id", 2)
    targets = payload.get("targets")
    if targets is not None and (not isinstance(targets, list) or not all(isinstance(t, str) for t in targets)):
        raise _Refused("targets must be a list of ids", 2)
    return payload


def _begin(root: Path, record: dict, payload: dict) -> None:
    targets = payload.get("targets") or []
    if len(targets) > 1:
        raise _Refused("an implementing pass has at most one target (one IB or one Intent); "
                       f"{len(targets)} were given")
    pending = _pending(record)
    if pending is not None:
        raise _Refused(f"pass {pending['pass_id']} is pending; resolve it by append or abandon first")
    if any(p.get("pass_id") == payload["pass_id"] for p in record["passes"]):
        raise _Refused(f"pass_id {payload['pass_id']} is already recorded", 2)
    if record["status"] != "continue":
        raise _Refused(f"run already stopped: {record['status']}; inspect status before starting new work")
    ref, revision = _input_revision(root)
    latest = _latest_integration(record["passes"])
    # An archived run's passes are earlier passes too (O-6): `start --new-run` carries their latest
    # integration forward, and every later pass's input must still contain it.
    required = latest or record.get("prior_integration")
    if required and not _is_ancestor(root, required, revision):
        raise _Refused(f"the base {ref} at {revision} does not contain {required}, the latest integrated "
                       "revision recorded by an earlier pass" + ("" if latest else " (of an archived run)"))
    begin = {"input_revision": revision, "base": ref, "latest_integration": latest, "target": None,
             "core_runs": {}}
    if targets:
        core = _core(root, targets[0])
        if len(core["resolved"]) != 1:
            raise _Refused(f"{targets[0]} does not resolve to exactly one target "
                           f"(resolved: {core['resolved'] or 'none'})")
        if core["outcome"] == "complete":
            raise _Refused(f"core already reports {core['resolved'][0]} complete: nothing to do")
        begin["target"] = core["resolved"][0]
        begin["core_runs"] = {d["run"]: d["last_seq"] for d in core["deliveries"]}
    stored = {k: v for k, v in payload.items() if k not in _TOOL_KEYS}
    record["passes"].append({**stored, "state": "pending", "begin": begin})


def _same_targets(stored: dict, signal: dict) -> bool:
    if "targets" not in signal:
        return True
    given = {t.upper() for t in signal["targets"] or []}
    begun = {t.upper() for t in stored.get("targets") or []}
    target = stored["begin"].get("target")
    return given == begun or given == ({target} if target else set())


def _complete(root: Path, record: dict, stored: dict, signal: dict) -> dict:
    """Core's evidence for a completion claim, or a refusal (IB-139 O-5, O-6)."""
    begin = stored["begin"]
    target = begin["target"]
    core = _core(root, target)
    if core["outcome"] != "complete":
        raise _Refused(f"core does not report {target} complete (outcome: {core['outcome']})")
    after = [d for d in core["deliveries"] if d["integration"] is not None and (
        d["run"] not in begin["core_runs"] or d["integration"].seq > begin["core_runs"][d["run"]])]
    if not after:
        raise _Refused(f"core records no integration for {target} after the pass began "
                       "(the only recorded integration predates it)")
    if len(after) > 1:
        raise _Refused(f"the completion spans several deliveries: {', '.join(d['slug'] for d in after)}")
    delivery = after[0]
    event = delivery["integration"]
    revision, tree = event.data.get("revision"), event.data.get("tree")
    if delivery["reported"] and delivery["reported"].get("revision") != revision:
        raise _CoreUnavailable(f"core's status and the run record of {delivery['slug']} disagree on the "
                               "integrated revision")
    if "revision" in signal and signal["revision"] != revision:
        raise _Refused(f"revision {signal['revision']} is not core's recorded integrated revision {revision}")
    source = begin["input_revision"]
    if not revision or revision == source or not _is_ancestor(root, source, revision):
        raise _Refused(f"the integrated revision {revision} is not a strict descendant of the pass's input "
                       f"revision {source}")
    for other in record["passes"]:
        claimed = other.get("core") or {}
        if other is not stored and claimed.get("run") == delivery["run"] and \
                claimed.get("integration_seq") == event.seq:
            raise _Refused(f"pass {other['pass_id']} already claimed the integration {delivery['run']}#{event.seq}")
    return {"outcome": core["outcome"], "target": target, "run": delivery["run"], "delivery": delivery["slug"],
            "revision": revision, "tree": tree, "verified_tree": event.data.get("verified_tree"),
            "integrated_verified": event.data.get("integrated_verified"), "method": event.data.get("method"),
            "integration_seq": event.seq, "integration_hash": event.hash,
            "completions": _completion_refs(delivery)}


def _append(root: Path, record: dict, signal: dict) -> bool:
    """Resolve a pending pass; False when the append repeats a resolved one (idempotent)."""
    if not isinstance(signal.get("evidence"), list):
        raise _Refused("pass must be an object with pass_id and evidence list", 2)
    stored = next((p for p in record["passes"] if p.get("pass_id") == signal["pass_id"]), None)
    if stored is None or "begin" not in stored:
        raise _Refused(f"pass {signal['pass_id']} was never begun; `begin` it before appending its outcome")
    # The tool owns `revision` and `verified` (and the lifecycle keys): they are never stored from a
    # caller. A caller's revision is only compared with core's, on the completion path.
    fields = {k: v for k, v in signal.items() if k not in _TOOL_KEYS}
    if stored.get("state") != "pending":
        recorded = (stored.get("core") or {}).get("revision")
        if all(stored.get(k) == v for k, v in fields.items()) and (
                stored.get("state") != "complete" or signal.get("revision", recorded) == recorded):
            return False
        raise _Refused(f"pass {signal['pass_id']} is already resolved ({stored.get('state')}) with different "
                       "evidence", 2)
    if not _same_targets(stored, signal):
        raise _Refused(f"the targets {signal['targets']} are not the ones pass {signal['pass_id']} was begun with")
    target = stored["begin"].get("target")
    # A claim is judged on the pass as it would be stored: the begin payload merged with this outcome.
    merged = {**stored, **fields}
    status = merged.get("implementation_status")
    completed = merged.get("completed") or 0
    claims = bool(merged.get("targets")) or status == "complete" or completed > 0
    if status in _BLOCKED:
        if completed > 0:
            raise _Refused(f"a {status} outcome cannot record completed changes")
        if target:
            core = _core(root, target)
            if core["outcome"] not in _BLOCKED:
                raise _Refused(f"core does not report {target} blocked or not ready (outcome: {core['outcome']})")
            stored["core"] = {"outcome": core["outcome"], "target": target,
                              "runs": [d["run"] for d in core["deliveries"]]}
        stored.update(fields, state="blocker")
    elif target:
        if status == "not-needed" or not completed > 0:
            raise _Refused(f"pass {signal['pass_id']} was begun for {target}; it resolves only through core's "
                           "completion, a core-reported blocked or not-ready outcome, or abandon — never as "
                           "not-needed or completed: 0")
        stored["core"] = _complete(root, record, stored, signal)
        stored.update(fields, state="complete")
    elif claims:
        raise _Refused("a completion without targets is refused: a pass begun without targets is a dry "
                       "reassessment")
    else:
        stored.update(fields, state="dry")
    return True


def _abandon(root: Path, record: dict, payload: dict) -> bool:
    stored = next((p for p in record["passes"] if p.get("pass_id") == payload["pass_id"]), None)
    if stored is None or "begin" not in stored:
        raise _Refused(f"pass {payload['pass_id']} was never begun")
    if stored.get("state") == "abandoned":
        return False
    if stored.get("state") != "pending":
        raise _Refused(f"pass {payload['pass_id']} is already resolved ({stored.get('state')})")
    target = stored["begin"].get("target")
    if target:
        open_runs = [d["run"] for d in _core(root, target)["deliveries"] if d["integration"] is None]
        if open_runs:
            raise _Refused(f"core shows an unintegrated run for {target} ({', '.join(open_runs)}); resolve the "
                           "pass through core's outcome instead")
    stored.update(state="abandoned", abandon={"reason": payload.get("reason")})
    return True


def _status_view(root: Path, record: dict) -> dict:
    """The stored record, plus the pending pass and core's outstanding dispatches for it."""
    view = dict(record)
    pending = _pending(record)
    if pending is None:
        return view
    target = pending["begin"].get("target")
    shown = {"pass_id": pending["pass_id"], "targets": [target] if target else [],
             "outstanding_dispatches": []}
    if target:
        try:
            core = _core(root, target)
            shown["core_outcome"] = core["outcome"]
            shown["outstanding_dispatches"] = [i for d in core["deliveries"] for i in d["outstanding"]]
        except _CoreUnavailable as exc:
            view["core_error"] = str(exc)
    view["pending"] = shown
    return view


def _refuse(message: str, code: int = 1) -> int:
    print(json.dumps({"error": message}))
    return code


def deepen_command(args):
    import hashlib
    root = target_root(Path(args.at))
    key = hashlib.sha256(args.scope.encode()).hexdigest()[:12]
    path = state_directory(root, "deepening") / f"{key}.json"
    try:
        record = json.loads(path.read_text()) if path.exists() else None
        if args.action == "status":
            print(json.dumps(_status_view(root, record) if record else {"passes": [], "status": "not-started"}))
            return 0
        if args.new_run and args.action != "start":
            return _refuse("--new-run is only valid with start", 2)
        if args.action == "start":
            if args.max_passes < 2:
                return _refuse("multi-pass bound must be at least 2", 2)
            prior_record = carried = None
            if record and args.new_run:
                pending = _pending(record)
                if pending is not None:
                    return _refuse(f"pass {pending['pass_id']} is pending; resolve it by append or abandon "
                                   "before starting a new run")
                carried = _latest_integration(record["passes"]) or record.get("prior_integration")
                from datetime import datetime, timezone
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                archive = path.with_name(f"{path.stem}-{stamp}.json")
                path.rename(archive)
                prior_record = str(archive)
                record = None
            if record:
                print(json.dumps(record))  # idempotent resume, never discard learning
                return 0
            record = {"identity": identity(root), "scope": args.scope, "max_passes": args.max_passes,
                      "passes": [], "status": "continue", "prior_record": prior_record}
            if carried:
                record["prior_integration"] = carried
        else:
            if not record:
                return _refuse(f"start a record before {args.action}", 2)
            if record["identity"]["repo"] != str(root):
                return _refuse("record repository mismatch")
            payload = _load_pass(args)
            if args.action == "begin":
                _begin(root, record, payload)
            elif args.action == "abandon":
                if not _abandon(root, record, payload):
                    print(json.dumps(record))
                    return 0
            else:
                if record["status"] not in ("continue", "interrupted") and not any(
                        p.get("pass_id") == payload["pass_id"] for p in record["passes"]):
                    return _refuse(f"run already stopped: {record['status']}; inspect status before starting "
                                   "new work", 2)
                if not _append(root, record, payload):
                    print(json.dumps(record))  # a repeated append changes nothing
                    return 0
            record["status"] = assess(record["passes"], max_iterations=record["max_passes"])
            record["identity"] = identity(root)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2) + "\n")
        tmp.replace(path)
        print(json.dumps(record))
        return 0
    except _Refused as exc:
        return _refuse(str(exc), exc.code)
    except _CoreUnavailable as exc:
        return _refuse(f"core evidence unavailable: {exc}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _refuse(str(exc))


def scan_command(args):
    from .archeology.scan import scan
    try:
        root = target_root(Path(args.at))
        target = Path(args.target)
        if not target.is_absolute():
            target = root / target
        print(json.dumps([item.to_dict() for item in scan(target, repo_root=root)], indent=2))
        return 0
    except (OSError, ValueError) as exc:
        return _error(exc)
