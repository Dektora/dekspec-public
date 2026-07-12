#!/usr/bin/env python3
"""Verify all quality-gate files referenced by an IB exist on disk.

`/orchestrate-coding-session` Pre-Flight Checks asks the model, in prose, to:

  1. Run `br ready --json` for the candidate bead list.
  2. For each bead, resolve its IB path from `external_ref` (stripping any
     `:suffix` qualifier, e.g. `test-ib-gpu.md:semantic-endpoints`).
  3. Read the IB, collect every referenced checklist / eval / test file path.
  4. Check each path exists. If any are missing — STOP.

Steps 2-4 are pure file inspection. This module turns them into one
deterministic check. It is a CLI (`preflight_quality_gates.py IB...`) and
importable (`check_quality_gates(ib_paths, repo_root)`).

It collects referenced paths from three places in each IB:

  - the `## Quality Checklists` section — backtick-wrapped `.md` paths
  - the `## Files to Modify` table — first-cell `tests/...` paths
  - `## Acceptance Criteria` / `## Done When` items — `tests/...` paths and
    `*.md` eval-file paths cited inline

**Greenfield exemption.** A referenced test/eval file that is *missing on disk*
but listed in some IB's `## Files to Modify` table is a deliverable a bead in
the set will create — not a missing prerequisite. Such files are reported under
`claimed` and never STOP the session. Only a referenced quality file that is
missing AND claimed by no IB in the set triggers the STOP (exit 1).

Output (JSON on stdout):

    {
      "missing": ["dekspec/templates/checklists/python-quality-checklist.md"],
      "claimed": ["tests/test_new_feature.py"],
      "present": ["tests/test_foo.py"],
      "checked": 3,
      "ok": false
    }

Exit codes:
  0 — every referenced quality file exists or is claimed by a bead (a deliverable)
  1 — one or more referenced files are missing AND unclaimed (the STOP condition)
  2 — an IB path itself does not exist or could not be read

Style mirrors `tooling/dekspec/cli.py`. Stdlib-only — vendored into consumer
repos where the `dekspec` engine is not importable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# `external_ref` may carry a `:suffix` slice qualifier — strip it.
def _strip_suffix(ref: str) -> str:
    """Drop a trailing `:suffix` qualifier from an external_ref / IB path."""
    return ref.split(":", 1)[0].strip()


# A `## Quality Checklists` (or `## Checklists`) section header. Everything
# until the next `## ` heading is the checklist block.
_QUALITY_SECTION_RE = re.compile(
    r"^##\s+(?:Quality\s+Checklists|Checklists)\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
# Acceptance-criteria / done-when section (test + eval files are cited here).
_ACCEPTANCE_SECTION_RE = re.compile(
    r"^##\s+(?:Acceptance\s+Criteria|Done\s+When)\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
# `## Files to Modify` table block.
_FILES_SECTION_RE = re.compile(
    r"^##\s+Files\s+to\s+Modify\s*$(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

# A backtick-wrapped path token. Quality files of interest are `.md` checklist
# files and `tests/...py` test files; eval files are typically `.md`.
_BACKTICK_PATH_RE = re.compile(r"`([^`\n]+?)`")
# A `## Files to Modify` table row's first cell.
_TABLE_ROW_FIRST_CELL_RE = re.compile(r"^\|\s*`?([^`|]+?)`?\s*\|", re.MULTILINE)

# Paths we treat as quality-gate files: test files, eval files, checklist md.
_TEST_PATH_RE = re.compile(r"(?:^|/)tests?/.*\.py$")
_CHECKLIST_PATH_RE = re.compile(r"checklist.*\.md$", re.IGNORECASE)
_EVAL_PATH_RE = re.compile(r"eval.*\.md$", re.IGNORECASE)


class PreflightError(Exception):
    """Raised when an IB path cannot be read."""


def _looks_like_quality_file(token: str) -> bool:
    """True when a path token names a test, checklist, or eval file."""
    token = token.strip()
    if not token or " " in token:
        return False
    return bool(
        _TEST_PATH_RE.search(token)
        or _CHECKLIST_PATH_RE.search(token)
        or _EVAL_PATH_RE.search(token)
    )


def collect_quality_paths(ib_text: str) -> list[str]:
    """Extract every quality-gate file path referenced by one IB's text.

    Scans the Quality Checklists, Files to Modify, and Acceptance Criteria
    sections. Returns a sorted, de-duplicated list of repo-relative paths.
    """
    found: set[str] = set()

    for match in _QUALITY_SECTION_RE.finditer(ib_text):
        for tok in _BACKTICK_PATH_RE.findall(match.group(1)):
            if _looks_like_quality_file(tok):
                found.add(tok.strip())

    for match in _FILES_SECTION_RE.finditer(ib_text):
        for tok in _TABLE_ROW_FIRST_CELL_RE.findall(match.group(1)):
            if _looks_like_quality_file(tok):
                found.add(tok.strip())

    for match in _ACCEPTANCE_SECTION_RE.finditer(ib_text):
        for tok in _BACKTICK_PATH_RE.findall(match.group(1)):
            if _looks_like_quality_file(tok):
                found.add(tok.strip())

    return sorted(found)


def collect_claimed_paths(ib_text: str) -> set[str]:
    """Extract every path a bead claims to create/modify from one IB.

    These are the first-cell entries of the `## Files to Modify` table — the
    files the IB's beads are responsible for producing. A referenced quality
    file that is missing on disk but appears here is a deliverable (greenfield),
    not a missing prerequisite, so the caller exempts it from the STOP.
    """
    claimed: set[str] = set()
    for match in _FILES_SECTION_RE.finditer(ib_text):
        for tok in _TABLE_ROW_FIRST_CELL_RE.findall(match.group(1)):
            tok = tok.strip()
            # Skip table header / separator rows ("File", "----", etc.).
            if not tok or " " in tok or "/" not in tok and not tok.endswith(".py"):
                continue
            claimed.add(tok)
    return claimed


def check_quality_gates(
    ib_paths: list[str],
    repo_root: Path,
) -> dict[str, object]:
    """Collect + verify quality-gate files across one or more IBs.

    Raises PreflightError if an IB path itself cannot be read.
    """
    repo_root = Path(repo_root)
    all_paths: set[str] = set()
    claimed_paths: set[str] = set()
    for raw in ib_paths:
        ib_path = Path(_strip_suffix(raw))
        if not ib_path.is_absolute():
            ib_path = repo_root / ib_path
        if not ib_path.is_file():
            raise PreflightError(f"IB path does not exist: {ib_path}")
        try:
            text = ib_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PreflightError(f"failed to read IB {ib_path}: {exc}") from exc
        all_paths.update(collect_quality_paths(text))
        claimed_paths.update(collect_claimed_paths(text))

    missing: list[str] = []
    claimed: list[str] = []
    present: list[str] = []
    for rel in sorted(all_paths):
        candidate = Path(rel)
        if not candidate.is_absolute():
            candidate = repo_root / rel
        if candidate.is_file():
            present.append(rel)
        elif rel in claimed_paths:
            # Missing on disk but a bead in the set creates it — a deliverable,
            # not a missing prerequisite. Greenfield-safe: never STOPs.
            claimed.append(rel)
        else:
            missing.append(rel)

    return {
        "missing": missing,
        "claimed": claimed,
        "present": present,
        "checked": len(all_paths),
        "ok": not missing,
    }


def cmd_check(args: argparse.Namespace) -> int:
    """CLI dispatcher: verify quality gates for the given IB paths."""
    try:
        result = check_quality_gates(args.ib_paths, Path(args.repo_root))
    except PreflightError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    if result["claimed"]:
        print(
            "note — referenced files missing on disk but claimed by a bead "
            "(greenfield deliverables, not a STOP):\n"
            + "\n".join(f"  - {p}" for p in result["claimed"]),
            file=sys.stderr,
        )
    if result["missing"]:
        print(
            "STOP — quality gate files missing and unclaimed by any bead:\n"
            + "\n".join(f"  - {p}" for p in result["missing"]),
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="preflight_quality_gates.py",
        description="Verify quality-gate files referenced by IB(s) exist on disk.",
    )
    parser.add_argument(
        "ib_paths",
        nargs="+",
        metavar="IB",
        help="one or more IB paths (a trailing `:suffix` qualifier is stripped)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="repository root for resolving relative paths (default: cwd)",
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
