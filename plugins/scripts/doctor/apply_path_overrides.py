#!/usr/bin/env python3
"""Apply `--library-self-audit` path overrides for /fidelity-audit.

The fidelity-audit skill is authored for *consumer* repos: it walks the paths
consumers vendor DekSpec content to (`.claude/skills/`, `dekspec/templates/`,
`dekspec/dekspec-operating-guide.md`). When the audit runs against the library
repo itself (`Dektora/dekspec`), source markdown lives at different paths.
The `--library-self-audit` flag swaps in the library-side layout.

This script owns the override table (mirrors §Library self-audit mode in
SKILL.md). Given a consumer-side path, it returns the library-side path the
audit should actually validate against; given a list, it translates each.

Deterministic table lookup — keeps the translation in code, not prose.

Usage:
  apply_path_overrides.py translate <consumer-path> [<consumer-path> ...]
  apply_path_overrides.py table

`translate` emits one JSON object per line:
  {"input": "dekspec/templates/AE.md",
   "library_path": "templates/AE.md",
   "rule": "dekspec/templates/",
   "skip": false}

A path that matches the `dekspec/project-context.md` rule resolves to
`skip: true` (the file does not exist in the library layout).

`table` emits the full override table as a JSON array.

Exit codes: 0 ok; 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Override table — consumer-side prefix/path -> library-side translation.
# Mirrors the table in fidelity-audit/SKILL.md §Library
# self-audit mode. Order matters: the first matching rule wins, so more
# specific prefixes (checklists/) precede the broader templates/ prefix.
#
# Each rule is (kind, consumer, library):
#   kind="prefix"  -> consumer is a path prefix; replace it with `library`.
#   kind="exact"   -> consumer is a whole path; replace with `library`.
#   kind="skip"    -> consumer prefix has no library equivalent; mark skip.
_OVERRIDE_TABLE: list[tuple[str, str, str]] = [
    ("prefix", ".claude/skills/", "skills/"),
    ("prefix", "dekspec/templates/checklists/", "templates/checklists/"),
    ("prefix", "dekspec/templates/", "templates/"),
    ("exact", "dekspec/dekspec-operating-guide.md", "docs/dekspec-operating-guide.md"),
    ("exact", "dekspec/dekspec-quick-reference.md", "docs/dekspec-quick-reference.md"),
    ("skip", "dekspec/project-context.md", ""),
]


def _normalize(path: str) -> str:
    """Strip a leading `./` and collapse redundant slashes for matching."""
    path = path.strip()
    path = re.sub(r"^\./", "", path)
    return re.sub(r"/{2,}", "/", path)


def translate(path: str) -> dict:
    """Translate one consumer-side path to its library-side equivalent.

    Returns a dict with keys: input, library_path, rule, skip. A path that
    matches no rule passes through unchanged (rule=None, skip=False) — the
    library and consumer layouts agree on it (e.g. `dekspec/` self-spec).
    """
    norm = _normalize(path)
    for kind, consumer, library in _OVERRIDE_TABLE:
        if kind == "exact":
            if norm == consumer:
                return {
                    "input": path,
                    "library_path": library,
                    "rule": consumer,
                    "skip": False,
                }
        elif kind == "skip":
            if norm == consumer:
                return {
                    "input": path,
                    "library_path": None,
                    "rule": consumer,
                    "skip": True,
                }
        else:  # prefix
            if norm.startswith(consumer):
                return {
                    "input": path,
                    "library_path": library + norm[len(consumer) :],
                    "rule": consumer,
                    "skip": False,
                }
    return {"input": path, "library_path": norm, "rule": None, "skip": False}


def table_rows() -> list[dict]:
    """Return the override table as a list of JSON-friendly dicts."""
    return [
        {"kind": kind, "consumer": consumer, "library": library or None}
        for kind, consumer, library in _OVERRIDE_TABLE
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apply_path_overrides.py",
        description="Apply --library-self-audit path overrides for the fidelity audit.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_translate = sub.add_parser(
        "translate", help="Translate consumer-side paths to library-side paths."
    )
    p_translate.add_argument(
        "paths", nargs="+", help="One or more consumer-side paths to translate."
    )

    sub.add_parser("table", help="Print the full override table as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "table":
        json.dump(table_rows(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.command == "translate":
        for path in args.paths:
            print(json.dumps(translate(path), sort_keys=True))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
