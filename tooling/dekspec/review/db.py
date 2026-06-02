"""SQLite schema + persistence write-path for the review flywheel
(MSN-017 / INT-109). Per ADR-026 (LOCKED 2026-05-29) the orchestration
shell (INT-105 LOCKED) calls :func:`write_verdict` after every review
run; the persisted rows form the calibration corpus that
:mod:`dekspec.review.calibration` (INT-117) proposes per-lens
silver/gold thresholds against.

Schema columns mirror the design substrate §"Persistence" row:
``ib_id``, ``branch_sha``, ``lens_scores`` (JSON), ``aggregated_verdict``
(GO|NO-GO|INSUFFICIENT_EVIDENCE), ``operator_decision``
(advance|hold|abort|None), ``time_to_decision`` (seconds, None until the
operator decides), ``eventual_outcome`` (operator-accepted |
PR-merged-clean | PR-reverted-in-14d | bead-reopened |
audit-doctor-regressed, None until labeled).

The CLI verbs (``dekspec review status/history/calibrate``) live in
INT-116 and consume this module read-only.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Mapping


SCHEMA: str = """
CREATE TABLE IF NOT EXISTS reviews (
    rowid              INTEGER PRIMARY KEY AUTOINCREMENT,
    ib_id              TEXT NOT NULL,
    branch_sha         TEXT NOT NULL,
    lens_scores        TEXT NOT NULL,     -- JSON: per-lens score tuples
    aggregated_verdict TEXT NOT NULL,     -- GO | NO-GO | INSUFFICIENT_EVIDENCE
    operator_decision  TEXT,              -- advance | hold | abort | NULL
    time_to_decision   REAL,              -- seconds; NULL until decided
    eventual_outcome   TEXT,              -- label; NULL until corpus-labeled
    audit_doctor_sha   TEXT,              -- correlation key for the cached snapshot
    ran_at             TEXT NOT NULL,     -- UTC ISO-8601 timestamp
    review_stage       TEXT NOT NULL DEFAULT 'REVIEW_IB'  -- REVIEW_IB | REVIEW_PR
);
CREATE INDEX IF NOT EXISTS idx_reviews_ib_id ON reviews(ib_id);
CREATE INDEX IF NOT EXISTS idx_reviews_outcome ON reviews(eventual_outcome);
"""


def open_db(path: Path | str) -> sqlite3.Connection:
    """Open the reviews.db file at ``path``, applying :data:`SCHEMA`
    idempotently. Returns a :class:`sqlite3.Connection`.

    The connection is the caller's responsibility to close. Tests use
    `tmp_path` fixtures; the orchestration shell uses
    ``$XDG_DATA_HOME/dekspec/<repo>/reviews.db`` resolved per
    INT-116's CLI conventions.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def write_verdict(conn: sqlite3.Connection, verdict: Mapping[str, object]) -> int:
    """Persist a verdict row. Returns the rowid of the inserted row.

    The ``verdict`` mapping must include at least ``ib_id``,
    ``branch_sha``, ``lens_scores`` (JSON-encoded), and
    ``aggregated_verdict``. The remaining columns are optional and
    populated lazily as the operator decides + the corpus labeller
    later assigns the ``eventual_outcome``.
    """
    from datetime import datetime, timezone

    cur = conn.execute(
        """
        INSERT INTO reviews (
            ib_id, branch_sha, lens_scores, aggregated_verdict,
            operator_decision, time_to_decision, eventual_outcome,
            audit_doctor_sha, ran_at, review_stage
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            verdict["ib_id"],
            verdict["branch_sha"],
            verdict["lens_scores"],
            verdict["aggregated_verdict"],
            verdict.get("operator_decision"),
            verdict.get("time_to_decision"),
            verdict.get("eventual_outcome"),
            verdict.get("audit_doctor_sha"),
            verdict.get("ran_at") or datetime.now(timezone.utc).isoformat(),
            verdict.get("review_stage", "REVIEW_IB"),
        ),
    )
    conn.commit()
    return cur.lastrowid
