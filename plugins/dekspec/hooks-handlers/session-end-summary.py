#!/usr/bin/env python3
"""DekSpec session-end summary + rotation-handoff emit hook.

Fires on Stop, SessionEnd, and PreCompact (INT-176 — PreCompact + SessionEnd
are registered so compaction-driven rotations are captured; the Stop hook fires
per-response and misses compaction).

Two responsibilities:

  1. Surface (Stop-style summary): runs `dekspec doctor --at . --json`
     and prints a one-line summary if vendoring drift or graph-level audit
     findings are worth surfacing. Stays silent when clean.
  2. Rotation-handoff emit (INT-176 / κ): writes a structured, secret-redacted
     handoff record to `dekspec/.scratch/rotation-handoff/` so a rotated or
     compacted session resumes from a DekSpec-authored record (zero dependency
     on `claude-mem`). Artifacts are referenced by path, not copied.

Never blocks. The summary half skips when the dekspec CLI is not on PATH; both
halves skip when run outside a dekspec repo (no `.dekspec-version` marker AND
no `dekspec/` artifact directory). The handoff emit is best-effort — any
failure is swallowed so it never crashes the parent lifecycle event.

Environment overrides:
    DEKSPEC_HOOK_DISABLE=1            Skip the hook entirely.
    DEKSPEC_HOOK_SUMMARY_TIMEOUT=N    doctor subprocess timeout in seconds (default: 8).
    DEKSPEC_HANDOFF_KEEP=N            Handoff records retained in .scratch/ (default: 10).
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

    cwd = Path.cwd().resolve()
    if not (cwd / ".dekspec-version").exists() and not (cwd / "dekspec").is_dir():
        # Not a dekspec consumer repo. Stay silent.
        return 0

    # Rotation-handoff emit runs whether or not the CLI is on PATH — it imports
    # the engine directly and is fully best-effort.
    _emit_handoff(cwd)

    # The doctor summary half needs the CLI on PATH.
    if shutil.which("dekspec") is None:
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
            "— run `dekspec doctor --json` for detail"
        )

    critical, important, minor = _audit_counts(payload)
    if critical + important > 0:
        messages.append(
            f"doctor findings: critical={critical} important={important} minor={minor} "
            "— run `dekspec doctor` or `/dekspec:doctor` for detail"
        )

    if not messages:
        return 0

    print("[dekspec] session-end summary:", file=sys.stderr)
    for msg in messages:
        print(f"  - {msg}", file=sys.stderr)
    return 0


def _import_handoff_engine(cwd: Path):
    """Best-effort load of the native rotation-handoff engine.

    The handlers run from the plugin tree, not the installed package. Prefer the
    in-repo source at `<repo>/tooling/dekspec/rotation_handoff.py` (loaded
    directly from its file, so it works even when a different `dekspec` package
    is already on sys.path), then fall back to a plain import. Returns the
    module or None.
    """
    src = cwd / "tooling" / "dekspec" / "rotation_handoff.py"
    if src.is_file():
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "dekspec_rotation_handoff_engine", src
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
        except Exception:
            pass
    try:
        from dekspec import rotation_handoff  # type: ignore

        return rotation_handoff
    except Exception:
        return None


def _emit_handoff(cwd: Path) -> None:
    """Write a structured, secret-redacted handoff record to .scratch/.

    Best-effort: the captured session state is assembled from environment hints
    with safe defaults, the engine applies redaction + by-path references +
    retention, and any failure is swallowed so the parent lifecycle event is
    never disturbed.
    """
    engine = _import_handoff_engine(cwd)
    if engine is None:
        return
    record = {
        "objective": os.environ.get("DEKSPEC_HANDOFF_OBJECTIVE", ""),
        "artifacts_touched": [],
        "decisions": [],
        "open_questions": [],
        "commands_run": [],
        "test_status": "",
        "files_changed": [],
        "next_safest_action": os.environ.get("DEKSPEC_HANDOFF_NEXT_ACTION", ""),
    }
    try:
        engine.write_handoff(cwd, record)
    except Exception:
        return


def _run_doctor(cwd: Path, timeout: int) -> dict | None:
    """Run `dekspec doctor --json`. Return parsed payload, or None on error/no-data."""
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
