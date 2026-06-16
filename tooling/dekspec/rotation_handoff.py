"""Native DekSpec rotation-handoff engine (INT-176 / κ).

DekSpec session continuity owned natively, with **zero runtime dependency** on
the external ``claude-mem`` plugin (MSN-020 D13). This module is the runnable
core: it writes a structured handoff record at session end and reads the most
recent one back at session start, so a rotated/compacted session resumes from a
DekSpec-authored record rather than starting cold.

Records land in the ephemeral, gitignored governed zone introduced by INT-165
(α) / ADR-040: ``<root>/dekspec/.scratch/rotation-handoff/``. Each record is a
JSON file named ``handoff-<UTC-timestamp>.json``.

Three guarantees the write path upholds:

1. **Secret-redaction** — every string in the record is passed through a fixed
   initial redaction pattern set before write, so tokens / keys / env-secret
   assignments never land in ``.scratch/``. Extend ``_REDACTION_PATTERNS`` to
   broaden coverage.
2. **Artifacts by reference, not by value** — ``artifacts_touched`` and
   ``files_changed`` carry repo-relative *path strings*; this module never reads
   or inlines artifact file bodies.
3. **Bounded retention** — after each write, only the newest ``keep`` records
   are retained (default 10; ``DEKSPEC_HANDOFF_KEEP`` env override); older ones
   are pruned by mtime. ``read_latest_handoff`` selects the newest by mtime.

This module imports nothing from ``claude-mem`` and requires nothing from it.
When both are installed they coexist without coordination — rotation-handoff is
authoritative for DekSpec continuity and reads/writes only its own store.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "HANDOFF_FIELDS",
    "REDACTED",
    "write_handoff",
    "read_latest_handoff",
]

# The eight required structured-handoff fields (INT-176 §Outcome Verification).
HANDOFF_FIELDS: tuple[str, ...] = (
    "objective",
    "artifacts_touched",
    "decisions",
    "open_questions",
    "commands_run",
    "test_status",
    "files_changed",
    "next_safest_action",
)

# Fields that are lists of strings (vs scalar strings).
_LIST_FIELDS: frozenset[str] = frozenset(
    {"artifacts_touched", "decisions", "open_questions", "commands_run", "files_changed"}
)

REDACTED = "[REDACTED]"

_SUBDIR = ("dekspec", ".scratch", "rotation-handoff")
_DEFAULT_KEEP = 10

# Fixed initial secret-redaction pattern set (INT-176 Open Issue — resolved at
# --decompose). Each entry is (compiled regex, replacement). Documented
# expansion point: append patterns here.
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # (a) shell-style KEY=value where KEY names a secret-bearing variable.
    (
        re.compile(
            r"\b([A-Za-z_][A-Za-z0-9_]*?"
            r"(?:_SECRET|_TOKEN|_KEY|_PASSWORD|_PASSWD|_API[A-Za-z0-9_]*))"
            r"\s*=\s*\S+",
            re.IGNORECASE,
        ),
        rf"\1={REDACTED}",
    ),
    # (b) bearer-token-looking blobs.
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), REDACTED),  # GitHub tokens
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), REDACTED),  # OpenAI-style keys
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), REDACTED),  # Slack tokens
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED),  # AWS access key ids
    # standalone long base64/hex runs (>= 32 chars) — likely a key/digest.
    (re.compile(r"\b[A-Za-z0-9+/=]{32,}\b"), REDACTED),
)


def _redact(value: str) -> str:
    """Apply the fixed redaction pattern set to a single string."""
    for pattern, repl in _REDACTION_PATTERNS:
        value = pattern.sub(repl, value)
    return value


def _redact_obj(obj):
    """Recursively redact every string inside a JSON-serializable structure."""
    if isinstance(obj, str):
        return _redact(obj)
    if isinstance(obj, list):
        return [_redact_obj(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _redact_obj(v) for k, v in obj.items()}
    return obj


def _normalize(record: dict) -> dict:
    """Coerce an arbitrary record dict to exactly the eight required fields.

    Missing list fields default to ``[]``; missing scalar fields to ``""``.
    Extra keys are dropped — the on-disk record is a stable, known shape.
    """
    out: dict = {}
    for field in HANDOFF_FIELDS:
        raw = record.get(field)
        if field in _LIST_FIELDS:
            if raw is None:
                out[field] = []
            elif isinstance(raw, list):
                out[field] = [str(v) for v in raw]
            else:
                out[field] = [str(raw)]
        else:
            out[field] = "" if raw is None else str(raw)
    return out


def _scratch_dir(root: Path) -> Path:
    return Path(root).joinpath(*_SUBDIR)


def _keep_limit(keep: int) -> int:
    env = os.environ.get("DEKSPEC_HANDOFF_KEEP")
    if env:
        try:
            keep = int(env)
        except ValueError:
            pass
    return max(1, keep)


def write_handoff(root: Path, record: dict, *, keep: int = _DEFAULT_KEEP) -> Path:
    """Write a redacted structured handoff record under the scratch zone.

    The record is normalized to the eight required fields, every string is
    secret-redacted, and the result is written as JSON to
    ``<root>/dekspec/.scratch/rotation-handoff/handoff-<ts>.json``. After the
    write, older records beyond ``keep`` are pruned by mtime. Returns the path
    of the written record.
    """
    out_dir = _scratch_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)

    normalized = _normalize(record)
    redacted = _redact_obj(normalized)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_path = out_dir / f"handoff-{ts}.json"
    out_path.write_text(
        json.dumps(redacted, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    _prune(out_dir, _keep_limit(keep))
    return out_path


def _records(out_dir: Path) -> list[Path]:
    if not out_dir.is_dir():
        return []
    return sorted(
        out_dir.glob("handoff-*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _prune(out_dir: Path, keep: int) -> None:
    """Best-effort retention prune: keep the newest ``keep`` records by mtime."""
    for stale in _records(out_dir)[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def read_latest_handoff(root: Path) -> dict | None:
    """Return the newest handoff record (by mtime), or None if none/unreadable."""
    records = _records(_scratch_dir(root))
    if not records:
        return None
    try:
        data = json.loads(records[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
