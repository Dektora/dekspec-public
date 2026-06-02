"""Run persistence — per-compile-invocation logging to XDG_DATA_HOME.

Each `dekspec compile` invocation writes to a per-run directory under
`$XDG_DATA_HOME/dekspec/<repo-fingerprint>/runs/<timestamp>-<run-id>/`
containing:

  - manifest.json    metadata: trigger, timestamp, source SHAs, exit code, emitted paths
  - events.jsonl     structured event stream (parsed, validated, emitted, warned, errored)
  - irs/<id>.ir.json the parsed IR objects

Per-repo top-level also maintains:
  - latest          symlink to the most recent run dir
  - lock-states.json small ledger of artifact id -> last-known status

v0.1 lite: simple count-based retention (default 200 runs), no compression,
no SQLite index, no tiering. Cross-repo-ready layout (top-level
`$XDG_DATA_HOME/dekspec/index.db` slot is reserved but not yet populated).

Public API: open_run() context manager + helpers.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .. import __version__ as DEKSPEC_VERSION
from .parser import IR_SCHEMA_VERSION, PARSER_VERSION

DEFAULT_KEEP_RUNS = 200
PERSISTENCE_VERSION = "0.2.0"


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #


def xdg_data_root() -> Path:
    """Base $XDG_DATA_HOME / dekspec dir. Honours XDG_DATA_HOME if set."""
    base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    return base / "dekspec"


def repo_fingerprint(start: str | Path) -> str:
    """Stable per-repo fingerprint: <basename>-<sha12>.

    Resolves to the git toplevel if `start` is inside a git repo; otherwise
    to the directory containing `start`. The SHA is over the absolute path
    so the fingerprint is deterministic per location on the host.
    """
    path = Path(start).resolve()
    if path.is_file():
        path = path.parent
    try:
        toplevel = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        anchor = Path(toplevel)
    except (subprocess.CalledProcessError, FileNotFoundError):
        anchor = path
    digest = hashlib.sha256(str(anchor).encode("utf-8")).hexdigest()[:12]
    return f"{anchor.name}-{digest}"


def repo_state_dir(start: str | Path, base: Path | None = None) -> Path:
    """Per-repo state directory: <xdg_data_root>/<repo-fingerprint>/."""
    return (base or xdg_data_root()) / repo_fingerprint(start)


def repo_runs_dir(start: str | Path, base: Path | None = None) -> Path:
    """<repo_state_dir>/runs/."""
    return repo_state_dir(start, base=base) / "runs"


# --------------------------------------------------------------------------- #
# Run model
# --------------------------------------------------------------------------- #


@dataclass
class Run:
    """In-memory record of a single compile invocation. Serialized to manifest.json."""

    run_id: str
    timestamp: str
    trigger: str = "manual-compile"
    command: str = ""
    dekspec_version: str = DEKSPEC_VERSION
    parser_version: str = PARSER_VERSION
    persistence_version: str = PERSISTENCE_VERSION
    ir_schema_versions: dict[str, str] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    emissions: list[dict[str, Any]] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0
    exit_code: int = 0
    duration_ms: int = 0
    milestone: bool = False  # captured but not used for retention until v0.2

    @classmethod
    def new(cls, trigger: str = "manual-compile", command: str = "") -> Run:
        return cls(
            run_id=uuid4().hex[:12],
            timestamp=_iso_now(),
            trigger=trigger,
            command=command,
        )


class RunWriter:
    """Wraps a Run with file-writing helpers. Created via open_run()."""

    def __init__(self, run: Run, run_dir: Path):
        self.run = run
        self.run_dir = run_dir
        self.events_path = run_dir / "events.jsonl"
        self.manifest_path = run_dir / "manifest.json"

    def event(self, kind: str, **fields: Any) -> None:
        evt = {"t": _iso_now_ms(), "kind": kind, **fields}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evt, default=str) + "\n")

    def record_artifact(self, ir: dict[str, Any]) -> Path:
        """Persist an IR to irs/<id>.ir.json and append to manifest.artifacts."""
        artifact_id = ir["id"]
        ir_path = self.run_dir / "irs" / f"{artifact_id}.ir.json"
        ir_path.write_text(json.dumps(ir, indent=2, default=str), encoding="utf-8")
        warning_count = len(ir.get("parse_warnings", []))
        self.run.artifacts.append(
            {
                "id": artifact_id,
                "source_path": ir.get("source", {}).get("path", ""),
                "source_sha256": ir.get("source", {}).get("sha256", ""),
                "ir_path": f"irs/{artifact_id}.ir.json",
                "status": ir.get("status", "UNKNOWN"),
                "warnings": warning_count,
            }
        )
        self.run.warnings += warning_count
        self.run.ir_schema_versions["interface-contract"] = ir.get(
            "ir_schema_version", IR_SCHEMA_VERSION
        )
        self.event(
            kind="parse_complete",
            artifact_id=artifact_id,
            warnings=warning_count,
            status=ir.get("status"),
        )
        return ir_path

    def record_emission(
        self,
        emitter: str,
        artifact_id: str,
        output_path: str | None,
        output_size: int,
    ) -> None:
        self.run.emissions.append(
            {
                "emitter": emitter,
                "artifact_id": artifact_id,
                "output_path": output_path,
                "output_size": output_size,
            }
        )
        self.event(
            kind="emit_complete",
            emitter=emitter,
            artifact_id=artifact_id,
            output_path=output_path,
            output_size=output_size,
        )

    def flush_manifest(self) -> None:
        self.manifest_path.write_text(
            json.dumps(asdict(self.run), indent=2, default=str), encoding="utf-8"
        )


# --------------------------------------------------------------------------- #
# Run lifecycle
# --------------------------------------------------------------------------- #


@contextmanager
def open_run(
    start: str | Path,
    trigger: str = "manual-compile",
    command: str = "",
    base: Path | None = None,
    keep: int = DEFAULT_KEEP_RUNS,
) -> Iterator[RunWriter]:
    """Context manager that owns the lifecycle of a single compile run.

    On enter: creates the run dir under <repo-fingerprint>/runs/ and yields a
    RunWriter. The caller calls writer.record_artifact() / writer.record_emission()
    / writer.event() during the run.

    On exit:
      - writes manifest.json (whether the body succeeded or raised)
      - refreshes the per-repo `latest` symlink
      - updates the per-repo lock-states.json ledger
      - prunes runs older than `keep` (default 200)
    """
    runs_dir = repo_runs_dir(start, base=base)
    runs_dir.mkdir(parents=True, exist_ok=True)

    run = Run.new(trigger=trigger, command=command)
    run_dir_name = f"{run.timestamp.replace(':', '-')}-{run.run_id}"
    run_dir = runs_dir / run_dir_name
    run_dir.mkdir(exist_ok=True)
    (run_dir / "irs").mkdir(exist_ok=True)

    writer = RunWriter(run=run, run_dir=run_dir)
    started_at = datetime.now(timezone.utc)
    try:
        writer.event(kind="run_start", trigger=trigger, command=command)
        yield writer
        writer.event(kind="run_complete")
    except Exception as e:
        writer.run.exit_code = max(writer.run.exit_code, 1)
        writer.run.errors += 1
        writer.event(kind="run_error", error=str(e), error_type=type(e).__name__)
        raise
    finally:
        writer.run.duration_ms = int(
            (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        )
        writer.flush_manifest()
        _update_latest_symlink(runs_dir, run_dir)
        _update_lock_states(start, writer.run.artifacts, base=base)
        _record_in_index(start, writer.run, run_dir.name, base=base)
        _prune_runs(runs_dir, keep=keep)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _update_latest_symlink(runs_dir: Path, run_dir: Path) -> None:
    """Refresh <repo-state-dir>/latest -> runs/<run_dir_name>."""
    latest = runs_dir.parent / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(Path("runs") / run_dir.name)


def _update_lock_states(
    start: str | Path,
    artifacts: list[dict[str, Any]],
    base: Path | None = None,
) -> None:
    """Update <repo-state-dir>/lock-states.json with each artifact's current status."""
    if not artifacts:
        return
    states_path = repo_state_dir(start, base=base) / "lock-states.json"
    states: dict[str, Any] = {}
    if states_path.exists():
        try:
            states = json.loads(states_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            states = {}
    now_iso = _iso_now()
    for a in artifacts:
        states[a["id"]] = {
            "status": a["status"],
            "source_sha256": a["source_sha256"],
            "last_seen": now_iso,
        }
    states_path.write_text(json.dumps(states, indent=2), encoding="utf-8")


def _record_in_index(
    start: str | Path,
    run: Run,
    run_dir_name: str,
    base: Path | None = None,
) -> None:
    """Best-effort SQLite-index update. Failures here must not block the
    primary on-disk persistence path; a corrupt index can be rebuilt via
    `dekspec runs reindex`.
    """
    from .persistence_index import open_index, record_run
    state_dir = repo_state_dir(start, base=base)
    try:
        conn = open_index(state_dir)
        try:
            record_run(conn, run, run_dir_name)
        finally:
            conn.close()
    except Exception:
        pass


def _prune_runs(runs_dir: Path, keep: int) -> None:
    """Keep the `keep` most recent runs; delete older ones (skipping milestone runs)."""
    if not runs_dir.exists() or keep <= 0:
        return
    all_runs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    for old in all_runs[keep:]:
        if _is_milestone(old):
            continue
        shutil.rmtree(old, ignore_errors=True)


def _is_milestone(run_dir: Path) -> bool:
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        return False
    try:
        return bool(json.loads(manifest.read_text(encoding="utf-8")).get("milestone"))
    except json.JSONDecodeError:
        return False


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_now_ms() -> str:
    # Truncate microseconds to milliseconds for compactness.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
