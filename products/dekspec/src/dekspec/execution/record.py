"""Append-only execution record for one work contract (ADR-056).

An execution record holds everything that happens while an Implementation
Brief is carried out — ownership, the executor's revisable plan and tasks,
attempts, blockers, deviations, acceptance baselines, evidence, review
verdicts, and completion. It deliberately lives *beside* the governed
specification corpus, not inside it: ``<repo>/.dekspec/execution/<ID>/``.
Nothing here is compiled into IR or projected into agent instructions.

The record is a JSON-lines event log. Each event carries the SHA-256 of the
previous event, so a hand edit, a deleted line, or a spliced-in event breaks
the chain and is detected by :func:`verify_chain`. That makes the record
tamper-*evident* for anyone re-reading it (a reviewer, CI); it is not an
isolation boundary against an agent that can run this module itself —
see ADR-057 for where independent control actually comes from.

Current state is never stored separately: callers fold the events
(:mod:`dekspec.execution.state`). One source, no status to keep in sync.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]

__all__ = [
    "EXECUTION_DIRNAME",
    "Event",
    "ExecutionRecord",
    "RecordIntegrityError",
    "execution_root",
]

#: Repo-relative home of every execution record. Committed durable state
#: (the `.dekspec/` zoning rule), excluded from the implementation
#: fingerprint so recording evidence never invalidates it.
EXECUTION_DIRNAME = ".dekspec/execution"

_RECORD_FILENAME = "record.jsonl"


class RecordIntegrityError(RuntimeError):
    """The event chain is broken (edited, truncated, reordered or spliced)."""


@dataclass(frozen=True)
class Event:
    seq: int
    ts: str
    type: str
    actor: str
    data: dict[str, Any]
    prev: str | None
    hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "type": self.type,
            "actor": self.actor,
            "data": self.data,
            "prev": self.prev,
            "hash": self.hash,
        }


def execution_root(repo_root: Path) -> Path:
    return Path(repo_root) / EXECUTION_DIRNAME


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _event_hash(seq: int, ts: str, type_: str, actor: str, data: dict[str, Any], prev: str | None) -> str:
    body = {"seq": seq, "ts": ts, "type": type_, "actor": actor, "data": data, "prev": prev}
    return hashlib.sha256(_canonical(body)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows only
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        yield
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)


class ExecutionRecord:
    """The event log for one work contract (an IB, or an Intent's outcome run)."""

    def __init__(self, repo_root: Path, artifact_id: str) -> None:
        self.repo_root = Path(repo_root)
        self.artifact_id = artifact_id
        self.dir = execution_root(self.repo_root) / artifact_id
        self.path = self.dir / _RECORD_FILENAME
        self._held = False

    # -- reading ---------------------------------------------------------
    def exists(self) -> bool:
        return self.path.is_file()

    def _raw_lines(self) -> list[str]:
        if not self.path.is_file():
            return []
        text = self.path.read_text(encoding="utf-8")
        # A final line without its newline is an append still in progress by
        # another process; it is not part of the record yet.
        if text and not text.endswith("\n"):
            text = text[: text.rfind("\n") + 1]
        return [ln for ln in text.splitlines() if ln.strip()]

    @contextmanager
    def locked(self) -> Iterator[ExecutionRecord]:
        """Hold the record's exclusive lock across read → validate → append,
        so a check made on the current state is still true when the event
        lands (two agents cannot both take the last attempt)."""
        if self._held:
            yield self
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        with _locked(self.path):
            self._held = True
            try:
                yield self
            finally:
                self._held = False

    def verify_chain(self) -> list[str]:
        """Return integrity problems; an empty list means the chain is intact."""
        problems: list[str] = []
        prev: str | None = None
        for index, line in enumerate(self._raw_lines(), start=1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"line {index}: not JSON ({exc.msg})")
                return problems
            expected_seq = index
            if raw.get("seq") != expected_seq:
                problems.append(f"line {index}: seq {raw.get('seq')!r}, expected {expected_seq}")
            if raw.get("prev") != prev:
                problems.append(f"line {index}: prev hash does not match the preceding event")
            recomputed = _event_hash(
                raw.get("seq"), raw.get("ts"), raw.get("type"), raw.get("actor"),
                raw.get("data") or {}, raw.get("prev"),
            )
            if raw.get("hash") != recomputed:
                problems.append(f"line {index}: content does not match its hash (edited)")
            prev = raw.get("hash")
        return problems

    def events(self, *, strict: bool = True) -> list[Event]:
        """Load all events. ``strict`` raises on a broken chain."""
        if strict:
            problems = self.verify_chain()
            if problems:
                raise RecordIntegrityError(
                    f"execution record {self.path} failed integrity check: " + "; ".join(problems)
                )
        out: list[Event] = []
        for line in self._raw_lines():
            raw = json.loads(line)
            out.append(
                Event(
                    seq=raw["seq"], ts=raw["ts"], type=raw["type"], actor=raw["actor"],
                    data=raw.get("data") or {}, prev=raw.get("prev"), hash=raw["hash"],
                )
            )
        return out

    # -- writing ---------------------------------------------------------
    def append(self, type_: str, actor: str, data: dict[str, Any] | None = None) -> Event:
        """Append one event under an exclusive lock and return it.

        Refuses to extend a broken chain: evidence appended after tampering
        would inherit a legitimacy it does not have.
        """
        data = dict(data or {})
        with self.locked():
            problems = self.verify_chain()
            if problems:
                raise RecordIntegrityError(
                    f"refusing to append to a broken execution record ({self.path}): "
                    + "; ".join(problems)
                )
            lines = self._raw_lines()
            if lines:
                last = json.loads(lines[-1])
                seq, prev = last["seq"] + 1, last["hash"]
            else:
                seq, prev = 1, None
            ts = _now()
            digest = _event_hash(seq, ts, type_, actor, data, prev)
            event = Event(seq=seq, ts=ts, type=type_, actor=actor, data=data, prev=prev, hash=digest)
            self.dir.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.as_dict(), sort_keys=True, ensure_ascii=False) + "\n")
            return event


def parse_record_text(text: str) -> list[Event]:
    """Events of a record's committed text (e.g. ``git show <rev>:<record>``),
    without verifying the chain."""
    out: list[Event] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        out.append(Event(seq=raw["seq"], ts=raw["ts"], type=raw["type"], actor=raw["actor"],
                         data=raw.get("data") or {}, prev=raw.get("prev"), hash=raw["hash"]))
    return out


def is_record_file(path: str) -> bool:
    """An execution record's own files — ``<ID>/record.jsonl``, its lock and
    its evidence snapshots — and nothing else placed under the directory."""
    if not path.startswith(EXECUTION_DIRNAME + "/"):
        return False
    parts = path[len(EXECUTION_DIRNAME) + 1:].split("/")
    return (len(parts) == 2 and parts[1] in ("record.jsonl", "record.jsonl.lock", ".lock")) or (
        len(parts) == 3 and parts[1] == "snapshots" and parts[2].endswith(".json"))
