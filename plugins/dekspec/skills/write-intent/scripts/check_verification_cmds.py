#!/usr/bin/env python3
"""L9 check (mechanical): every Verification `cmd:` resolves to something runnable.

The /write-intent skill must confirm, before Accept and hard before --testpass,
that each command in the Intent's `## Verification` yaml block actually points at
a runnable script or tool. This script does the *resolvability* check only — it
NEVER executes the commands (that is --testpass's job, and would be unsafe here).

Resolution rules (audit-v2 L9):
  * `pytest ...`            -> pytest must be importable / on PATH.
  * `bash scripts/x.sh`,
    `scripts/x.sh`,
    `./scripts/x.sh ...`     -> the referenced script file must exist and be
                               executable, relative to the repo root.
  * `dekspec ...`            -> the `dekspec` entry point must be on PATH.
  * anything else            -> the leading token is resolved via `shutil.which`.

A command whose script has a `<placeholder>` token (e.g. the documented
`<reproduction-test-path-from-IB-1>`) is reported as `pending`, not `unresolved`
— the skill leaves that one verbatim until --decompose fills it.

Stdlib-only. Parses a minimal subset of YAML (the fixed
`verification:\\n  - name: ...\\n    cmd: ...` shape) by hand — no PyYAML.

Runnable:   python check_verification_cmds.py <intent-path> [--repo-root DIR]
Importable: from check_verification_cmds import parse_verification, resolve_cmd
Exit codes: 0 = all resolve (pending allowed); 2 = unresolved cmd(s); 1 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import sys
from pathlib import Path

_PLACEHOLDER = re.compile(r"<[^>]+>")
_NAME_RE = re.compile(r"^\s*-?\s*name:\s*(?P<v>.+?)\s*$")
_CMD_RE = re.compile(r"^\s*-?\s*cmd:\s*(?P<v>.+?)\s*$")


def parse_verification(text: str) -> list[dict[str, str]]:
    """Extract {name, cmd} records from a `## Verification` fenced yaml block.

    Tolerates the corpus shape: a ```yaml fence containing a `verification:` (or
    bare) list of `- name:` / `cmd:` pairs. Returns records in document order.
    """
    sec = re.search(r"^#+[ \t]+Verification[ \t]*$", text, re.MULTILINE)
    if not sec:
        return []
    body = text[sec.end():]
    # Stop at the next heading. Require H2+ (`##`): a single `#` also begins
    # a YAML comment line, and the `## Verification` block's fenced yaml
    # carries comment lines like `# Verification predicate ...`. Matching
    # `#+` truncated the body before the fence — 0 records parsed.
    nxt = re.search(r"^##+[ \t]+\S", body, re.MULTILINE)
    if nxt:
        body = body[: nxt.start()]
    # Grab the first fenced block.
    fence = re.search(r"```[a-zA-Z]*\n(.*?)```", body, re.DOTALL)
    block = fence.group(1) if fence else body

    records: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in block.splitlines():
        nm = _NAME_RE.match(line)
        cm = _CMD_RE.match(line)
        if nm:
            if cur.get("cmd") is not None:
                records.append(cur)
                cur = {}
            cur["name"] = nm.group("v").strip().strip("'\"")
        elif cm:
            cur["cmd"] = cm.group("v").strip().strip("'\"")
            records.append(cur)
            cur = {}
    if cur.get("cmd") is not None:
        records.append(cur)
    return records


def resolve_cmd(cmd: str, repo_root: Path) -> str:
    """Classify a verification command. Returns 'resolved'|'unresolved'|'pending'.

    Never runs the command.
    """
    if _PLACEHOLDER.search(cmd):
        return "pending"
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return "unresolved"
    if not tokens:
        return "unresolved"

    head = tokens[0]

    # `bash scripts/x.sh` / `sh scripts/x.sh` — the real target is tokens[1].
    if head in {"bash", "sh"} and len(tokens) >= 2:
        return _resolve_script(tokens[1], repo_root, require_exec=False)

    # A direct script path.
    if head.endswith((".sh", ".py")) or head.startswith(("./", "scripts/")):
        return _resolve_script(head, repo_root, require_exec=True)

    # `pytest`, `dekspec`, or any other tool — must be on PATH.
    if shutil.which(head) is not None:
        return "resolved"
    return "unresolved"


def _resolve_script(ref: str, repo_root: Path, require_exec: bool) -> str:
    path = (repo_root / ref.lstrip("./")).resolve()
    if not path.is_file():
        return "unresolved"
    import os

    if require_exec and not os.access(path, os.X_OK):
        return "unresolved"
    return "resolved"


def check(intent_path: Path, repo_root: Path) -> dict[str, object]:
    text = intent_path.read_text(encoding="utf-8")
    records = parse_verification(text)
    classified: list[dict[str, str]] = []
    for rec in records:
        cmd = rec.get("cmd", "")
        classified.append(
            {
                "name": rec.get("name", "(unnamed)"),
                "cmd": cmd,
                "status": resolve_cmd(cmd, repo_root),
            }
        )
    unresolved = [c for c in classified if c["status"] == "unresolved"]
    pending = [c for c in classified if c["status"] == "pending"]
    return {
        "intent": str(intent_path),
        "total": len(classified),
        "checks": classified,
        "unresolved": unresolved,
        "pending": pending,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_verification_cmds.py",
        description="L9: check Verification cmd entries resolve (no execution).",
    )
    parser.add_argument("intent_path", help="Path to the Intent markdown file.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root the script paths resolve against (default: cwd).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    args = parser.parse_args(argv)

    intent_path = Path(args.intent_path)
    if not intent_path.is_file():
        print(f"ERROR: Intent file not found: {intent_path}", file=sys.stderr)
        return 1
    repo_root = Path(args.repo_root).resolve()

    result = check(intent_path, repo_root)
    unresolved = result["unresolved"]
    pending = result["pending"]

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["total"] == 0:
            print(
                "WARNING: no Verification cmd entries found.", file=sys.stderr
            )
        if not unresolved:
            extra = (
                f" ({len(pending)} pending placeholder cmd[s] left for "
                "--decompose)"
                if pending
                else ""
            )
            print(
                f"OK: all runnable Verification cmds resolve{extra}."
            )
        else:
            print(
                f"L9 FAIL: {len(unresolved)} of {result['total']} "
                "Verification cmd(s) do not resolve:",
                file=sys.stderr,
            )
            for c in unresolved:  # type: ignore[union-attr]
                print(f"  [{c['name']}] {c['cmd']}", file=sys.stderr)

    return 2 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
