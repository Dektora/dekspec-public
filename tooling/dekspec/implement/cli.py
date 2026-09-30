"""`dekspec implement` — the core caller contract of ADR-059.

    dekspec implement resolve "<request>"   targets a request names (ids, lowercase ids, descriptions)
    dekspec implement ready   "<request>"   the READY predicate, with the specific missing preparation
    dekspec implement next    "<request>"   take every mechanical step; print the next action
    dekspec implement ack     "<request>" <dispatch-id> [--summary …]   a dispatched worker returned
    dekspec implement status  "<request>"   read-only: per-target and per-delivery state

Exit codes: 0 ok (ready / an action to take / complete), 1 not ready or
refused, 2 usage, 3 blocked (a genuine blocker holds the remaining work).
`--json` prints the machine-readable payload optional tools consume.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dekspec.execution.cli import _actor, _run

__all__ = ["register"]


def _root(args: argparse.Namespace) -> Path:
    import subprocess

    if getattr(args, "at", None):
        return Path(args.at).resolve()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    return Path(top or ".").resolve()


def _request(args: argparse.Namespace) -> str:
    return " ".join(args.request).strip()


def _print(args: argparse.Namespace, payload: Any, text: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str) if args.json else text)


def _missing_text(items: list[dict[str, Any]]) -> str:
    return "\n".join(f"  - {m['target']}: {m['detail']}\n      → {m['fix']}" for m in items)


def _guard(fn):
    wrapped = _run(fn)

    def call(args: argparse.Namespace) -> int:
        from dekspec.implement.driver import DriverError

        try:
            return wrapped(args)
        except DriverError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1
    return call


@_guard
def cmd_resolve(args: argparse.Namespace) -> int:
    from dekspec.implement.targets import resolve

    res = resolve(_root(args), _request(args), spec_root=args.dekspec_root)
    lines = [f"{t.id} ({t.kind}, {t.status}) — {t.name}" for t in res.targets]
    lines += [f"{p['code']}: {p['detail']}" + "".join(f"\n    {c}" for c in p.get("candidates", []))
              for p in res.problems]
    _print(args, res.as_dict(), "\n".join(lines))
    return 0 if res.ok else 1


@_guard
def cmd_ready(args: argparse.Namespace) -> int:
    from dekspec.implement.readiness import assess
    from dekspec.implement.targets import resolve

    root = _root(args)
    res = resolve(root, _request(args), spec_root=args.dekspec_root)
    if not res.ok:
        _print(args, {"ready": False, "resolution": res.as_dict()},
               "NOT READY — the request does not resolve:\n" + "\n".join(
                   f"  - {p['code']}: {p['detail']}" for p in res.problems))
        return 1
    readiness = assess(root, res.targets, spec_root=args.dekspec_root)
    payload = readiness.as_dict()
    if readiness.ready:
        text = ("READY — " + ", ".join(f"{t.id} ({', '.join(t.ibs) or 'no IBs'})" for t in readiness.targets)
                + f"\n  order: {' → '.join(readiness.order) or '—'}"
                + f"\n  deliveries: {'; '.join('+'.join(g) for g in readiness.groups)}"
                + f"\n  integration: {readiness.integration.get('method')} into {readiness.base}")
        done = [t.id for t in readiness.targets if t.outcome == "complete"]
        if done:
            text += f"\n  already complete: {', '.join(done)}"
    elif readiness.targets and all(t.outcome == "complete" for t in readiness.targets):
        text = "COMPLETE — " + ", ".join(t.id for t in readiness.targets) + " (nothing to implement)"
        _print(args, payload, text)
        return 0
    else:
        text = "NOT READY — missing preparation:\n" + _missing_text(payload["missing"])
    _print(args, payload, text)
    return 0 if readiness.ready else 1


def _action_text(step: dict[str, Any]) -> str:
    kind = step["action"]
    if kind == "dispatch":
        return (f"DISPATCH {step['id']} — {step['role']} for {step.get('ib') or step.get('intent') or step['key']} "
                f"as {step['actor']} in {step['worktree']}\n\n{step['prompt']}")
    if kind == "wait":
        return f"WAIT {step.get('seconds', 60)}s — {step.get('reason', '')}"
    if kind == "not-ready":
        if "readiness" in step:
            return "NOT READY — missing preparation:\n" + _missing_text(step["readiness"]["missing"])
        return "NOT READY — " + "; ".join(p["detail"] for p in step["resolution"]["problems"])
    result = step.get("result", {})
    return f"{kind.upper()} — {json.dumps(result, indent=2, default=str)}"


@_guard
def cmd_next(args: argparse.Namespace) -> int:
    from dekspec.implement.driver import next_step

    step = next_step(_root(args), _request(args), actor=_actor(args))
    _print(args, step, _action_text(step))
    return {"not-ready": 1, "blocked": 3}.get(step["action"], 0)


@_guard
def cmd_ack(args: argparse.Namespace) -> int:
    from dekspec.implement.driver import ack

    out = ack(_root(args), _request(args), args.dispatch, summary=args.summary or "")
    _print(args, out, f"ACK {args.dispatch} — {'already recorded' if out.get('already') else 'recorded'}")
    return 0


@_guard
def cmd_status(args: argparse.Namespace) -> int:
    from dekspec.implement.driver import status

    out = status(_root(args), _request(args))
    lines = [f"{out.get('outcome', '?').upper()}"]
    for d in out.get("deliveries", []):
        lines.append(f"  {d['slug']}: {d['state']} — branch {d['branch']}, worktree {d['worktree']}")
        for b in d.get("blockers", []):
            lines.append(f"      blocker {b['kind']}: {b['detail']}")
    _print(args, out, "\n".join(lines))
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "implement",
        help="Implement ready work autonomously: resolve, check readiness, drive to integrated completion.",
        description="The core of `/implement` (ADR-059). `next` takes every mechanical step and prints the one "
                    "action an agent harness must take; `ack` records that a dispatched worker returned.",
    )
    verbs = p.add_subparsers(dest="implement_command", metavar="<implement-command>", required=True)
    for name, fn, hlp in (
        ("resolve", cmd_resolve, "targets a request names — explicit ids, lowercase ids or a description"),
        ("ready", cmd_ready, "the READY predicate, with the specific missing preparation when not ready"),
        ("next", cmd_next, "take every mechanical step; print the next action (dispatch, wait, done, blocked)"),
        ("status", cmd_status, "read-only state of each target and delivery"),
    ):
        q = verbs.add_parser(name, help=hlp)
        q.add_argument("request", nargs="+", help="e.g. INT-041, 'int-041 and int-042', 'the auth feature'")
        _common(q)
        q.set_defaults(func=fn)
    q = verbs.add_parser("ack", help="record that dispatched worker <dispatch> returned; checkpoint its work")
    q.add_argument("request", nargs="+", help="the same request passed to `next`")
    q.add_argument("--dispatch", required=True, help="dispatch id from `next` (D-n)")
    q.add_argument("--summary", help="the worker's report")
    _common(q)
    q.set_defaults(func=cmd_ack)


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--at", help="repository root (default: git top level of the cwd)")
    p.add_argument("--dekspec-root", default="dekspec", help="spec tree relative to the repo (default: dekspec)")
    p.add_argument("--actor", help="identity recorded as the requester (default: $DEKSPEC_ACTOR, then git user.name)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
