#!/usr/bin/env python3
"""DekSpec session-end summary hook.

Fires on Stop. Runs `dekspec audit doctor --at . --json` and prints a
one-line summary if anything is worth surfacing:

  - vendoring drift detected by the doctor's verify-vendored section.
  - graph-level audit linkage findings.

Stays silent when both are clean. Never blocks. Skips entirely when the
dekspec CLI is not on PATH or when run outside a dekspec consumer repo
(no `.dekspec-version` marker AND no `dekspec/` artifact directory).

Environment overrides:
    DEKSPEC_HOOK_DISABLE=1            Skip the hook entirely.
    DEKSPEC_HOOK_SUMMARY_TIMEOUT=N    doctor subprocess timeout in seconds (default: 8).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if os.environ.get("DEKSPEC_HOOK_DISABLE") == "1":
        return 0
    if shutil.which("dekspec") is None:
        return 0

    cwd = Path.cwd().resolve()
    if not (cwd / ".dekspec-version").exists() and not (cwd / "dekspec").is_dir():
        # Not a dekspec consumer repo. Stay silent.
        return 0

    try:
        timeout = int(os.environ.get("DEKSPEC_HOOK_SUMMARY_TIMEOUT", "8"))
    except ValueError:
        timeout = 8

    payload = _run_doctor(cwd, timeout)
    if payload is None:
        return 0

    messages: list[str] = []

    drift_count = _drift_count(payload)
    if drift_count > 0:
        messages.append(
            f"vendored content drift: {drift_count} finding(s) "
            "— run `dekspec audit doctor --json` for detail"
        )

    critical, important, minor = _audit_counts(payload)
    if critical + important > 0:
        messages.append(
            f"doctor findings: critical={critical} important={important} minor={minor} "
            "— run `dekspec audit doctor` or `/dekspec:doctor` for detail"
        )

    if not messages:
        return 0

    print("[dekspec] session-end summary:", file=sys.stderr)
    for msg in messages:
        print(f"  - {msg}", file=sys.stderr)
    return 0


def _run_doctor(cwd: Path, timeout: int) -> dict | None:
    """Run `dekspec audit doctor --json`. Return parsed payload, or None on error/no-data."""
    try:
        proc = subprocess.run(
            ["dekspec", "audit", "doctor", "--at", str(cwd), "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _drift_count(payload: dict) -> int:
    """Extract verify-vendored section finding count from doctor JSON."""
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return 0
    for section in sections:
        if not isinstance(section, dict):
            continue
        if section.get("name") == "verify-vendored":
            return int(section.get("findings_count") or 0)
    return 0


def _audit_counts(payload: dict) -> tuple[int, int, int]:
    """Extract (critical, important, minor) finding counts from doctor JSON.

    Defensive: doctor JSON shape varies across versions; return zeros on any
    structural mismatch so the hook never crashes the parent Stop event.
    """
    audit = payload.get("audit_linkage") if isinstance(payload, dict) else None
    if not isinstance(audit, dict):
        return 0, 0, 0
    return (
        int(audit.get("critical") or 0),
        int(audit.get("important") or 0),
        int(audit.get("minor") or 0),
    )


if __name__ == "__main__":
    sys.exit(main())
