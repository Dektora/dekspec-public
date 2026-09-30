"""`dekspec ib`, `dekspec delivery` and `dekspec intent` verbs (AE-011).

Exit codes: 0 ok · 1 refused / gate not satisfied · 2 usage · 3 blocked
(a truthful blocked outcome — attempts exhausted, no progress, stall,
unavailable prerequisite, contract conflict).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

__all__ = ["register"]


def _repo_root(args: argparse.Namespace) -> Path:
    if getattr(args, "at", None):
        return Path(args.at).resolve()
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(proc.stdout.strip() or os.getcwd()).resolve()


def _actor(args: argparse.Namespace) -> str:
    if getattr(args, "actor", None):
        return args.actor
    if os.environ.get("DEKSPEC_ACTOR"):
        return os.environ["DEKSPEC_ACTOR"]
    proc = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def _base(args: argparse.Namespace) -> str | None:
    """The delivery base: `--base`, else `$DEKSPEC_BASE` (set for every worker
    of an Implementation Run, so its unqualified commands share the run's base),
    else none — the conservative default of main / origin/main / master."""
    return getattr(args, "base", None) or os.environ.get("DEKSPEC_BASE") or None


def _engine(args: argparse.Namespace):
    from dekspec.execution.engine import Engine

    base = _base(args)
    if hasattr(args, "base"):
        args.base = base  # the verb's own base-aware calls read the same context
    return Engine(_repo_root(args), spec_root=args.dekspec_root, base=base)


def _emit(args: argparse.Namespace, payload: Any, human: Callable[[Any], str] | None = None) -> None:
    if getattr(args, "json", False) or human is None:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(human(payload))


def _run(fn: Callable[[argparse.Namespace], int]) -> Callable[[argparse.Namespace], int]:
    def wrapper(args: argparse.Namespace) -> int:
        from dekspec.execution.artifact_edit import ArtifactEditError
        from dekspec.execution.contract import ContractError
        from dekspec.execution.engine import Blocked, ExecutionError
        from dekspec.execution.fingerprint import FingerprintError
        from dekspec.execution.plan import PlanError
        from dekspec.execution.record import RecordIntegrityError
        from dekspec.execution.scope import ScopeError

        try:
            return fn(args)
        except Blocked as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 3
        except (ExecutionError, PlanError, ContractError, RecordIntegrityError, ArtifactEditError,
                FingerprintError, ScopeError) as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
    return wrapper


def _gate_text(gate: Any) -> str:
    lines = [f"{gate.ib}: {'SATISFIED' if gate.ok else 'NOT SATISFIED'}"]
    for c in gate.checks:
        lines.append(f"  [{'x' if c.ok else ' '}] {c.name}: {c.detail}")
    if gate.carried_forward:
        lines.append("  carried forward (outside every reviewed surface): " + ", ".join(gate.carried_forward))
    return "\n".join(lines)


# ----------------------------------------------------------------------- ib
@_run
def cmd_new(args: argparse.Namespace) -> int:
    from dekspec.vendoring import resolve_template

    root = _repo_root(args)
    folder = root / args.dekspec_root / "impl-briefs"
    folder.mkdir(parents=True, exist_ok=True)
    used = [int(m.group(1)) for p in (root / args.dekspec_root).rglob("IB-*.md")
            if (m := re.match(r"(?:P-)?IB-(\d{3,})-", p.name))]
    ib_id = f"IB-{(max(used) + 1 if used else 1):03d}"
    slug = re.sub(r"[^a-z0-9]+", "-", args.slug.lower()).strip("-")
    target = folder / f"{ib_id}-{slug}.md"
    template = resolve_template("implementation-brief", root)
    if template is None:
        print("REFUSED: implementation-brief template not found", file=sys.stderr)
        return 1
    text = template.read_text(encoding="utf-8")
    title = args.title or slug.replace("-", " ")
    text = text.replace("[bounded outcome, in a few words]", title, 1)
    if args.parent:
        text = text.replace("**Parent:** none", f"**Parent:** {args.parent}", 1)
    text = text.replace("| Date | Type | Change | Author |\n|------|------|--------|--------|",
                        "| Date | Type | Change | Author |\n|------|------|--------|--------|\n"
                        f"| {date.today().isoformat()} | Create | Scaffolded with `dekspec ib new`. | {_actor(args)} |", 1)
    target.write_text(text, encoding="utf-8")
    _emit(args, {"ib": ib_id, "path": str(target.relative_to(root))},
          lambda d: f"created {d['path']} ({d['ib']}, DRAFT, authority policy delegated)")
    return 0


@_run
def cmd_lint(args: argparse.Namespace) -> int:
    eng = _engine(args)
    c = eng.contract(args.ib)
    problems = list(c.contract_problems())
    packet = eng.context(args.ib) if c.is_delegated else None
    if packet:
        problems += packet.problems
    _emit(args, {"ib": c.ib_id, "ok": not problems, "problems": problems},
          lambda d: f"{d['ib']}: {'OK' if d['ok'] else 'PROBLEMS'}" + "".join(f"\n  - {p}" for p in d["problems"]))
    return 0 if not problems else 1


@_run
def cmd_propose(args: argparse.Namespace) -> int:
    status = _engine(args).propose(args.ib, _actor(args))
    print(f"{args.ib} → {status}")
    return 0


@_run
def cmd_accept(args: argparse.Namespace) -> int:
    payload = _engine(args).accept(args.ib, _actor(args))
    _emit(args, payload, lambda d: f"{args.ib} → ACCEPTED; baseline pins {len(d['assets'])} acceptance asset(s)"
          + (f" ({len(d['absent_assets'])} not yet written)" if d["absent_assets"] else "")
          + f" and {len(d['runner_inputs'])} runner input(s)")
    return 0


@_run
def cmd_baseline(args: argparse.Namespace) -> int:
    payload = _engine(args).rebaseline(args.ib, _actor(args), args.reason)
    _emit(args, payload, lambda d: f"{args.ib}: baseline refreshed before execution ({args.reason})")
    return 0


@_run
def cmd_amend(args: argparse.Namespace) -> int:
    payload = _engine(args).amend(args.ib, _actor(args), reviewer=args.reviewer, reason=args.reason)
    _emit(args, payload, lambda d: f"{args.ib}: acceptance amended by {args.reviewer} — {args.reason}; "
          "the completing verdict must acknowledge it")
    return 0


@_run
def cmd_context(args: argparse.Namespace) -> int:
    packet = _engine(args).context(args.ib)
    text = json.dumps(packet.as_dict(), indent=2) if args.json else packet.render_markdown()
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 1 if packet.problems else 0


@_run
def cmd_start(args: argparse.Namespace) -> int:
    payload = _engine(args).start(args.ib, args.owner or _actor(args), takeover=args.takeover)
    _emit(args, payload, lambda d: f"{d['ib']}: run owned by {d['owner']} (context {d['manifest_hash'][:12]})")
    return 0


@_run
def cmd_plan(args: argparse.Namespace) -> int:
    import yaml

    from dekspec.execution.plan import PlanError

    raw = Path(args.file).read_text(encoding="utf-8") if args.file != "-" else sys.stdin.read()
    try:
        plan = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise PlanError(f"plan is not valid YAML: {exc}") from exc
    payload = _engine(args).plan(args.ib, plan, _actor(args), takeover=args.takeover)
    _emit(args, payload, lambda d: f"{args.ib}: plan revision {d['revision']} committed "
          f"({'direct run' if d['direct'] else str(len(d['tasks'])) + ' task(s)'})"
          + (f"; deviations recorded: {', '.join(d['hypothesis_deviations'])}" if d["hypothesis_deviations"] else ""))
    return 0


@_run
def cmd_task(args: argparse.Namespace) -> int:
    payload = _engine(args).task(args.ib, args.task, args.action, _actor(args), note=args.note or "",
                                 evidence=args.evidence or "", takeover=args.takeover)
    _emit(args, payload, lambda d: f"{args.ib} {d['task']}: {d['status']}")
    return 0


@_run
def cmd_attempt(args: argparse.Namespace) -> int:
    eng = _engine(args)
    actor = _actor(args)
    if args.action == "start":
        payload = eng.attempt_start(args.ib, actor, task=args.task)
        _emit(args, payload, lambda d: f"{args.ib}: attempt {d['attempt']} of {d['allowed']} started")
        return 0
    if args.action == "heartbeat":
        eng.heartbeat(args.ib, actor, args.summary or "")
        return 0
    payload = eng.attempt_end(args.ib, actor, outcome=args.outcome, failure_class=args.failure_class or "",
                              summary=args.summary or "")
    _emit(args, payload, lambda d: f"{args.ib}: attempt {d['attempt']} ended {d['outcome']}"
          + (f" — BLOCKED ({d['blocked']['reason']}: {d['blocked']['detail']})" if d.get("blocked") else ""))
    return 3 if payload.get("blocked") else 0


@_run
def cmd_verify(args: argparse.Namespace) -> int:
    payload = _engine(args).verify(args.ib, _actor(args), base=args.base, record=not args.dry_run)

    def human(d: dict[str, Any]) -> str:
        lines = [f"{args.ib}: verification {d['overall'].upper()} at {d['fingerprint'][:12]}"]
        for r in d["results"]:
            lines.append(f"  {r['id']} [{r['kind']}] {r['status']}: {r.get('detail', '')}")
        for p in d["integrity_problems"] + d["context_problems"]:
            lines.append(f"  ! {p}")
        for v in d["scope"].get("violations", []):
            lines.append(f"  ! scope: {v.get('detail')}")
        for m in d["scope"].get("missing_spec_impact", []):
            lines.append(f"  ! {m}")
        if d["scope"].get("unplanned_in_scope"):
            lines.append("  deviation (recorded, allowed): " + ", ".join(d["scope"]["unplanned_in_scope"]))
        if d["attention"]:
            lines.append("  needs reviewer acknowledgment: " + ", ".join(d["attention"]))
        return "\n".join(lines)

    _emit(args, payload, human)
    return 0 if payload["overall"] == "passed" else 1


@_run
def cmd_floor(args: argparse.Namespace) -> int:
    """The acceptance floor report (ADR-062): read-only, records nothing.

    Exit 0 only when every new node is genuine red with a basis and every
    preserved node passes; 1 otherwise or for a legacy IB; 2 for an unknown IB
    (a message naming it, not a usage error) and for usage errors."""
    from dekspec.execution.floor import FloorError, UnknownIB, floor_report, floor_text

    try:
        report = floor_report(_repo_root(args), args.ib, spec_root=args.dekspec_root)
    except UnknownIB as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FloorError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({k: v for k, v in report.items() if not k.startswith("_")}, indent=2, sort_keys=True))
    else:
        print(floor_text(report))
    return 0 if report["ok"] else 1


def _dispatched_revision(args: argparse.Namespace, expected: str) -> tuple[int | None, str | None]:
    """The policy revision a verdict answers to, and a refusal if any (ADR-061).

    A worker the driver dispatched carries `DEKSPEC_ROLE=<role>@<revision>`. Only
    a dispatch of the reviewing role may record this verdict, and it records
    under the revision it was dispatched with, even when `--policy-revision` is
    omitted, so a review made under superseded instructions is never relabelled."""
    flag = getattr(args, "policy_revision", None)
    raw = os.environ.get("DEKSPEC_ROLE", "").strip()
    if not raw:
        return flag, None
    role, _sep, rev = raw.partition("@")
    if role != expected:
        return None, (f"REFUSED: this agent was dispatched as `{role}`; only a `{expected}` dispatch records this "
                      "verdict (ADR-061)")
    try:
        dispatched = int(rev)
    except ValueError:
        return None, f"REFUSED: malformed DEKSPEC_ROLE {raw!r} (expected <role>@<revision>)"
    if flag is not None and flag != dispatched:
        return None, (f"REFUSED: --policy-revision {flag} contradicts the dispatch ({raw}); record under the "
                      "revision you were dispatched with")
    return dispatched, None


@_run
def cmd_review(args: argparse.Namespace) -> int:
    if _actor(args) != args.reviewer:
        print(f"REFUSED: record the verdict as the reviewer — the acting identity is {_actor(args)!r}, "
              f"not {args.reviewer!r} (pass --actor or set DEKSPEC_ACTOR)", file=sys.stderr)
        return 1
    revision, refusal = _dispatched_revision(args, "code-reviewer")
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    payload = _engine(args).review(args.ib, args.reviewer, args.verdict, criteria=args.criteria or None,
                                   acknowledge=args.acknowledge or [], notes=args.notes or "",
                                   policy_revision=revision)
    _emit(args, payload, lambda d: f"{args.ib}: verdict {d['verdict'].upper()} by {d['reviewer']} "
          f"bound to {d['fingerprint'][:12]}")
    return 0


@_run
def cmd_complete(args: argparse.Namespace) -> int:
    gate = _engine(args).complete(args.ib, _actor(args), base=args.base)
    _emit(args, gate.as_dict(), lambda _d: _gate_text(gate) + ("\n→ COMPLETE" if gate.ok else ""))
    return 0 if gate.ok else 1


@_run
def cmd_gate(args: argparse.Namespace) -> int:
    gate = _engine(args).evaluate_completion(args.ib, readonly=True, base=args.base)
    _emit(args, gate.as_dict(), lambda _d: _gate_text(gate))
    return 0 if gate.ok else 1


@_run
def cmd_status(args: argparse.Namespace) -> int:
    payload = _engine(args).status(args.ib, base=args.base)

    def human(d: dict[str, Any]) -> str:
        att = d["attempts"]
        lines = [f"{d['ib']} ({d['path']}): {d['status']} · policy {d['authority_policy']} · run {d['phase']}"
                 f" · owner {d['owner'] or '-'} · attempts {att['used']}/{att['allowed']}"
                 + (f" (open #{att['open']})" if att["open"] else "")]
        for b in d["blockers"]:
            lines.append(f"  BLOCKED {b['reason']}: {b.get('detail', '')}")
        for tid, t in d["tasks"].items():
            lines.append(f"  {tid}: {t['status']} {t['owner'] or ''} covers {','.join(t['covers']) or '-'}")
        if "completion_gate" in d:
            g = d["completion_gate"]
            lines.append(f"  completion gate: {'satisfied' if g['ok'] else 'not satisfied'}")
            lines += [f"    [{'x' if c['ok'] else ' '}] {c['check']}: {c['detail']}" for c in g["checks"]]
        return "\n".join(lines)

    _emit(args, payload, human)
    return 0


@_run
def cmd_block(args: argparse.Namespace) -> int:
    _engine(args).block(args.ib, _actor(args), args.reason, args.detail or "")
    print(f"{args.ib}: BLOCKED ({args.reason})")
    return 3


@_run
def cmd_unblock(args: argparse.Namespace) -> int:
    _engine(args).unblock(args.ib, _actor(args), args.decision, extra_attempts=args.extra_attempts)
    print(f"{args.ib}: unblocked — {args.decision}")
    return 0


@_run
def cmd_ready(args: argparse.Namespace) -> int:
    items = _engine(args).ready()
    _emit(args, items, lambda d: "\n".join(f"{i['ib']}  {i['path']}" for i in d) or "0 IBs ready")
    return 0


@_run
def cmd_import_beads(args: argparse.Namespace) -> int:
    from dekspec.execution.legacy import import_beads

    payload = import_beads(_engine(args), args.ib, _actor(args), source=Path(args.source) if args.source else None)
    _emit(args, payload, lambda d: f"{d['ib']}: imported {d['imported']} legacy bead(s) as execution-record tasks")
    return 0


@_run
def cmd_adopt(args: argparse.Namespace) -> int:
    from dekspec.execution.legacy import adopt

    payload = adopt(_engine(args), args.ib, _actor(args), reason=args.reason)
    _emit(args, payload, lambda d: f"{d['ib']}: adopted under the delegated authority policy")
    return 0


# ----------------------------------------------------------------- delivery
@_run
def cmd_delivery_verify(args: argparse.Namespace) -> int:
    from dekspec.execution.delivery import delivery_verify, discover_delivery_ibs

    eng = _engine(args)
    ibs = args.ib or discover_delivery_ibs(eng, args.base)
    payload = delivery_verify(eng, ibs, _actor(args), base=args.base)
    _emit(args, payload, lambda d: f"delivery {d['delivery']['overall'].upper()}: "
          + ", ".join(f"{k} {v}" for k, v in d["ibs"].items())
          + (f"; integration {d['delivery']['integration']['status']}" if d["delivery"]["integration"] else ""))
    return 0 if payload["delivery"]["overall"] == "passed" else 1


@_run
def cmd_delivery_check(args: argparse.Namespace) -> int:
    from dekspec.execution.delivery import delivery_check

    result = delivery_check(_engine(args), args.ib or None, base=args.base, rerun=args.rerun)

    def human(_d: Any) -> str:
        lines = [f"delivery {'READY TO LAND' if result.ok else 'NOT READY'} ({', '.join(result.ibs) or 'no IBs'})"]
        lines += [f"  [{'x' if c.ok else ' '}] {c.name}: {c.detail}" for c in result.checks]
        lines += [_gate_text(g) for g in result.gates]
        return "\n".join(lines)

    _emit(args, result.as_dict(), human)
    return 0 if result.ok else 1


# ------------------------------------------------------------------- intent
@_run
def cmd_intent_verify(args: argparse.Namespace) -> int:
    from dekspec.execution.intent_gate import intent_verify

    payload = intent_verify(_engine(args), args.intent, _actor(args))
    _emit(args, payload, lambda d: f"{args.intent}: outcome verification {d['overall'].upper()}"
          + "".join(f"\n  {r['id']} {r['status']}: {r.get('detail', '')}" for r in d["results"]))
    return 0 if payload["overall"] == "passed" else 1


@_run
def cmd_intent_review(args: argparse.Namespace) -> int:
    from dekspec.execution.intent_gate import intent_review

    if _actor(args) != args.reviewer:
        print(f"REFUSED: record the verdict as the reviewer — the acting identity is {_actor(args)!r}, "
              f"not {args.reviewer!r} (pass --actor or set DEKSPEC_ACTOR)", file=sys.stderr)
        return 1
    revision, refusal = _dispatched_revision(args, "verifier")
    if refusal:
        print(refusal, file=sys.stderr)
        return 1
    payload = intent_review(_engine(args), args.intent, args.reviewer, args.verdict, args.notes or "",
                            policy_revision=revision)
    _emit(args, payload, lambda d: f"{args.intent}: verdict {d['verdict']} by {d['reviewer']}")
    return 0


@_run
def cmd_intent_complete(args: argparse.Namespace) -> int:
    from dekspec.execution.intent_gate import intent_complete, intent_evaluate

    eng = _engine(args)
    gate = intent_evaluate(eng, args.intent) if args.check_only else intent_complete(eng, args.intent, _actor(args))
    _emit(args, gate.as_dict(), lambda _d: _gate_text(gate) + ("\n→ COMPLETE" if gate.ok and not args.check_only else ""))
    return 0 if gate.ok else 1


# ----------------------------------------------------------------- register
def _common(p: argparse.ArgumentParser, *, ib: bool = True) -> None:
    if ib:
        p.add_argument("ib", help="IB id (IB-NNN) or path to the IB file")
    p.add_argument("--at", help="repository root (default: git top level of the cwd)")
    p.add_argument("--dekspec-root", default="dekspec", help="spec tree relative to the repo (default: dekspec)")
    p.add_argument("--actor", help="identity recorded for this action (default: $DEKSPEC_ACTOR, then git user.name)")
    p.add_argument("--json", action="store_true", help="machine-readable output")


def register(sub: argparse._SubParsersAction) -> None:
    ib = sub.add_parser(
        "ib",
        help="Execute an Implementation Brief directly: authorize, run, verify, review, complete.",
        description="The IB execution path (ADR-055–058). No code beads: ownership, plans, attempts, "
                    "evidence and completion live in the IB's execution record under .dekspec/execution/.",
    )
    ibs = ib.add_subparsers(dest="ib_command", metavar="<ib-command>", required=True)

    p = ibs.add_parser("new", help="scaffold a delegated IB (no parent artifact required)")
    p.add_argument("slug")
    p.add_argument("--title")
    p.add_argument("--parent", help="optional parent Intent / WS / Mission id")
    _common(p, ib=False)
    p.set_defaults(func=cmd_new)

    for name, fn, hlp in (
        ("lint", cmd_lint, "check the IB is an executable contract whose references resolve"),
        ("propose", cmd_propose, "DRAFT → PROPOSED (lint-gated): request authorization"),
        ("accept", cmd_accept, "PROPOSED → ACCEPTED: authorize execution and take the acceptance baseline"),
        ("status", cmd_status, "derived execution state and the completion gate"),
        ("gate", cmd_gate, "evaluate the completion gate without writing anything"),
        ("complete", cmd_complete, "record completion (ACCEPTED → COMPLETE) if the evidence gate passes"),
        ("verify", cmd_verify, "run the acceptance conditions, scope and integrity checks; record evidence"),
    ):
        p = ibs.add_parser(name, help=hlp)
        _common(p)
        if name in ("verify", "status", "gate", "complete"):
            p.add_argument("--base", help="the delivery's base branch, for the scope diff "
                                          "(default: $DEKSPEC_BASE, else main / origin/main / master)")
        if name == "verify":
            p.add_argument("--dry-run", action="store_true", help="run checks without recording evidence")
        p.set_defaults(func=fn)

    p = ibs.add_parser("floor", help="the acceptance floor report (read-only): each criterion's nodes, "
                                     "new or preserved, failure kind and line, declared basis; floor digest")
    p.add_argument("ib", help="IB id (IB-NNN) or path to the IB file")
    p.add_argument("--at", help="repository root (default: git top level of the cwd)")
    p.add_argument("--dekspec-root", default="dekspec", help="spec tree relative to the repo (default: dekspec)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_floor)

    p = ibs.add_parser("baseline", help="refresh the acceptance baseline before execution starts")
    _common(p)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_baseline)

    p = ibs.add_parser("amend", help="recorded amendment of the acceptance contract after execution started")
    _common(p)
    p.add_argument("--reviewer", required=True, help="independent reviewer authorizing the amendment")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_amend)

    p = ibs.add_parser("context", help="generate the execution context (canonical obligations + manifest)")
    _common(p)
    p.add_argument("--out", help="write to a file instead of stdout")
    p.set_defaults(func=cmd_context)

    p = ibs.add_parser("start", help="start or resume the IB's run (checks prerequisites, binds context)")
    _common(p)
    p.add_argument("--owner", help="run owner (default: the actor)")
    p.add_argument("--takeover", action="store_true", help="transfer ownership from another agent (recorded)")
    p.add_argument("--base", help="the delivery's base branch — for historical dependencies and scope (default: $DEKSPEC_BASE, else main / origin/main / master)")
    p.set_defaults(func=cmd_start)

    p = ibs.add_parser("plan", help="commit or revise the executor's plan (YAML: findings, tasks | direct)")
    _common(p)
    p.add_argument("--file", required=True, help="plan YAML path, or - for stdin")
    p.add_argument("--takeover", action="store_true")
    p.set_defaults(func=cmd_plan)

    p = ibs.add_parser("task", help="claim / done / block / release an internal task")
    _common(p)
    p.add_argument("action", choices=["claim", "done", "block", "release"])
    p.add_argument("task")
    p.add_argument("--note")
    p.add_argument("--evidence")
    p.add_argument("--takeover", action="store_true")
    p.set_defaults(func=cmd_task)

    p = ibs.add_parser("attempt", help="start / heartbeat / end a counted attempt")
    _common(p)
    p.add_argument("action", choices=["start", "heartbeat", "end"])
    p.add_argument("--task")
    p.add_argument("--outcome", default="failed", choices=["passed", "failed", "error", "abandoned"])
    p.add_argument("--failure-class")
    p.add_argument("--summary")
    p.set_defaults(func=cmd_attempt)

    p = ibs.add_parser("review", help="record an independent review verdict bound to the current content")
    _common(p)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--verdict", required=True, choices=["pass", "fail"])
    p.add_argument("--criteria", nargs="*", help="review conditions covered (default: all review conditions)")
    p.add_argument("--acknowledge", nargs="*", help="attention items acknowledged (amendments, new assets, runner inputs)")
    p.add_argument("--notes")
    p.add_argument("--policy-revision", type=int, dest="policy_revision",
                   help="the code-reviewer policy revision the review was dispatched under (from its instructions); "
                        "refused if the policy has changed since (ADR-061)")
    p.set_defaults(func=cmd_review)

    p = ibs.add_parser("block", help="record a blocked outcome")
    _common(p)
    p.add_argument("--reason", required=True,
                   choices=["attempts-exhausted", "no-progress", "stalled", "prerequisite-unavailable",
                            "contract-conflict", "scope-expansion", "acceptance-invalid", "other"])
    p.add_argument("--detail")
    p.set_defaults(func=cmd_block)

    p = ibs.add_parser("unblock", help="record the decision that resolves a blocker")
    _common(p)
    p.add_argument("--decision", required=True)
    p.add_argument("--extra-attempts", type=int, default=0)
    p.set_defaults(func=cmd_unblock)

    p = ibs.add_parser("ready", help="accepted IBs whose dependencies are complete and that no run owns")
    _common(p, ib=False)
    p.add_argument("--base", help="the delivery's base branch — for historical dependencies and scope (default: $DEKSPEC_BASE, else main / origin/main / master)")
    p.set_defaults(func=cmd_ready)

    p = ibs.add_parser("import-beads", help="migrate a legacy IB's code beads into its execution record")
    _common(p)
    p.add_argument("--source", help="bead JSONL (default: .beads/issues.jsonl)")
    p.set_defaults(func=cmd_import_beads)

    p = ibs.add_parser("adopt", help="switch a rewritten legacy IB to the delegated policy (recorded)")
    _common(p)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_adopt)

    dl = sub.add_parser("delivery", help="Integrated verification and the landing gate for a branch (ADR-058).")
    dls = dl.add_subparsers(dest="delivery_command", metavar="<delivery-command>", required=True)
    for name, fn, hlp in (
        ("verify", cmd_delivery_verify, "re-run every included IB's acceptance + the integration command at this head"),
        ("check", cmd_delivery_check, "the landing gate: every included IB satisfied at this exact head"),
    ):
        p = dls.add_parser(name, help=hlp)
        _common(p, ib=False)
        p.add_argument("--ib", action="append", help="IB in the delivery (repeatable; default: discovered from the diff)")
        p.add_argument("--base", help="base branch (default: $DEKSPEC_BASE, else main)")
        if name == "check":
            p.add_argument("--rerun", action="store_true",
                           help="re-execute acceptance instead of trusting records; write nothing (CI mode)")
        p.set_defaults(func=fn)

    it = sub.add_parser("intent", help="Intent outcome verification and evidence-backed completion.")
    its = it.add_subparsers(dest="intent_command", metavar="<intent-command>", required=True)
    p = its.add_parser("verify", help="run the Intent's Verification commands and record evidence")
    p.add_argument("intent")
    _common(p, ib=False)
    p.set_defaults(func=cmd_intent_verify)
    p = its.add_parser("review", help="independent verdict for manual verification entries")
    p.add_argument("intent")
    _common(p, ib=False)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--verdict", required=True, choices=["pass", "fail"])
    p.add_argument("--notes")
    p.add_argument("--policy-revision", type=int, dest="policy_revision",
                   help="the verifier policy revision the attestation was dispatched under; refused if it has "
                        "changed since (ADR-061)")
    p.set_defaults(func=cmd_intent_review)
    p = its.add_parser("complete", help="ACCEPTED → COMPLETE when child IBs are complete and outcome evidence is current")
    p.add_argument("intent")
    _common(p, ib=False)
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--base", help="the delivery's base branch — for historical dependencies and scope (default: $DEKSPEC_BASE, else main / origin/main / master)")
    p.set_defaults(func=cmd_intent_complete)
