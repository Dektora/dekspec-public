"""Session-lifecycle data plane — runtime session-state record under MSN-002.

Owns the SessionState dataclass, JSON serialization, file locking, TTL
semantics, and bypass-log emission. The state file lives at
XDG_STATE_HOME/dekspec/<repo-hash>/session.json with <repo-hash> =
sha256(absolute_repo_path)[:12] (worktree-aware). POSIX local filesystems
only — fcntl.flock semantics on NFS are unsupported.

NOT an L1-L4 IR; not registered in the Constraint Compiler parser
dispatch, the _detect_artifact_kind CLI table, or any SpecGraph accessor.
The schema lives at tooling/dekspec/schemas/session_state.schema.yaml for
discoverability + ADR-006 closure discipline, nothing more.
"""
from __future__ import annotations

# Advisory file locking is platform-split: POSIX has `fcntl`, Windows has
# `msvcrt`. Import both defensively so the module (and therefore the whole CLI,
# which imports it at startup) loads on either OS.
try:
    import fcntl  # POSIX-only; absent on Windows.
except ImportError:  # pragma: no cover - Windows has no fcntl
    fcntl = None  # type: ignore[assignment]
try:
    import msvcrt  # Windows-only; absent on POSIX.
except ImportError:  # pragma: no cover - POSIX has no msvcrt
    msvcrt = None  # type: ignore[assignment]
import hashlib
import json
import os
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "session_state.schema.yaml"
_SESSION_STATE_SCHEMA: dict[str, Any] = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SESSION_STATE_SCHEMA)

_DEFAULT_TTL_HOURS = 4
_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_INTENT_ID_PATTERN = "INT-"


class SessionStateValidationError(Exception):
    """Raised on schema-validation failure, malformed env vars, or missing operator."""


class SessionAlreadyActiveError(Exception):
    """Raised by start() when a non-expired session already exists."""


@dataclass
class SessionState:
    """Runtime record of an open session. Mirrors session_state.schema.yaml."""

    session_id: str
    branch: str
    start_ts: str
    operator: str
    commits: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    bypass_count: int = 0
    bypass_reasons: list[dict[str, Any]] = field(default_factory=list)
    off_spec_commits: list[dict[str, Any]] = field(default_factory=list)
    ir_schema_version: str = "0.1.0"
    bound_bead_id: str | None = None
    bound_intent_id: str | None = None
    end_ts: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().strftime(_TS_FORMAT)


def _resolve_xdg_state_home() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    if xdg:
        return Path(xdg)
    return Path.home() / ".local" / "state"


def _repo_hash() -> str:
    """sha256(absolute_repo_path)[:12]; falls back to cwd realpath when not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            repo_path = str(Path(result.stdout.strip()).resolve())
        else:
            repo_path = str(Path.cwd().resolve())
    except (FileNotFoundError, OSError):
        repo_path = str(Path.cwd().resolve())
    return hashlib.sha256(repo_path.encode("utf-8")).hexdigest()[:12]


def _state_dir() -> Path:
    return _resolve_xdg_state_home() / "dekspec" / _repo_hash()


def _session_state_path() -> Path:
    return _state_dir() / "session.json"


def _bypass_log_path() -> Path:
    return _state_dir() / "bypass.log"


def _lock_path() -> Path:
    return _state_dir() / ".lock"


def _resolve_ttl_hours() -> int:
    raw = os.environ.get("DEKSPEC_SESSION_TTL_HOURS")
    if raw is None:
        return _DEFAULT_TTL_HOURS
    try:
        value = int(raw)
    except ValueError as e:
        raise SessionStateValidationError(
            f"DEKSPEC_SESSION_TTL_HOURS must be a positive integer; got: {raw!r}"
        ) from e
    if value <= 0:
        raise SessionStateValidationError(
            f"DEKSPEC_SESSION_TTL_HOURS must be a positive integer; got: {raw!r}"
        )
    return value


def _resolve_operator(supplied: str | None) -> str:
    if supplied:
        return supplied
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError) as e:
        raise SessionStateValidationError(
            "Operator not supplied and git is unavailable. Pass operator= explicitly."
        ) from e
    email = result.stdout.strip()
    if result.returncode != 0 or not email:
        raise SessionStateValidationError(
            "Operator not supplied and git config user.email is unset. "
            "Pass operator= explicitly."
        )
    return email


def _ensure_state_dir() -> Path:
    d = _state_dir()
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir respects existing mode; chmod for safety on pre-existing dirs.
    try:
        d.chmod(0o700)
    except PermissionError:
        pass
    return d


def _lock_exclusive(fd: int) -> None:
    """Acquire an exclusive advisory lock on `fd` (cross-platform).

    POSIX uses ``fcntl.flock``; Windows uses ``msvcrt.locking`` (a 1-byte
    region at offset 0). If neither is available the lock is a best-effort
    no-op — session state is single-user and local, so its absence only
    forgoes the guard against the rare concurrent-write race.
    """
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)
    elif msvcrt is not None:  # pragma: no cover - exercised on Windows only
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)


def _unlock(fd: int) -> None:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_UN)
    elif msvcrt is not None:  # pragma: no cover - exercised on Windows only
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


@contextmanager
def _acquire_lock() -> Iterator[None]:
    _ensure_state_dir()
    lock_path = _lock_path()
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock_exclusive(fd)
        yield
    finally:
        try:
            _unlock(fd)
        finally:
            os.close(fd)


def _state_to_dict(state: SessionState) -> dict[str, Any]:
    d = asdict(state)
    return {k: v for k, v in d.items() if v is not None}


def _to_json(state: SessionState) -> str:
    payload = _state_to_dict(state)
    _VALIDATOR.validate(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
        ensure_ascii=False,
    ) + "\n"


def _from_json(text: str) -> SessionState:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SessionStateValidationError(f"corrupted session.json: {e}") from e
    try:
        _VALIDATOR.validate(data)
    except ValidationError as e:
        raise SessionStateValidationError(f"session.json fails schema: {e.message}") from e
    return SessionState(
        session_id=data["session_id"],
        branch=data["branch"],
        start_ts=data["start_ts"],
        operator=data["operator"],
        commits=list(data.get("commits", [])),
        files_touched=list(data.get("files_touched", [])),
        bypass_count=int(data.get("bypass_count", 0)),
        bypass_reasons=list(data.get("bypass_reasons", [])),
        off_spec_commits=list(data.get("off_spec_commits", [])),
        ir_schema_version=data.get("ir_schema_version", "0.1.0"),
        bound_bead_id=data.get("bound_bead_id"),
        bound_intent_id=data.get("bound_intent_id"),
        end_ts=data.get("end_ts"),
    )


def _save_session(state: SessionState) -> None:
    _ensure_state_dir()
    path = _session_state_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(_to_json(state), encoding="utf-8")
    os.replace(tmp, path)


def _load_session() -> SessionState | None:
    path = _session_state_path()
    if not path.exists():
        return None
    return _from_json(path.read_text(encoding="utf-8"))


def _delete_session_file() -> None:
    path = _session_state_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _parse_iso(ts: str) -> datetime:
    return datetime.strptime(ts, _TS_FORMAT).replace(tzinfo=timezone.utc)


def _is_stale(state: SessionState, now: datetime) -> bool:
    age = now - _parse_iso(state.start_ts)
    return age > timedelta(hours=_resolve_ttl_hours())


def _route_id(bound_id: str) -> tuple[str | None, str | None]:
    """Returns (bound_bead_id, bound_intent_id) per the routing rule."""
    if bound_id.startswith(_INTENT_ID_PATTERN) and len(bound_id) >= len("INT-") + 3:
        suffix = bound_id[len("INT-"):]
        if suffix.isdigit():
            return None, bound_id
    return bound_id, None


def _bound_display(state: SessionState) -> str:
    parts = []
    if state.bound_intent_id:
        parts.append(state.bound_intent_id)
    if state.bound_bead_id:
        parts.append(state.bound_bead_id)
    return " / ".join(parts) if parts else "<unbound>"


def start(
    bound_id: str,
    branch: str,
    *,
    operator: str | None = None,
) -> SessionState:
    """Open a new session. Raises SessionAlreadyActiveError if one already exists."""
    if not bound_id:
        raise SessionStateValidationError("bound_id is required")
    if not branch:
        raise SessionStateValidationError("branch is required")
    resolved_operator = _resolve_operator(operator)
    with _acquire_lock():
        existing = _load_session()
        if existing is not None and not _is_stale(existing, _now()):
            raise SessionAlreadyActiveError(
                f"Session already active for {_bound_display(existing)} "
                f"(started {existing.start_ts}). "
                "Run `dekspec session end` or `dekspec session reap` first."
            )
        if existing is not None:
            _delete_session_file()
        bead_id, intent_id = _route_id(bound_id)
        state = SessionState(
            session_id=str(uuid.uuid4()),
            branch=branch,
            start_ts=_now_iso(),
            operator=resolved_operator,
            bound_bead_id=bead_id,
            bound_intent_id=intent_id,
        )
        _save_session(state)
        return state


def end(reason: str | None = None) -> SessionState:
    """Close the active session, returning the final state and deleting the file."""
    _ = reason  # reserved for INT-009 CLI surface; not persisted in this Intent
    with _acquire_lock():
        state = _load_session()
        if state is None:
            raise FileNotFoundError(
                f"No active session at {_session_state_path()}"
            )
        state.end_ts = _now_iso()
        _save_session(state)
        _delete_session_file()
        return state


def status(machine_readable: bool = False) -> dict[str, Any] | str:
    """Inspect the active session (no lock — reads only)."""
    state = _load_session()
    if state is None:
        if machine_readable:
            return {
                "active": False,
                "session_id": None,
                "bound_bead_id": None,
                "bound_intent_id": None,
                "branch": None,
                "start_ts": None,
                "stale": False,
            }
        return "No active session."
    stale = _is_stale(state, _now())
    if machine_readable:
        return {
            "active": True,
            "session_id": state.session_id,
            "bound_bead_id": state.bound_bead_id,
            "bound_intent_id": state.bound_intent_id,
            "branch": state.branch,
            "start_ts": state.start_ts,
            "stale": stale,
        }
    if stale:
        age_hours = (_now() - _parse_iso(state.start_ts)).total_seconds() / 3600
        return (
            f"Stale session {state.session_id} bound to {_bound_display(state)} "
            f"(started {state.start_ts}, age {age_hours:.1f}h, TTL exceeded). "
            "Run `dekspec session reap` to clear."
        )
    return (
        f"Active session {state.session_id} bound to {_bound_display(state)} "
        f"on branch {state.branch} (started {state.start_ts})."
    )


def reap(now: datetime | None = None) -> SessionState | None:
    """Remove a stale session. Returns the reaped state, or None if no stale session."""
    evaluation_time = now if now is not None else _now()
    with _acquire_lock():
        state = _load_session()
        if state is None:
            return None
        if not _is_stale(state, evaluation_time):
            return None
        _delete_session_file()
        return state


def emit_bypass(
    session: SessionState | None,
    operator: str,
    files: list[str],
    reason: str,
) -> None:
    """Append one NDJSON row to bypass.log; mirror to in-line state if session given."""
    if not operator:
        raise SessionStateValidationError("operator is required for emit_bypass")
    if not reason:
        raise SessionStateValidationError("reason is required for emit_bypass")
    row = {
        "ts": _now_iso(),
        "session_id": session.session_id if session is not None else None,
        "operator": operator,
        "files": list(files),
        "reason": reason,
    }
    _ensure_state_dir()
    log_path = _bypass_log_path()
    line = (json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    if session is not None:
        with _acquire_lock():
            current = _load_session()
            if current is not None and current.session_id == session.session_id:
                current.bypass_count += 1
                current.bypass_reasons.append(row)
                _save_session(current)
                session.bypass_count = current.bypass_count
                session.bypass_reasons = list(current.bypass_reasons)


def emit_off_spec(
    commit_sha: str,
    off_spec_files: list[str],
    claimed_intent: str | None,
    reason: str,
) -> None:
    """Append one off-spec record to the active session's off_spec_commits log.

    Mirrors emit_bypass's lock + load + save discipline. No-op (returns
    silently, no exception) when no session is active — the INT-053
    pre-commit hook calls this unconditionally, including the
    no-claimed-bead case where there is no session to record into.
    `commit_sha` is the literal "pending" when called from a pre-commit
    hook (the commit does not exist yet).
    """
    with _acquire_lock():
        state = _load_session()
        if state is None:
            return
        state.off_spec_commits.append(
            {
                "ts": _now_iso(),
                "commit_sha": commit_sha,
                "off_spec_files": list(off_spec_files),
                "claimed_intent": claimed_intent,
                "reason": reason,
            }
        )
        _save_session(state)


def load_active_session() -> SessionState | None:
    """Public accessor for the active session record (None when absent).

    Thin public wrapper over the data-plane loader so CLI dispatchers can
    obtain a SessionState without reaching into an underscore-prefixed
    helper (WS-012 BR9). Reads only — no lock, no mutation.
    """
    return _load_session()


__all__ = [
    "SessionState",
    "SessionStateValidationError",
    "SessionAlreadyActiveError",
    "start",
    "end",
    "status",
    "reap",
    "emit_bypass",
    "emit_off_spec",
    "load_active_session",
]
