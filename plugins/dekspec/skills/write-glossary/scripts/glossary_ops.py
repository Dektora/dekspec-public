#!/usr/bin/env python3
"""Deterministic glossary operations for /write-glossary.

The glossary half of the former `ggc_ops.py`, carried over unchanged by
INT-191 when `write-ggc` split into `/dekspec:write-glossary` and
`/dekspec:write-corrections`. The correction-side helpers (`slugify`,
`add-recurrence`, `promote`) live in the `write-corrections` skill folder;
only the duplicate/synonym check is a glossary concern, so only it lives here.

The duplication is deliberate. A cross-skill import would couple two skill
folders that are vendored independently into consumer repos; a copied helper
file is the lesser evil (INT-191 records the decision).

Subcommands:

  find-synonym <term>
      Return candidate glossary rows + correction slugs whose text overlaps
      the term. Heuristic only -- the agent decides whether a candidate is a
      true synonym. This is Add-Term Mode Step 3's deterministic half.

The glossary (`dekspec/domain-glossary.md`) and the corrections log
(`dekspec/terminology-corrections.md`) may not exist; the command degrades
gracefully. Both files are read-only here -- nothing in this module writes.

Stdlib-only. Importable + argparse CLI, matching `extract_candidates.py`.

Exit codes: 0 = success; 1 = error (unreadable file, bad arguments).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# --------------------------------------------------------------------------
# find-synonym
# --------------------------------------------------------------------------
def find_synonym(
    term: str, glossary_path: Path, corrections_path: Path
) -> dict[str, object]:
    """Return glossary rows + correction slugs whose text overlaps `term`."""
    needles = {w for w in re.findall(r"[a-z0-9]+", term.lower()) if len(w) > 2}

    glossary_hits: list[dict[str, str]] = []
    if glossary_path.is_file():
        for line in glossary_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s.startswith("|") or set(s) <= {"|", "-", ":", " "}:
                continue
            cells = [c.strip(" *") for c in s.strip("|").split("|")]
            if not cells or cells[0].lower() in {"term", "constraint", "rule"}:
                continue
            row_words = set(re.findall(r"[a-z0-9]+", " ".join(cells).lower()))
            if needles & row_words:
                glossary_hits.append(
                    {"term": cells[0], "row": s}
                )

    correction_hits: list[str] = []
    if corrections_path.is_file():
        for m in re.finditer(
            r"^###[ \t]+(.+?)[ \t]*$",
            corrections_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        ):
            slug = m.group(1).strip()
            slug_words = set(re.findall(r"[a-z0-9]+", slug.lower()))
            if needles & slug_words:
                correction_hits.append(slug)

    return {
        "term": term,
        "glossary_candidates": glossary_hits,
        "correction_candidates": correction_hits,
        "note": (
            "Heuristic word-overlap match — the agent judges whether any "
            "candidate is a true synonym."
        ),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="glossary_ops.py",
        description="Deterministic glossary operations (read-only).",
    )
    parser.add_argument(
        "--glossary",
        default="dekspec/domain-glossary.md",
        help="Path to the glossary (default: dekspec/domain-glossary.md).",
    )
    parser.add_argument(
        "--corrections-file",
        default="dekspec/terminology-corrections.md",
        help=(
            "Path to the corrections log "
            "(default: dekspec/terminology-corrections.md)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_syn = sub.add_parser(
        "find-synonym",
        help="Find candidate glossary / corrections synonym matches.",
    )
    p_syn.add_argument("term", help="Term to search for.")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "find-synonym":
            result = find_synonym(
                args.term, Path(args.glossary), Path(args.corrections_file)
            )
            print(json.dumps(result, indent=2))
            return 0
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error("unknown subcommand")
    return 1


if __name__ == "__main__":
    sys.exit(main())
