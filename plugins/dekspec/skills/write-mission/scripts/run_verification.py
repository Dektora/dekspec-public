#!/usr/bin/env python3
"""Execute a Mission's Verification predicate for /write-mission --complete.

Complete Mode's promotion gate runs every `cmd:` in the Mission's
`### Mission Verification` yaml block and fast-fails on the first non-zero
exit. This script does exactly that: it parses the block, runs each command in
order from the repo root, and stops at the first failure, returning the failing
record (name, cmd, exit code, captured tail of stdout/stderr).

Unlike the sibling `check_verification_cmds.py` (which only checks
*resolvability* and never executes anything), this script DOES execute the
commands — that is its job, and it is only invoked by Complete Mode. Commands
are run with `subprocess.run` over a tokenised argv (`shlex.split`); `shell=True`
is never used.

A command containing an unresolved `<placeholder>` is a hard configuration
error (a Mission should not reach --complete with placeholders) — the script
fast-fails on it without executing.

Stdlib-only. Importable + argparse CLI.

Runnable:   python run_verification.py <mission-path> [--repo-root DIR]
                                       [--timeout SECONDS]
Importable: from run_verification import run_mission_verification
Exit codes: 0 = all checks passed; 2 = a check failed; 1 = usage/parse error.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

_PLACEHOLDER = re.compile(r"<[^>]+>")
DEFAULT_TIMEOUT = 600  # seconds, per individual command


def _unquote(value: str) -> str:
    """Strip a *matched* enclosing quote pair only.

    `value.strip("'\"")` removes leading/trailing quote characters
    indiscriminately, which corrupts a cmd like `sh -c '...'` (no leading
    quote, trailing `'`) into an untokenisable fragment. Only strip when the
    string is wholly enclosed by the same quote character.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_mission_verification(text: str) -> list[dict[str, str]]:
    """Extract {name, cmd} records from the `### Mission Verification` block."""
    m = re.search(
        r"^#+[ \t]+Mission Verification[ \t]*$", text, re.MULTILINE
    )
    if not m:
        return []
    body = text[m.end():]
    nxt = re.search(r"^#+[ \t]+\S", body, re.MULTILINE)
    if nxt:
        body = body[: nxt.start()]
    fence = re.search(r"```[a-zA-Z]*\n(.*?)```", body, re.DOTALL)
    block = fence.group(1) if fence else body

    records: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in block.splitlines():
        nm = re.match(r"^\s*-?\s*name:\s*(?P<v>.+?)\s*$", line)
        cm = re.match(r"^\s*-?\s*cmd:\s*(?P<v>.+?)\s*$", line)
        if nm:
            if "cmd" in cur:
                records.append(cur)
                cur = {}
            cur["name"] = _unquote(nm.group("v").strip())
        elif cm:
            cur["cmd"] = _unquote(cm.group("v").strip())
            records.append(cur)
            cur = {}
    if "cmd" in cur:
        records.append(cur)
    return records


def _tail(text: str, lines: int = 20) -> str:
    return "\n".join(text.splitlines()[-lines:])


def run_mission_verification(
    mission_path: Path,
    repo_root: Path,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, object]:
    """Run each Mission Verification cmd in order, fast-failing on first error.

    Returns {passed: bool, ran: [...], failing: {...} | None}.
    """
    text = mission_path.read_text(encoding="utf-8")
    records = parse_mission_verification(text)

    ran: list[dict[str, object]] = []
    for rec in records:
        name = rec.get("name", "(unnamed)")
        cmd = rec.get("cmd", "")

        if _PLACEHOLDER.search(cmd):
            failing = {
                "name": name,
                "cmd": cmd,
                "exit_code": None,
                "error": "unresolved <placeholder> in cmd",
            }
            return {"passed": False, "ran": ran, "failing": failing}

        try:
            argv = shlex.split(cmd)
        except ValueError as exc:
            failing = {
                "name": name,
                "cmd": cmd,
                "exit_code": None,
                "error": f"cmd does not tokenise: {exc}",
            }
            return {"passed": False, "ran": ran, "failing": failing}
        if not argv:
            continue

        try:
            proc = subprocess.run(  # noqa: S603 - list argv, no shell
                argv,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            failing = {
                "name": name,
                "cmd": cmd,
                "exit_code": None,
                "error": f"command not found: {argv[0]}",
            }
            return {"passed": False, "ran": ran, "failing": failing}
        except subprocess.TimeoutExpired:
            failing = {
                "name": name,
                "cmd": cmd,
                "exit_code": None,
                "error": f"timed out after {timeout}s",
            }
            return {"passed": False, "ran": ran, "failing": failing}

        entry = {"name": name, "cmd": cmd, "exit_code": proc.returncode}
        ran.append(entry)
        if proc.returncode != 0:
            failing = {
                "name": name,
                "cmd": cmd,
                "exit_code": proc.returncode,
                "stdout_tail": _tail(proc.stdout),
                "stderr_tail": _tail(proc.stderr),
            }
            return {"passed": False, "ran": ran, "failing": failing}

    return {"passed": True, "ran": ran, "failing": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_verification.py",
        description="Execute a Mission's Verification predicate (Complete Mode).",
    )
    parser.add_argument("mission_path", help="Path to the Mission markdown file.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Working directory for command execution (default: cwd).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-command timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    args = parser.parse_args(argv)

    mission_path = Path(args.mission_path)
    if not mission_path.is_file():
        print(f"ERROR: Mission file not found: {mission_path}", file=sys.stderr)
        return 1
    repo_root = Path(args.repo_root).resolve()

    result = run_mission_verification(mission_path, repo_root, args.timeout)
    print(json.dumps(result, indent=2))

    if result["passed"]:
        return 0
    failing = result["failing"]
    if isinstance(failing, dict):
        print(
            f"VERIFICATION FAILED: [{failing.get('name')}] "
            f"{failing.get('cmd')}",
            file=sys.stderr,
        )
        if failing.get("error"):
            print(f"  {failing['error']}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
