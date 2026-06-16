#!/usr/bin/env python3
"""Report an Implementation Brief's status and where it lives on disk.

`/write-code-beads` Safety Check asks the model, in prose, two deterministic
questions about an IB before it decomposes the brief into beads:

  1. Is the IB's `**Status:**` field set to `ACCEPTED`?
  2. Where does the IB file live? The skill body references `queued/`,
     `active/`, and `completed/` subdirectories — but IBs actually live
     FLAT in `dekspec/impl-briefs/` in current repos. This script reports
     the real layout so the skill stops guessing.

Both are pure file inspection — no judgement. This module turns the prose
into one deterministic lookup. It is a CLI (`ib_status_check.py <ib-path>`)
and importable (`ib_status_check(ib_path)`).

Output (JSON on stdout):

    {"status": "ACCEPTED", "path_kind": "flat", "path": "dekspec/impl-briefs/IB-001-foo.md"}

`path_kind` is one of:
  - `flat`     — IB sits directly under `impl-briefs/` (the real layout)
  - `queued`   — IB sits under `impl-briefs/queued/`
  - `active`   — IB sits under `impl-briefs/active/`
  - `completed`— IB sits under `impl-briefs/completed/`
  - `unknown`  — IB is not under any `impl-briefs/` tree

Exit codes:
  0 — IB read, JSON emitted (regardless of status value)
  2 — IB path does not exist or is not a file
  3 — IB has no parseable `**Status:**` field

Style mirrors `tooling/dekspec/cli.py`: argparse, `cmd_*` dispatcher,
`int` return codes, `main(argv)` entry point. Stdlib-only — vendored into
consumer repos where the `dekspec` engine is not importable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# IB front-matter `**Status:**` line, e.g. `**Status:** ACCEPTED`. Some IBs
# instead use a `## Status` heading followed by the value on a later line;
# both shapes are matched, the inline `**Status:**` taking precedence.
_STATUS_FIELD_RE = re.compile(r"^\*\*Status:\*\*\s*`?([A-Za-z_]+)`?\s*$", re.MULTILINE)
_STATUS_HEADING_RE = re.compile(
    r"^##\s+Status\s*\n+\s*`?([A-Za-z_]+)`?\s*$", re.MULTILINE
)

# The leaf subdirectory names the skill body references under `impl-briefs/`.
_KNOWN_SUBDIRS = {"queued", "active", "completed"}


class IBStatusError(Exception):
    """Raised when the IB cannot be read or has no parseable status."""


def _classify_path(ib_path: Path) -> str:
    """Return the `path_kind` for an IB file path.

    `flat` when the IB's parent directory is itself named `impl-briefs`;
    one of the known subdir names when the IB sits one level deeper;
    `unknown` when no `impl-briefs` ancestor is found.
    """
    parent = ib_path.parent
    if parent.name == "impl-briefs":
        return "flat"
    if parent.name in _KNOWN_SUBDIRS and parent.parent.name == "impl-briefs":
        return parent.name
    return "unknown"


def _parse_status(text: str) -> str | None:
    """Extract the IB status token from front-matter text, or None."""
    match = _STATUS_FIELD_RE.search(text)
    if match:
        return match.group(1).strip().upper()
    match = _STATUS_HEADING_RE.search(text)
    if match:
        return match.group(1).strip().upper()
    return None


def ib_status_check(ib_path: Path) -> dict[str, str]:
    """Read an IB and return its status + path classification.

    Raises IBStatusError on a missing file or an unparseable status.
    """
    ib_path = Path(ib_path)
    if not ib_path.is_file():
        raise IBStatusError(f"IB path does not exist or is not a file: {ib_path}")
    try:
        text = ib_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IBStatusError(f"failed to read IB: {exc}") from exc
    status = _parse_status(text)
    if status is None:
        raise IBStatusError(
            f"no parseable `**Status:**` field in IB: {ib_path}"
        )
    return {
        "status": status,
        "path_kind": _classify_path(ib_path),
        "path": str(ib_path),
    }


def cmd_check(args: argparse.Namespace) -> int:
    """CLI dispatcher: print the status JSON for one IB path."""
    try:
        result = ib_status_check(Path(args.ib_path))
    except IBStatusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        # Distinguish a missing file (exit 2) from an unparseable status (3).
        return 2 if "does not exist" in str(exc) else 3
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ib_status_check.py",
        description="Report an Implementation Brief's status and on-disk layout.",
    )
    parser.add_argument(
        "ib_path",
        help="path to the Implementation Brief markdown file",
    )
    parser.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
