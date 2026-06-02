#!/usr/bin/env python3
"""Resolve an ADR's supersession chain to the live (non-superseded) ADR.

DekSpec ADRs record supersession as an italic markdown line under a
`## Supersession` heading:

    *Supersedes:* none
    *Superseded by:* ADR-012

This is a deterministic graph walk: given an ADR id, follow each
`*Superseded by:*` link transitively until reaching an ADR with no
successor (the live ADR). Cycles and dangling references are refused.

Usage:
  resolve_supersession.py <ADR-ID>
  resolve_supersession.py --batch ADR-007,ADR-011 [--adr-dir PATH]

Single-id mode prints `<id>\\t<path>` for the resolved live ADR.
Batch mode prints one JSON object per line:
  {"input": "ADR-007", "resolved": "ADR-012",
   "path": "dekspec/adrs/ADR-012-...md", "chain": ["ADR-007","ADR-012"]}

Exit codes: 0 ok; 2 usage error; 1 unresolvable (cycle / dangling /
missing ADR).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Mirrors `_SUPERSEDED_BY_LINE` / `_ADR_ID_REF` in
# tooling/dekspec/constraint_compiler/parser.py — keep the regexes in sync.
_SUPERSEDED_BY_LINE = re.compile(r"\*Superseded by:\*\s*(.+?)(?=\n|$)", re.MULTILINE)
_ADR_ID_REF = re.compile(r"\bADR-\d{3,}\b")
_ADR_ID = re.compile(r"^ADR-\d{3,}$")

DEFAULT_ADR_DIR = "dekspec/adrs"


class ResolutionError(Exception):
    """A supersession chain could not be resolved (cycle / dangling / missing)."""


def find_adr_path(adr_id: str, adr_dir: Path) -> Path:
    """Return the file for `adr_id` in `adr_dir` (filename starts with the id).

    Raises ResolutionError if no file (or more than one) matches.
    """
    matches = sorted(adr_dir.glob(f"{adr_id}-*.md"))
    # Also accept an exact `ADR-NNN.md` with no slug.
    exact = adr_dir / f"{adr_id}.md"
    if exact.is_file() and exact not in matches:
        matches.append(exact)
    if not matches:
        raise ResolutionError(
            f"{adr_id}: no ADR file found in {adr_dir} "
            f"(looked for '{adr_id}-*.md')"
        )
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise ResolutionError(f"{adr_id}: ambiguous — multiple files match: {names}")
    return matches[0]


def read_superseded_by(adr_path: Path) -> str | None:
    """Return the successor ADR id named by `adr_path`, or None if it is live.

    A `*Superseded by:*` line whose value contains no ADR id (e.g. `none`)
    is treated as no successor.
    """
    body = adr_path.read_text(encoding="utf-8")
    match = _SUPERSEDED_BY_LINE.search(body)
    if not match:
        return None
    ids = _ADR_ID_REF.findall(match.group(1))
    if not ids:
        return None
    # First named id wins; the schema permits an array but a chain walk
    # follows a single successor per hop.
    return ids[0]


def resolve(adr_id: str, adr_dir: Path) -> tuple[str, Path, list[str]]:
    """Walk the supersession chain from `adr_id` to the live ADR.

    Returns (live_id, live_path, chain) where `chain` lists every ADR
    visited including the start and the live ADR.

    Raises ResolutionError on a cycle, a dangling successor, or a
    missing start ADR.
    """
    if not _ADR_ID.match(adr_id):
        raise ResolutionError(f"{adr_id!r}: not a valid ADR id (expected ADR-NNN)")
    chain: list[str] = []
    seen: set[str] = set()
    current = adr_id
    while True:
        if current in seen:
            cycle = " -> ".join([*chain, current])
            raise ResolutionError(f"supersession cycle detected: {cycle}")
        seen.add(current)
        chain.append(current)
        path = find_adr_path(current, adr_dir)
        successor = read_superseded_by(path)
        if successor is None:
            return current, path, chain
        # `find_adr_path` on the next hop surfaces a dangling reference
        # as a ResolutionError with a clear message.
        try:
            find_adr_path(successor, adr_dir)
        except ResolutionError as exc:
            raise ResolutionError(
                f"{current} names successor {successor} but {exc}"
            ) from exc
        current = successor


def _resolve_record(adr_id: str, adr_dir: Path) -> dict[str, object]:
    """Resolve `adr_id`, returning the batch-mode JSON record (raises on failure)."""
    live_id, live_path, chain = resolve(adr_id, adr_dir)
    return {
        "input": adr_id,
        "resolved": live_id,
        "path": str(live_path),
        "chain": chain,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resolve_supersession.py",
        description="Resolve an ADR supersession chain to the live ADR.",
    )
    parser.add_argument(
        "adr_id",
        nargs="?",
        help="ADR id to resolve (e.g. ADR-007). Omit when using --batch.",
    )
    parser.add_argument(
        "--batch",
        metavar="ID1,ID2,...",
        help="Comma-separated ADR ids; emit one JSON record per line.",
    )
    parser.add_argument(
        "--adr-dir",
        default=DEFAULT_ADR_DIR,
        help=f"Directory holding ADR files (default: {DEFAULT_ADR_DIR}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if bool(args.adr_id) == bool(args.batch):
        parser.error("provide exactly one of <ADR-ID> or --batch")

    adr_dir = Path(args.adr_dir)
    if not adr_dir.is_dir():
        print(f"error: ADR directory not found: {adr_dir}", file=sys.stderr)
        return 2

    if args.batch:
        ids = [tok.strip() for tok in args.batch.split(",") if tok.strip()]
        if not ids:
            parser.error("--batch given no ADR ids")
        failed = False
        for adr_id in ids:
            try:
                record = _resolve_record(adr_id, adr_dir)
            except ResolutionError as exc:
                print(f"error: {exc}", file=sys.stderr)
                failed = True
                continue
            print(json.dumps(record))
        return 1 if failed else 0

    try:
        live_id, live_path, _chain = resolve(args.adr_id, adr_dir)
    except ResolutionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{live_id}\t{live_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
