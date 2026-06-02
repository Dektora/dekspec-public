"""SQLite index for compile runs + execution-attempt lifecycle.

v0.2 (user_version 1) added the compile-run index. v0.3 (user_version 2)
adds the execution-lifecycle tables that DekFactory (or any executor)
writes when it runs against compiled IRs.

Per-run JSON + IRs continue to live on disk under
`<repo-state-dir>/runs/<run_dir_name>/` (manifest.json + irs/*.ir.json
+ events.jsonl). The SQLite index at `<repo-state-dir>/index.db` is a
derived view of compile-run history + the canonical store for execution
attempts (which have no JSONL on-disk counterpart today).

If the compile-run side of the index gets corrupt, `dekspec runs reindex`
rebuilds it from the JSON manifests on disk. Execution-attempt rows are
canonical in the DB and have no reindex-from-disk path.

Schema (versioned via PRAGMA user_version):

  v1 — compile-run side (unchanged):
    runs(run_id PK, timestamp, trigger, command, dekspec_version,
         artifact_count, emission_count, warnings, errors, exit_code,
         duration_ms, milestone, run_dir_name UNIQUE)
    artifacts(run_id, artifact_id, kind, status, source_sha256, warnings,
              PK (run_id, artifact_id))
    emissions(run_id, emitter, artifact_id, output_path, output_size)

  v2 — execution-lifecycle side (additive, this revision):
    execution_attempts(id PK, intent_id, mission_id, compile_run_id FK,
                       agent_model, audit_profile, attempt_number,
                       started_at, completed_at, ci_status,
                       constraint_violations_count, escalation_required,
                       merged, merge_commit_sha, last_heartbeat_at,
                       notes, tags_json)
    execution_events(id PK, attempt_id FK, intent_id, event_type,
                     custom_event_type, payload_json, timestamp,
                     agent_model)
    merge_outcomes(intent_id PK, first_attempt_id FK, final_attempt_id FK,
                   total_attempts, time_to_merge_seconds,
                   first_pass_success, human_escalation_count)

Public API:
  - INDEX_FILENAME, INDEX_SCHEMA_VERSION constants
  - open_index(state_dir) -> sqlite3.Connection
  - init_schema(conn)              # idempotent, migrates v1 -> v2 in place
  - record_run(conn, run, run_dir_name)
  - query_runs(conn, **filters) -> list[dict]
  - reindex(state_dir) -> dict (counts)

Lifecycle-side public API lives in `dekspec.lifecycle` (separate module
to keep concerns clean).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INDEX_FILENAME = "index.db"
INDEX_SCHEMA_VERSION = 2


def open_index(state_dir: Path) -> sqlite3.Connection:
    """Open (and initialize on first use) the SQLite index for a repo state dir."""
    state_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_dir / INDEX_FILENAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= INDEX_SCHEMA_VERSION:
        return

    # v1 — compile-run side. CREATE IF NOT EXISTS so an existing v1 DB
    # is left untouched and only the v2 additive tables below land.
    if current < 1:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id          TEXT PRIMARY KEY,
                timestamp       TEXT NOT NULL,
                trigger         TEXT,
                command         TEXT,
                dekspec_version TEXT,
                artifact_count  INTEGER NOT NULL DEFAULT 0,
                emission_count  INTEGER NOT NULL DEFAULT 0,
                warnings        INTEGER NOT NULL DEFAULT 0,
                errors          INTEGER NOT NULL DEFAULT 0,
                exit_code       INTEGER NOT NULL DEFAULT 0,
                duration_ms     INTEGER NOT NULL DEFAULT 0,
                milestone       INTEGER NOT NULL DEFAULT 0,
                run_dir_name    TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_exit_code ON runs(exit_code);
            CREATE INDEX IF NOT EXISTS idx_runs_milestone ON runs(milestone);

            CREATE TABLE IF NOT EXISTS artifacts (
                run_id        TEXT NOT NULL,
                artifact_id   TEXT NOT NULL,
                kind          TEXT NOT NULL,
                status        TEXT,
                source_sha256 TEXT,
                warnings      INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (run_id, artifact_id),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_artifacts_artifact_id ON artifacts(artifact_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);

            CREATE TABLE IF NOT EXISTS emissions (
                run_id      TEXT NOT NULL,
                emitter     TEXT NOT NULL,
                artifact_id TEXT NOT NULL,
                output_path TEXT,
                output_size INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_emissions_emitter ON emissions(emitter);
        """)

    # v2 — execution-lifecycle side. Additive; never alters v1 tables.
    if current < 2:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS execution_attempts (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id                   TEXT NOT NULL,
                mission_id                  TEXT,
                compile_run_id              TEXT,
                agent_model                 TEXT NOT NULL,
                audit_profile               TEXT NOT NULL DEFAULT 'v1',
                attempt_number              INTEGER NOT NULL,
                started_at                  TEXT NOT NULL,
                completed_at                TEXT,
                ci_status                   TEXT,
                constraint_violations_count INTEGER NOT NULL DEFAULT 0,
                escalation_required         INTEGER NOT NULL DEFAULT 0,
                merged                      INTEGER NOT NULL DEFAULT 0,
                merge_commit_sha            TEXT,
                last_heartbeat_at           TEXT,
                notes                       TEXT,
                tags_json                   TEXT,
                FOREIGN KEY (compile_run_id) REFERENCES runs(run_id) ON DELETE SET NULL,
                UNIQUE (intent_id, attempt_number)
            );
            CREATE INDEX IF NOT EXISTS idx_exec_intent      ON execution_attempts(intent_id);
            CREATE INDEX IF NOT EXISTS idx_exec_mission     ON execution_attempts(mission_id);
            CREATE INDEX IF NOT EXISTS idx_exec_completed   ON execution_attempts(completed_at);
            CREATE INDEX IF NOT EXISTS idx_exec_agent_model ON execution_attempts(agent_model);
            CREATE INDEX IF NOT EXISTS idx_exec_ci_status   ON execution_attempts(ci_status);

            CREATE TABLE IF NOT EXISTS execution_events (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id          INTEGER NOT NULL,
                intent_id           TEXT NOT NULL,
                event_type          TEXT NOT NULL,
                custom_event_type   TEXT,
                payload_json        TEXT NOT NULL,
                timestamp           TEXT NOT NULL,
                agent_model         TEXT NOT NULL,
                FOREIGN KEY (attempt_id) REFERENCES execution_attempts(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_exec_evt_attempt ON execution_events(attempt_id);
            CREATE INDEX IF NOT EXISTS idx_exec_evt_intent  ON execution_events(intent_id);
            CREATE INDEX IF NOT EXISTS idx_exec_evt_type    ON execution_events(event_type);

            CREATE TABLE IF NOT EXISTS merge_outcomes (
                intent_id               TEXT PRIMARY KEY,
                first_attempt_id        INTEGER,
                final_attempt_id        INTEGER,
                total_attempts          INTEGER NOT NULL,
                time_to_merge_seconds   INTEGER,
                first_pass_success      INTEGER NOT NULL DEFAULT 0,
                human_escalation_count  INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (first_attempt_id) REFERENCES execution_attempts(id) ON DELETE SET NULL,
                FOREIGN KEY (final_attempt_id) REFERENCES execution_attempts(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_merge_first_pass ON merge_outcomes(first_pass_success);
        """)

    conn.execute(f"PRAGMA user_version = {INDEX_SCHEMA_VERSION}")
    conn.commit()


def _kind_from_artifact_id(artifact_id: str) -> str:
    if artifact_id == "SYSTEM-VISION":
        return "vision"
    if artifact_id == "DOMAIN-GLOSSARY":
        return "glossary"
    if artifact_id == "CONSTITUTION":
        return "constitution"
    for prefix, kind in (
        ("ADR-", "adr"), ("AE-", "ae"), ("WS-", "ws"),
        ("IC-", "ic"), ("IB-", "ib"),
        ("INT-", "intent"), ("MSN-", "mission"),
        ("SP-", "sp"),
    ):
        if artifact_id.startswith(prefix):
            return kind
    return "unknown"


def record_run(
    conn: sqlite3.Connection,
    run: Any,
    run_dir_name: str,
) -> None:
    """Insert or replace a run row + its artifacts + emissions."""
    cur = conn.cursor()
    cur.execute(
        """INSERT OR REPLACE INTO runs (
            run_id, timestamp, trigger, command, dekspec_version,
            artifact_count, emission_count, warnings, errors,
            exit_code, duration_ms, milestone, run_dir_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run.run_id, run.timestamp, run.trigger, run.command,
            run.dekspec_version,
            len(run.artifacts), len(run.emissions),
            run.warnings, run.errors, run.exit_code,
            run.duration_ms, int(bool(run.milestone)),
            run_dir_name,
        ),
    )
    cur.execute("DELETE FROM artifacts WHERE run_id = ?", (run.run_id,))
    cur.execute("DELETE FROM emissions WHERE run_id = ?", (run.run_id,))
    for a in run.artifacts:
        artifact_id = a.get("id", "")
        cur.execute(
            """INSERT INTO artifacts (
                run_id, artifact_id, kind, status, source_sha256, warnings
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                run.run_id, artifact_id,
                _kind_from_artifact_id(artifact_id),
                a.get("status"), a.get("source_sha256"),
                a.get("warnings", 0),
            ),
        )
    for e in run.emissions:
        cur.execute(
            """INSERT INTO emissions (
                run_id, emitter, artifact_id, output_path, output_size
            ) VALUES (?, ?, ?, ?, ?)""",
            (
                run.run_id, e.get("emitter", ""), e.get("artifact_id", ""),
                e.get("output_path"), e.get("output_size", 0),
            ),
        )
    conn.commit()


def query_runs(
    conn: sqlite3.Connection,
    since: str | None = None,
    until: str | None = None,
    artifact_id: str | None = None,
    exit_code: int | None = None,
    milestone: bool | None = None,
    min_warnings: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Filtered, sorted (newest first) query over the runs table."""
    where: list[str] = []
    params: list[Any] = []
    if since is not None:
        where.append("r.timestamp >= ?")
        params.append(since)
    if until is not None:
        where.append("r.timestamp < ?")
        params.append(until)
    if exit_code is not None:
        where.append("r.exit_code = ?")
        params.append(exit_code)
    if milestone is not None:
        where.append("r.milestone = ?")
        params.append(int(bool(milestone)))
    if min_warnings is not None:
        where.append("r.warnings >= ?")
        params.append(min_warnings)
    if artifact_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM artifacts a WHERE a.run_id = r.run_id AND a.artifact_id = ?)"
        )
        params.append(artifact_id)
    sql = "SELECT * FROM runs r"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def reindex(state_dir: Path) -> dict[str, int]:
    """Rebuild the SQLite index from on-disk manifest.json files.

    Walks `<state_dir>/runs/*/manifest.json`, drops + recreates the
    SQLite tables, then re-records every run found. Returns a count
    summary.
    """
    runs_dir = state_dir / "runs"
    if not runs_dir.exists():
        return {"runs_indexed": 0, "manifests_skipped": 0}

    index_path = state_dir / INDEX_FILENAME
    if index_path.exists():
        index_path.unlink()
    conn = open_index(state_dir)

    indexed = 0
    skipped = 0
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            skipped += 1
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            skipped += 1
            continue
        run = _DictRun(**{
            "run_id": data.get("run_id", run_dir.name),
            "timestamp": data.get("timestamp", _iso_from_dirname(run_dir.name)),
            "trigger": data.get("trigger", ""),
            "command": data.get("command", ""),
            "dekspec_version": data.get("dekspec_version", ""),
            "artifacts": data.get("artifacts", []),
            "emissions": data.get("emissions", []),
            "warnings": data.get("warnings", 0),
            "errors": data.get("errors", 0),
            "exit_code": data.get("exit_code", 0),
            "duration_ms": data.get("duration_ms", 0),
            "milestone": data.get("milestone", False),
        })
        record_run(conn, run, run_dir.name)
        indexed += 1
    conn.close()
    return {"runs_indexed": indexed, "manifests_skipped": skipped}


class _DictRun:
    """Duck-typed Run for reindexing — shares the field names record_run reads."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


def _iso_from_dirname(name: str) -> str:
    """Run dir names look like 2026-05-11T01-23-45Z-<run_id>; return the timestamp."""
    parts = name.split("-")
    if len(parts) < 6:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}:{parts[4]}:{parts[5][:3] if 'Z' in parts[5] else parts[5]}"
