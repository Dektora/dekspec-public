#!/usr/bin/env python3
"""Mechanical Mission audit checks for the /write-mission --audit mode.

Runs the three deterministic checks --audit would otherwise spell out as prose
and emits JSON findings grouped by severity. The model still PRESENTS and JUDGES
the result (e.g. whether a MINOR stale-ACTIVE finding warrants a kill); this
script only does the mechanical work:

  L8  — Mission <-> Intent bidirectional linkage. For each row in the Mission's
        `### Intent queue` table: (a) the INT-NNN resolves to an Intent file;
        (b) that Intent's `## Mission` field back-points at this Mission.
  L9  — every `cmd:` in the `### Mission Verification` yaml block resolves to a
        runnable script/tool (resolvability only — NO execution here).
  L11 — stale-ACTIVE: Status ACTIVE and `Modified` (or `Created` fallback) is
        older than 90 days.

Severity mapping: L8 link breaks -> P1 (critical); L9 unresolved cmd -> P2
(important); L11 stale -> P3 (minor).

Stdlib-only. Importable + argparse CLI.

Runnable:   python mission_audit.py <mission-path> [--repo-root DIR]
Importable: from mission_audit import audit_mission
Exit codes: 0 = no P1 findings; 2 = at least one P1; 1 = error.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shlex
import shutil
import sys
from pathlib import Path

STALE_DAYS = 90

_PLACEHOLDER = re.compile(r"<[^>]+>")


def _unquote(value: str) -> str:
    """Strip a *matched* enclosing quote pair only.

    `value.strip("'\"")` removes leading/trailing quote characters
    indiscriminately, which corrupts a cmd like `sh -c '...'` (no leading
    quote, trailing `'`). Only strip when wholly enclosed by one quote char.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value
_INT_REF = re.compile(r"INT-(\d+)", re.IGNORECASE)


def _inline_field(text: str, field: str) -> str | None:
    m = re.search(
        rf"^\*\*{re.escape(field)}:\*\*[ \t]*(?P<v>.+?)[ \t]*$",
        text,
        re.MULTILINE,
    )
    return m.group("v").strip() if m else None


def _section_body(text: str, heading: str) -> str:
    """Return the body between `### heading` and the next heading of any level."""
    m = re.search(
        rf"^#+[ \t]+{re.escape(heading)}[ \t]*$", text, re.MULTILINE
    )
    if not m:
        return ""
    body = text[m.end():]
    nxt = re.search(r"^#+[ \t]+\S", body, re.MULTILINE)
    return body[: nxt.start()] if nxt else body


def parse_intent_queue(text: str) -> list[dict[str, str]]:
    """Return {int_id, status} rows from the `### Intent queue` markdown table."""
    body = _section_body(text, "Intent queue")
    rows: list[dict[str, str]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0].lower() in {"int", ""}:
            continue
        if set(cells[0]) <= {"-", ":", " "}:  # separator row
            continue
        ref = _INT_REF.search(cells[0])
        if not ref:
            continue
        status = ""
        # Status is conventionally the 4th column; fall back to a scan.
        if len(cells) >= 4:
            status = cells[3]
        rows.append(
            {"int_id": f"INT-{ref.group(1)}", "status": status.upper()}
        )
    return rows


def parse_verification_cmds(text: str) -> list[dict[str, str]]:
    body = _section_body(text, "Mission Verification")
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


def resolve_cmd(cmd: str, repo_root: Path) -> str:
    """'resolved' | 'unresolved' | 'pending' — never executes the command."""
    if _PLACEHOLDER.search(cmd):
        return "pending"
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return "unresolved"
    if not tokens:
        return "unresolved"
    head = tokens[0]
    if head in {"bash", "sh"} and len(tokens) >= 2:
        path = (repo_root / tokens[1].lstrip("./")).resolve()
        return "resolved" if path.is_file() else "unresolved"
    if head.endswith((".sh", ".py")) or head.startswith(("./", "scripts/")):
        import os

        path = (repo_root / head.lstrip("./")).resolve()
        if path.is_file() and os.access(path, os.X_OK):
            return "resolved"
        return "unresolved"
    return "resolved" if shutil.which(head) else "unresolved"


def _mission_id(text: str, mission_path: Path) -> str:
    mid = _inline_field(text, "Mission ID")
    if mid:
        return mid.strip("`")
    fm = re.search(r"MSN-(\d+)", mission_path.name, re.IGNORECASE)
    return f"MSN-{fm.group(1)}" if fm else mission_path.stem


def _parse_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not m:
        return None
    try:
        return datetime.date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def audit_mission(
    mission_path: Path,
    repo_root: Path,
    today: datetime.date | None = None,
) -> dict[str, object]:
    """Run L8 / L9 / L11. Return findings grouped by severity."""
    today = today or datetime.date.today()
    text = mission_path.read_text(encoding="utf-8")
    mission_id = _mission_id(text, mission_path)
    status = (_inline_field(text, "Status") or "").upper()

    findings: dict[str, list[dict[str, str]]] = {"P1": [], "P2": [], "P3": []}

    # --- L8 bidirectional linkage ---
    intents_dir = repo_root / "dekspec" / "intents"
    for row in parse_intent_queue(text):
        int_id = row["int_id"]
        matches = (
            sorted(intents_dir.glob(f"{int_id}-*.md"))
            if intents_dir.is_dir()
            else []
        )
        if not matches:
            findings["P1"].append(
                {
                    "rule": "L8-MSN-INT-EXISTS",
                    "detail": f"{int_id} in Intent queue resolves to no file.",
                }
            )
            continue
        int_text = matches[0].read_text(encoding="utf-8")
        back = re.search(
            r"^#+[ \t]+Mission[ \t]*$\n+(?P<v>.+)$",
            int_text,
            re.MULTILINE,
        )
        back_val = back.group("v").strip() if back else ""
        if mission_id.upper() not in back_val.upper():
            findings["P1"].append(
                {
                    "rule": "L8-MSN-INT-MIRROR",
                    "detail": (
                        f"{int_id} does not back-point at {mission_id} "
                        f"(its Mission field reads '{back_val or 'none'}')."
                    ),
                }
            )

    # --- L9 verification cmd-resolve ---
    for rec in parse_verification_cmds(text):
        cmd = rec.get("cmd", "")
        if resolve_cmd(cmd, repo_root) == "unresolved":
            findings["P2"].append(
                {
                    "rule": "L9-MSN-CMD-RESOLVE",
                    "detail": (
                        f"Mission Verification cmd does not resolve: "
                        f"[{rec.get('name', '?')}] {cmd}"
                    ),
                }
            )

    # --- L11 stale-ACTIVE ---
    if status == "ACTIVE":
        ref_date = _parse_date(_inline_field(text, "Modified")) or _parse_date(
            _inline_field(text, "Created")
        )
        if ref_date and (today - ref_date).days > STALE_DAYS:
            findings["P3"].append(
                {
                    "rule": "L11-MSN-STALE",
                    "detail": (
                        f"ACTIVE for {(today - ref_date).days} days since "
                        "last modification (>90)."
                    ),
                }
            )

    return {
        "mission": str(mission_path),
        "mission_id": mission_id,
        "status": status,
        "findings": findings,
        "counts": {sev: len(v) for sev, v in findings.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mission_audit.py",
        description="Mechanical L8/L9/L11 Mission audit; emits JSON findings.",
    )
    parser.add_argument("mission_path", help="Path to the Mission markdown file.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root for Intent + script resolution (default: cwd).",
    )
    args = parser.parse_args(argv)

    mission_path = Path(args.mission_path)
    if not mission_path.is_file():
        print(f"ERROR: Mission file not found: {mission_path}", file=sys.stderr)
        return 1
    repo_root = Path(args.repo_root).resolve()

    result = audit_mission(mission_path, repo_root)
    print(json.dumps(result, indent=2))
    counts = result["counts"]
    return 2 if counts["P1"] else 0  # type: ignore[index]


if __name__ == "__main__":
    sys.exit(main())
