#!/usr/bin/env python3
"""L7b check (mechanical): every Components-affected entry resolves to >=1 path.

The /write-intent skill audits `## Components affected` so that no Intent ships
a glob or path that matches nothing on disk. This script does that mechanically:
it parses the section's bullet list, runs each entry as a glob relative to the
repo root, and reports the entries that resolve to zero paths.

Section-prose paragraphs (lines that are not bullets) and the optional
"**Future implementation paths**" sub-list are *not* part of diff confinement;
only the bullets under the primary `## Components affected` heading are checked.
A "Future implementation paths" marker truncates the checked set there (those
paths are authored later under child Intents — see INT-007 for the pattern).

Stdlib-only. No subprocess execution — pure `pathlib.Path.glob`.

Runnable:   python check_components_resolve.py <intent-path> [--repo-root DIR]
Importable: from check_components_resolve import parse_components, check
Exit codes: 0 = all resolve; 2 = unresolved entries; 1 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_COMPONENTS_SECTION = re.compile(
    r"^#+[ \t]+Components affected[ \t]*$", re.MULTILINE
)
_BULLET = re.compile(r"^[ \t]*[-*][ \t]+(?P<body>.+?)[ \t]*$")
_FUTURE_MARKER = re.compile(r"future implementation paths", re.IGNORECASE)
# An inline-code span at the start of a bullet holds the glob/path.
_BACKTICK = re.compile(r"`([^`]+)`")


def parse_components(text: str) -> list[str]:
    """Return the glob/path entries from the `## Components affected` section.

    Stops at the next heading or at a "Future implementation paths" marker.
    """
    m = _COMPONENTS_SECTION.search(text)
    if not m:
        return []
    entries: list[str] = []
    for line in text[m.end():].splitlines():
        s = line.strip()
        if s.startswith("#"):
            break
        if _FUTURE_MARKER.search(s):
            break
        bm = _BULLET.match(line)
        if not bm:
            continue
        body = bm.group("body")
        # Prefer an inline-code span; else take the leading token verbatim.
        code = _BACKTICK.search(body)
        entry = code.group(1).strip() if code else body.split()[0].strip()
        if entry:
            entries.append(entry)
    return entries


def check(intent_path: Path, repo_root: Path) -> dict[str, object]:
    """Resolve every Components-affected entry; return a structured result."""
    text = intent_path.read_text(encoding="utf-8")
    entries = parse_components(text)
    unresolved: list[str] = []
    resolved: list[str] = []
    for entry in entries:
        # Absolute-looking entries are normalised relative to repo_root.
        rel = entry.lstrip("/")
        try:
            matches = list(repo_root.glob(rel))
        except (ValueError, NotImplementedError):
            matches = []
        # A literal path with no glob metacharacters: also accept a plain exist.
        if not matches and not any(c in rel for c in "*?[]"):
            if (repo_root / rel).exists():
                matches = [repo_root / rel]
        (resolved if matches else unresolved).append(entry)
    return {
        "intent": str(intent_path),
        "total": len(entries),
        "resolved": resolved,
        "unresolved": unresolved,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_components_resolve.py",
        description="L7b: check Components-affected entries resolve to >=1 path.",
    )
    parser.add_argument("intent_path", help="Path to the Intent markdown file.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root the globs resolve against (default: cwd).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    args = parser.parse_args(argv)

    intent_path = Path(args.intent_path)
    if not intent_path.is_file():
        print(f"ERROR: Intent file not found: {intent_path}", file=sys.stderr)
        return 1
    repo_root = Path(args.repo_root).resolve()

    result = check(intent_path, repo_root)
    unresolved = result["unresolved"]

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["total"] == 0:
            print(
                "WARNING: no Components-affected entries found "
                "(empty section or section absent).",
                file=sys.stderr,
            )
        if not unresolved:
            print(
                f"OK: all {result['total']} Components-affected entries resolve."
            )
        else:
            print(
                f"L7b FAIL: {len(unresolved)} of {result['total']} "
                "Components-affected entries resolve to 0 paths:",
                file=sys.stderr,
            )
            for entry in unresolved:  # type: ignore[union-attr]
                print(f"  {entry}", file=sys.stderr)

    return 2 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
