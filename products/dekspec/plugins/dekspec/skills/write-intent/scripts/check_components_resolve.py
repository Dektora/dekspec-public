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
_BRACE = re.compile(r"\{([^{}]*)\}")
_EXPANSION_LIMIT = 4096
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


def _expand_braces(pattern: str) -> list[str]:
    """Match the engine's innermost expansion, with a pre-matching budget.

    Retain duplicate alternatives: each consumes a candidate. Every pass can
    only maintain or increase the count, so refusing a pass over the limit is
    equivalent to refusing its eventual Cartesian product. Count before split
    or construction, including a single group with thousands of alternatives.
    """
    candidates = [pattern]
    while True:
        groups = [_BRACE.search(candidate) for candidate in candidates]
        if not any(groups):
            return candidates
        count = sum(group.group(1).count(",") + 1 if group else 1 for group in groups)
        if count > _EXPANSION_LIMIT:
            raise ValueError(
                f"{pattern}: brace expansion exceeds the {_EXPANSION_LIMIT} candidate limit; "
                "reduce alternatives or split the Components declaration."
            )
        expanded: list[str] = []
        for candidate, group in zip(candidates, groups):
            if group is None:
                expanded.append(candidate)
            else:
                expanded.extend(candidate[:group.start()] + alternative + candidate[group.end():]
                                for alternative in group.group(1).split(","))
        candidates = expanded


# Surface skeleton (ADR-062) for IB-191 O-9: the checker's public copy of the
# engine's matcher, brace expansion and limit. Behavior-free and unused until
# IB-191 implements them; `check()` and `main()` are unchanged.
EXPANSION_LIMIT: int | None = None


def expand_braces(pattern: str) -> list[str]:
    """Surface skeleton (IB-191 O-9); returns no candidates yet."""
    return []


def matches_any_glob(path: str, globs) -> bool:
    """Surface skeleton (IB-191 O-9); matches nothing yet."""
    return False


def _resolves(pattern: str, repo_root: Path) -> bool:
    """Preserve ordinary glob/literal behavior for one expanded candidate."""
    rel = pattern.lstrip("/")
    try:
        if next(repo_root.glob(rel), None) is not None:
            return True
    except (ValueError, NotImplementedError):
        pass
    return not any(c in rel for c in "*?[]") and (repo_root / rel).exists()


def check(intent_path: Path, repo_root: Path) -> dict[str, object]:
    """Resolve every Components-affected entry; return a structured result."""
    text = intent_path.read_text(encoding="utf-8")
    entries = parse_components(text)
    unresolved: list[str] = []
    resolved: list[str] = []
    for entry in entries:
        try:
            candidates = _expand_braces(entry)
        except ValueError as exc:
            print(f"L7b FAIL: {exc}", file=sys.stderr)
            unresolved.append(entry)
            continue
        matched = any(_resolves(candidate, repo_root) for candidate in candidates)
        (resolved if matched else unresolved).append(entry)
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
