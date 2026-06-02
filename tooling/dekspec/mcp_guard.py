"""MCP-layer secondary-gate guard for session-lifecycle enforcement (MSN-002).

Three-call surface (`is_session_active`, `guard_commit`, `guard_push`) consumed
by an MCP runtime's commit/push tool-call hooks. The guard subprocess-invokes
`dekspec session status --machine-readable`, parses the JSON envelope, and
returns a `GuardResult(allow, reason)`. Fail-closed by default: reject when no
active session, when status parsing fails, or when the CLI is absent. Honors
`DEKSPEC_BYPASS_SESSION=1` (allow + bypass-log emission) and
`DEKSPEC_MCP_GUARD_MODE=warn` (allow + warn-log emission). Bypass and warn
events route through `session_lifecycle.emit_bypass` to the canonical
`bypass.log` channel.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass

from . import session_lifecycle

_STATUS_TIMEOUT_SECONDS = 5
_GIT_CONFIG_TIMEOUT_SECONDS = 2
_TRUTHY_VALUES = ("1", "true", "yes")


@dataclass(frozen=True)
class GuardResult:
    """Result of a guard_commit / guard_push call: allow-or-reject + reason."""

    allow: bool
    reason: str


def _status_payload() -> dict | None:
    """Subprocess-invoke `dekspec session status --machine-readable`; parse JSON.

    Returns the parsed dict on success; None on any failure (missing CLI,
    timeout, non-zero exit, malformed JSON, non-dict payload). Never raises.
    """
    try:
        result = subprocess.run(
            ["dekspec", "session", "status", "--machine-readable"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_STATUS_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def is_session_active() -> bool:
    """Return True iff a non-stale session is currently active. Never raises."""
    payload = _status_payload()
    if payload is None:
        return False
    active = payload.get("active")
    stale = payload.get("stale")
    if not isinstance(active, bool) or not isinstance(stale, bool):
        return False
    return active and not stale


def _is_bypass_set() -> bool:
    return os.environ.get("DEKSPEC_BYPASS_SESSION", "").strip().lower() in _TRUTHY_VALUES


def _guard_mode() -> str:
    """Return 'reject', 'warn', or 'unsupported:<value>'."""
    raw = os.environ.get("DEKSPEC_MCP_GUARD_MODE", "").strip().lower()
    if raw == "" or raw == "reject":
        return "reject"
    if raw == "warn":
        return "warn"
    return f"unsupported:{raw}"


def _resolve_guard_operator() -> str:
    """Resolve operator for bypass-log emission when caller didn't pass one.

    Tries `git config user.email`; falls back to `$USER`; finally returns
    'unknown'. Never raises.
    """
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_CONFIG_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    return os.environ.get("USER", "unknown")


def _reject_hint(inner: str, op: str) -> str:
    return (
        f"{inner}; set `DEKSPEC_BYPASS_SESSION=1` to bypass this check "
        f"(logged to bypass.log) or run `dekspec session start <bead-id>` first"
    )


def _emit_bypass_log(operator: str, files: list[str], op: str) -> None:
    resolved = operator if operator else _resolve_guard_operator()
    session_lifecycle.emit_bypass(
        session=None,
        operator=resolved,
        files=list(files),
        reason=f"DEKSPEC_BYPASS_SESSION=1 set on MCP-routed {op}",
    )


def _emit_warn_log(operator: str, files: list[str], op: str, inner: str) -> None:
    resolved = operator if operator else _resolve_guard_operator()
    session_lifecycle.emit_bypass(
        session=None,
        operator=resolved,
        files=list(files),
        reason=f"mcp-guard warn-only: would reject MCP-routed {op} because {inner}",
    )


def _evaluate(operator: str, files: list[str], op: str) -> GuardResult:
    """Shared decision logic for guard_commit / guard_push."""
    if _is_bypass_set():
        _emit_bypass_log(operator, files, op=op)
        return GuardResult(allow=True, reason="bypass: DEKSPEC_BYPASS_SESSION set")

    payload = _status_payload()
    if payload is None:
        inner = "could not determine session state (CLI absent, timeout, or malformed payload)"
    else:
        active = payload.get("active")
        stale = payload.get("stale")
        if not isinstance(active, bool):
            inner = "malformed session-status payload (missing or non-bool `active`)"
        elif not active:
            inner = f"no active session for MCP-routed {op}"
        elif isinstance(stale, bool) and stale:
            session_id = payload.get("session_id") or "<unknown>"
            inner = (
                f"session stale: {session_id} (TTL exceeded); "
                f"run `dekspec session reap` and re-open"
            )
        else:
            session_id = payload.get("session_id") or "<unknown>"
            return GuardResult(allow=True, reason=f"session active: {session_id}")

    mode = _guard_mode()
    if mode == "warn":
        _emit_warn_log(operator, files, op=op, inner=inner)
        return GuardResult(
            allow=True,
            reason=f"warn-only mode: would reject because {inner}",
        )

    hint_msg = _reject_hint(inner, op=op)
    if mode.startswith("unsupported:"):
        raw_value = mode.split(":", 1)[1]
        prefix = (
            f"DEKSPEC_MCP_GUARD_MODE has unsupported value `{raw_value}`; "
            f"treating as reject. "
        )
        return GuardResult(allow=False, reason=prefix + hint_msg)
    return GuardResult(allow=False, reason=hint_msg)


def guard_commit(operator: str, files: list[str], message: str) -> GuardResult:
    """Pre-flight check for an MCP-routed commit. Returns allow-or-reject."""
    _ = message  # not consulted in this gate; reserved for future scope-aware policy
    return _evaluate(operator, files, op="commit")


def guard_push(remote: str, refs: list[str]) -> GuardResult:
    """Pre-flight check for an MCP-routed push. Returns allow-or-reject."""
    _ = remote
    _ = refs  # push events are not file-scoped; bypass-log files list is empty
    return _evaluate(operator="", files=[], op="push")


__all__ = [
    "GuardResult",
    "is_session_active",
    "guard_commit",
    "guard_push",
]
