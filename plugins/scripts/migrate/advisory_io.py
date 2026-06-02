#!/usr/bin/env python3
"""Advisory-report I/O for /dekspec:migrate --walker-only.

`dekspec migrate-artifacts` leaves semantic-change items it could not
auto-apply in an advisory report — a JSON file (default
`<repo>/dekspec/migration-advisory.json`). The orchestrator skill walks
that queue with Claude in the loop.

This script owns the deterministic plumbing the skill body otherwise
describes in prose:

  load <path>                  Parse + structurally validate the report,
                               print a one-line summary.
  status <path>                Print the compact per-item progress table.
  checkpoint <path> --completed N
                               Write a checkpoint JSON next to the report
                               so a `--skip N` resume works.

Advisory report shape (validated by `load`):
  {
    "library_from_version": "0.49.0",
    "library_to_version":   "0.50.0",
    "generated_at":         "2026-05-19T12:00:00Z",
    "advisories": [
      {"change_type": "section_split",
       "artifact_path": "dekspec/architecture-elements/AE-001.md",
       "description": "...",
       "suggested_transform": "...",   # optional
       "context": {"line_range": [10, 24]}}   # optional
    ]
  }

Checkpoint shape (written by `checkpoint`):
  {"advisory_path": "<original path>",
   "items_completed": <int>,
   "saved_at": "<ISO 8601>"}

Exit codes: 0 ok; 1 missing/malformed report; 2 usage error.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

# Top-level keys every advisory report must carry.
_REQUIRED_REPORT_KEYS = (
    "library_from_version",
    "library_to_version",
    "generated_at",
    "advisories",
)
# Keys every advisory item must carry.
_REQUIRED_ITEM_KEYS = ("change_type", "artifact_path", "description")


class AdvisoryError(Exception):
    """The advisory report is missing or structurally invalid."""


def load_report(path: Path) -> dict:
    """Read and structurally validate the advisory report at `path`.

    Raises AdvisoryError on a missing file, JSON parse error, missing
    required key, or an advisory item that is not a well-formed object.
    """
    if not path.is_file():
        raise AdvisoryError(
            f"No advisory report found at {path}. Run `dekspec migrate-artifacts` "
            f"(or `/dekspec-migrate`) first."
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AdvisoryError(f"Cannot read {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdvisoryError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise AdvisoryError(f"{path}: top-level value must be a JSON object.")
    missing = [k for k in _REQUIRED_REPORT_KEYS if k not in data]
    if missing:
        raise AdvisoryError(f"{path}: missing required key(s): {', '.join(missing)}")
    advisories = data["advisories"]
    if not isinstance(advisories, list):
        raise AdvisoryError(f"{path}: `advisories` must be an array.")
    for idx, item in enumerate(advisories, start=1):
        if not isinstance(item, dict):
            raise AdvisoryError(f"{path}: advisory item {idx} is not an object.")
        item_missing = [k for k in _REQUIRED_ITEM_KEYS if k not in item]
        if item_missing:
            raise AdvisoryError(
                f"{path}: advisory item {idx} missing key(s): "
                f"{', '.join(item_missing)}"
            )
    return data


def summary_line(report: dict) -> str:
    """Return the one-line `load` summary for a validated report."""
    return (
        f"Advisory queue: {report['library_from_version']} -> "
        f"{report['library_to_version']} | generated {report['generated_at']} | "
        f"{len(report['advisories'])} item(s)"
    )


def status_table(report: dict) -> str:
    """Render the compact IDX / CHANGE_TYPE / ARTIFACT progress table."""
    advisories = report["advisories"]
    lines = [
        "  IDX  CHANGE_TYPE              ARTIFACT",
        "  ---  -----------------------  " + "-" * 41,
    ]
    if not advisories:
        lines.append("  (queue empty — nothing to walk)")
        return "\n".join(lines)
    for idx, item in enumerate(advisories, start=1):
        lines.append(
            f"  {idx:<3}  {item['change_type']:<23}  {item['artifact_path']}"
        )
    return "\n".join(lines)


def write_checkpoint(advisory_path: Path, items_completed: int) -> Path:
    """Write a checkpoint JSON next to `advisory_path`; return its path.

    The checkpoint lets `--skip <items_completed>` resume a quit walk.
    """
    if items_completed < 0:
        raise AdvisoryError("--completed must be >= 0")
    checkpoint_path = advisory_path.parent / "migration-checkpoint.json"
    payload = {
        "advisory_path": str(advisory_path),
        "items_completed": items_completed,
        "saved_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    checkpoint_path.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return checkpoint_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="advisory_io.py",
        description="Advisory-report I/O for /dekspec:migrate --walker-only.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load", help="Validate the report; print a summary.")
    p_load.add_argument("path", help="Path to the advisory report JSON.")

    p_status = sub.add_parser("status", help="Print the compact progress table.")
    p_status.add_argument("path", help="Path to the advisory report JSON.")

    p_ckpt = sub.add_parser("checkpoint", help="Write a resume checkpoint JSON.")
    p_ckpt.add_argument("path", help="Path to the advisory report JSON.")
    p_ckpt.add_argument(
        "--completed",
        type=int,
        required=True,
        help="Number of advisory items walked before quitting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = Path(args.path)

    try:
        if args.command == "load":
            report = load_report(path)
            print(summary_line(report))
            return 0
        if args.command == "status":
            report = load_report(path)
            print(status_table(report))
            return 0
        if args.command == "checkpoint":
            # Validate the report exists/parses before checkpointing against it.
            load_report(path)
            checkpoint_path = write_checkpoint(path, args.completed)
            print(
                f"Checkpoint saved to {checkpoint_path}. "
                f"To resume: /dekspec:migrate --walker-only --skip {args.completed}"
            )
            return 0
    except AdvisoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
