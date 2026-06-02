#!/usr/bin/env python3
"""Resolve a bead's parent Intent and next execution attempt_number.

`/exec-coding-session` performs this walk in prose twice — once to pick the
`SESSION_BIND_ID` for the lifecycle prelude, and once in the IC-004 compliance
section to record an execution attempt:

    bead ID
      -> the bead's `external_ref` names a parent Implementation Brief (IB)
      -> the IB's `**Intent:**` field names the parent Intent directly
         (or, failing that, the IB's `**Spec:**` Working Spec names it)
      -> query `dekspec executions ls --intent <id>` for the highest
         existing attempt_number; the next attempt is that + 1

This module turns the prose into one deterministic lookup. It is a CLI
(`resolve_parent_intent.py <bead-id>`) and importable
(`resolve_parent_intent(bead_id, repo_root)`).

NOTE: a sibling shared script `resolve_bead_context.py` performs a similar
IB/WS/Intent hop walk, but it lives on an unmerged branch. This script is
intentionally standalone (no dependency on the shared script) and thinner —
focused on the Intent id + next attempt_number, which the shared variant
does not compute.

Output (JSON on stdout):

    {"bead": "bd-42", "intent": "INT-011", "attempt_id": null,
     "next_attempt_number": 3, "ib": "dekspec/impl-briefs/IB-019-foo.md"}

`attempt_id` is null unless `--record` is passed; with `--record` the script
runs `dekspec executions record-attempt` and fills in the returned id.

Exit codes:
  0 — bead resolved (intent may still be null for a loose task — see `intent`)
  2 — bead could not be located at all
  3 — a `dekspec executions` invocation failed (only with `--record`)

Style mirrors `tooling/dekspec/cli.py`. Stdlib-only — vendored into consumer
repos where the `dekspec` engine is not importable.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

# A runner: given an argv list + cwd, return (returncode, stdout, stderr).
# Injectable so tests need not depend on real `br` / `dekspec` installs.
Runner = Callable[[list[str], Path], "tuple[int, str, str]"]

# `external_ref` may carry a `:suffix` slice qualifier — strip it.
_IB_TOKEN_RE = re.compile(r"\bIB-\d{3,}\b")
_INTENT_TOKEN_RE = re.compile(r"\bINT-\d{3,}\b")

# IB front-matter field lines:
#   `**Intent:** \`dekspec/intents/INT-011-foo.md\``
#   `**Spec:**   \`dekspec/working-specs/WS-010-bar.md\``
_INTENT_FIELD_RE = re.compile(r"^\*\*Intent:\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
_SPEC_FIELD_RE = re.compile(r"^\*\*Spec:\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)


class IntentResolutionError(Exception):
    """Raised when a bead cannot be located at all (a hard failure)."""


def _default_runner(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a subprocess with list argv (never shell=True). Returns triple."""
    proc = subprocess.run(
        argv, capture_output=True, text=True, cwd=cwd, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def _strip_suffix(ref: str) -> str:
    """Drop a trailing `:suffix` qualifier from an external_ref."""
    return ref.split(":", 1)[0].strip()


def _lookup_bead(bead_id: str, repo_root: Path, runner: Runner) -> dict | None:
    """Find a bead via `br show <id> --json`, falling back to the JSONL store."""
    if shutil.which("br"):
        try:
            code, out, _ = runner(
                ["br", "show", bead_id, "--format", "json"], repo_root
            )
        except OSError:
            code, out = 1, ""
        if code == 0 and out.strip():
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, list):
                for bead in payload:
                    if isinstance(bead, dict) and bead.get("id") == bead_id:
                        return bead
                if payload and isinstance(payload[0], dict):
                    return payload[0]
            elif isinstance(payload, dict):
                return payload
    return _lookup_bead_jsonl(bead_id, repo_root)


def _lookup_bead_jsonl(bead_id: str, repo_root: Path) -> dict | None:
    """Scan `.beads/issues.jsonl` for a bead row. Returns the dict or None."""
    jsonl_path = repo_root / ".beads" / "issues.jsonl"
    if not jsonl_path.is_file():
        return None
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            bead = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(bead, dict) and bead.get("id") == bead_id:
            return bead
    return None


def _resolve_ib_path(ib_token_or_path: str, repo_root: Path) -> Path | None:
    """Resolve an IB reference (bare `IB-NNN` or a path) to a file on disk."""
    ib_token_or_path = _strip_suffix(ib_token_or_path)
    candidate = Path(ib_token_or_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    if candidate.is_file():
        return candidate
    # Bare token — glob the flat impl-briefs/ tree for `IB-NNN-*.md`.
    token_match = _IB_TOKEN_RE.search(ib_token_or_path)
    if token_match:
        briefs_dir = repo_root / "dekspec" / "impl-briefs"
        if briefs_dir.is_dir():
            hits = sorted(briefs_dir.glob(f"{token_match.group(0)}-*.md"))
            if hits:
                return hits[0]
    return None


def _intent_from_ib(ib_path: Path, repo_root: Path) -> str | None:
    """Read an IB and return its parent `INT-NNN` id.

    Prefers the IB's own `**Intent:**` field; failing that, reads the parent
    Working Spec named by `**Spec:**` and looks for an Intent token there.
    """
    try:
        text = ib_path.read_text(encoding="utf-8")
    except OSError:
        return None
    field = _INTENT_FIELD_RE.search(text)
    if field:
        token = _INTENT_TOKEN_RE.search(field.group(1))
        if token:
            return token.group(0)
    # Fall back through the Working Spec.
    spec_field = _SPEC_FIELD_RE.search(text)
    if spec_field:
        ws_path = Path(_strip_suffix(spec_field.group(1)))
        if not ws_path.is_absolute():
            ws_path = repo_root / ws_path
        if ws_path.is_file():
            try:
                ws_text = ws_path.read_text(encoding="utf-8")
            except OSError:
                ws_text = ""
            token = _INTENT_TOKEN_RE.search(ws_text)
            if token:
                return token.group(0)
    return None


def _next_attempt_number(
    intent_id: str, repo_root: Path, runner: Runner
) -> int:
    """Query `dekspec executions ls` for the next attempt_number for an Intent.

    Returns the highest existing attempt_number + 1; 1 when no prior attempts
    exist or the engine / query is unavailable (a safe default).
    """
    if not shutil.which("dekspec"):
        return 1
    try:
        code, out, _ = runner(
            ["dekspec", "executions", "ls", "--intent", intent_id, "--json"],
            repo_root,
        )
    except OSError:
        return 1
    if code != 0 or not out.strip():
        return 1
    try:
        rows = json.loads(out)
    except json.JSONDecodeError:
        return 1
    if isinstance(rows, dict):
        rows = rows.get("attempts") or rows.get("executions") or []
    if not isinstance(rows, list):
        return 1
    highest = 0
    for row in rows:
        if isinstance(row, dict):
            try:
                highest = max(highest, int(row.get("attempt_number") or 0))
            except (TypeError, ValueError):
                continue
    return highest + 1


def _record_attempt(
    intent_id: str,
    attempt_number: int,
    agent: str,
    repo_root: Path,
    runner: Runner,
) -> str | None:
    """Run `dekspec executions record-attempt`; return the attempt_id or None."""
    code, out, err = runner(
        [
            "dekspec", "executions", "record-attempt",
            "--intent", intent_id,
            "--agent", agent,
            "--attempt", str(attempt_number),
            "--json",
        ],
        repo_root,
    )
    if code != 0:
        raise IntentResolutionError(
            f"`dekspec executions record-attempt` failed (exit {code}): "
            f"{err.strip()}"
        )
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        raise IntentResolutionError(
            f"record-attempt produced non-JSON output: {exc}"
        ) from exc
    return payload.get("attempt_id") if isinstance(payload, dict) else None


def resolve_parent_intent(
    bead_id: str,
    repo_root: Path,
    runner: Runner | None = None,
    record: bool = False,
    agent: str = "unknown",
) -> dict[str, object]:
    """Resolve a bead's parent Intent and next attempt_number.

    Raises IntentResolutionError when the bead cannot be located at all, or
    (with `record=True`) when `record-attempt` fails.
    """
    run = runner or _default_runner
    repo_root = Path(repo_root)

    bead = _lookup_bead(bead_id, repo_root, run)
    if bead is None:
        raise IntentResolutionError(f"bead not found: {bead_id}")

    ext_ref = str(bead.get("external_ref") or bead.get("externalRef") or "")
    ib_path: Path | None = None
    intent_id: str | None = None
    if ext_ref:
        ib_path = _resolve_ib_path(ext_ref, repo_root)
        if ib_path is not None:
            intent_id = _intent_from_ib(ib_path, repo_root)

    result: dict[str, object] = {
        "bead": bead_id,
        "intent": intent_id,
        "ib": str(ib_path) if ib_path else None,
        "attempt_id": None,
        "next_attempt_number": None,
    }
    if intent_id is not None:
        next_n = _next_attempt_number(intent_id, repo_root, run)
        result["next_attempt_number"] = next_n
        if record:
            result["attempt_id"] = _record_attempt(
                intent_id, next_n, agent, repo_root, run
            )
    return result


def cmd_resolve(args: argparse.Namespace) -> int:
    """CLI dispatcher: resolve and print the parent-Intent JSON for a bead."""
    try:
        result = resolve_parent_intent(
            args.bead_id,
            Path(args.repo_root),
            record=args.record,
            agent=args.agent,
        )
    except IntentResolutionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3 if "record-attempt" in str(exc) else 2
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="resolve_parent_intent.py",
        description="Resolve a bead's parent Intent and next attempt_number.",
    )
    parser.add_argument("bead_id", help="the bead id to resolve")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="also run `dekspec executions record-attempt` and return the id",
    )
    parser.add_argument(
        "--agent",
        default="unknown",
        help="agent/model label passed to record-attempt (with --record)",
    )
    parser.set_defaults(func=cmd_resolve)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
