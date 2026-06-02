#!/usr/bin/env python3
"""Deterministic Glossary/Guidance/Corrections (GGC) operations for /write-ggc.

The write-ggc skill body spells out several mechanical steps as prose: slug
generation, appending a dated recurrence line + recomputing the count,
detecting the promotion threshold, moving a promoted entry's row into the
glossary, and finding candidate synonym matches. This script does the
deterministic half; the model still judges semantic matches.

Subcommands:

  slugify <text>
      Emit a lowercase, hyphenated slug derived from the correction text.

  add-recurrence <slug> --source S --desc D [--date YYYY-MM-DD]
      Append a `- DATE — SOURCE — DESC` recurrence line under the entry's
      `- **Recurrences:**` list in the g&c file, update its count, and report
      the new count plus `promote_ready` (True when count >= 3).

  promote <slug>
      Mark the g&c entry `- **Status:** promoted to glossary DATE`. (The
      glossary ROW authoring is a judgment step the model performs — this
      command only flips the g&c status surgically and reports the entry's
      Correction text so the agent can compose the glossary row.)

  find-synonym <term>
      Return candidate glossary rows + g&c slugs whose text overlaps the term.
      Heuristic only — the agent decides whether a candidate is a true synonym.

The g&c file (default `dekspec/guidance-and-corrections.md`) and the glossary
(`dekspec/domain-glossary.md`) may not exist; commands degrade gracefully.
Promotion threshold is 3 (a system constant per write-ggc/SKILL.md Rules).

Stdlib-only. Importable + argparse CLI. Mutations are surgical line edits.

Exit codes: 0 = success; 1 = error (missing file, unknown slug, etc.).
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

PROMOTION_THRESHOLD = 3
_RECURRENCE_LINE = re.compile(r"^\s*-\s+\d{4}-\d{2}-\d{2}\s+—")


# --------------------------------------------------------------------------
# slugify
# --------------------------------------------------------------------------
def slugify(text: str, max_words: int = 8) -> str:
    """Lowercase, hyphenate; strip punctuation; cap at `max_words` words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:max_words]) or "entry"


# --------------------------------------------------------------------------
# g&c entry parsing
# --------------------------------------------------------------------------
def _entry_span(text: str, slug: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the `### slug` entry block."""
    pat = re.compile(
        rf"^###[ \t]+{re.escape(slug)}[ \t]*$", re.MULTILINE
    )
    m = pat.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^#{1,3}[ \t]+\S", rest, re.MULTILINE)
    end = m.end() + (nxt.start() if nxt else len(rest))
    return (m.start(), end)


def _count_recurrences(block: str) -> int:
    return sum(1 for line in block.splitlines() if _RECURRENCE_LINE.match(line))


def _correction_text(block: str) -> str:
    m = re.search(r"-\s+\*\*Correction:\*\*[ \t]*(.+)", block)
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------
# add-recurrence
# --------------------------------------------------------------------------
def add_recurrence(
    gc_path: Path,
    slug: str,
    source: str,
    desc: str,
    date: str | None = None,
) -> dict[str, object]:
    if not gc_path.is_file():
        raise FileNotFoundError(f"g&c file not found: {gc_path}")
    date = date or datetime.date.today().isoformat()
    text = gc_path.read_text(encoding="utf-8")
    span = _entry_span(text, slug)
    if span is None:
        raise KeyError(f"no g&c entry with slug '{slug}'")
    start, end = span
    block = text[start:end]

    rec_hdr = re.search(r"^(\s*)-\s+\*\*Recurrences:\*\*\s*$", block, re.MULTILINE)
    new_line = f"  - {date} — {source} — {desc}"
    if rec_hdr:
        # Find the position after the last existing recurrence line (or the
        # header itself if there are none yet).
        insert_at = rec_hdr.end()
        for m in re.finditer(r"^\s*-\s+\d{4}-\d{2}-\d{2}\s+—.*$", block, re.MULTILINE):
            insert_at = max(insert_at, m.end())
        block = block[:insert_at] + "\n" + new_line + block[insert_at:]
    else:
        # No Recurrences sub-list yet — append one at the end of the block.
        block = block.rstrip("\n") + (
            f"\n- **Recurrences:**\n{new_line}\n"
        )

    new_text = text[:start] + block + text[end:]
    gc_path.write_text(new_text, encoding="utf-8")

    count = _count_recurrences(block)
    return {
        "slug": slug,
        "count": count,
        "threshold": PROMOTION_THRESHOLD,
        "promote_ready": count >= PROMOTION_THRESHOLD,
        "recurrence_added": new_line.strip(),
    }


# --------------------------------------------------------------------------
# promote
# --------------------------------------------------------------------------
def promote(
    gc_path: Path, slug: str, date: str | None = None
) -> dict[str, object]:
    if not gc_path.is_file():
        raise FileNotFoundError(f"g&c file not found: {gc_path}")
    date = date or datetime.date.today().isoformat()
    text = gc_path.read_text(encoding="utf-8")
    span = _entry_span(text, slug)
    if span is None:
        raise KeyError(f"no g&c entry with slug '{slug}'")
    start, end = span
    block = text[start:end]
    count = _count_recurrences(block)
    status_line = f"- **Status:** promoted to glossary {date}"

    existing = re.search(r"^-\s+\*\*Status:\*\*.*$", block, re.MULTILINE)
    if existing:
        block = block[: existing.start()] + status_line + block[existing.end():]
    else:
        block = block.rstrip("\n") + "\n" + status_line + "\n"

    new_text = text[:start] + block + text[end:]
    gc_path.write_text(new_text, encoding="utf-8")
    return {
        "slug": slug,
        "count": count,
        "below_threshold": count < PROMOTION_THRESHOLD,
        "status_set": status_line,
        "correction": _correction_text(block),
        "note": (
            "g&c status flipped; compose the glossary row from the "
            "Correction text above (judgment step)."
        ),
    }


# --------------------------------------------------------------------------
# find-synonym
# --------------------------------------------------------------------------
def find_synonym(
    term: str, glossary_path: Path, gc_path: Path
) -> dict[str, object]:
    """Return glossary rows + g&c slugs whose text overlaps `term`."""
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

    gc_hits: list[str] = []
    if gc_path.is_file():
        for m in re.finditer(
            r"^###[ \t]+(.+?)[ \t]*$",
            gc_path.read_text(encoding="utf-8"),
            re.MULTILINE,
        ):
            slug = m.group(1).strip()
            slug_words = set(re.findall(r"[a-z0-9]+", slug.lower()))
            if needles & slug_words:
                gc_hits.append(slug)

    return {
        "term": term,
        "glossary_candidates": glossary_hits,
        "gc_candidates": gc_hits,
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
        prog="ggc_ops.py",
        description="Deterministic Glossary/Guidance/Corrections operations.",
    )
    parser.add_argument(
        "--gc-file",
        default="dekspec/guidance-and-corrections.md",
        help="Path to the g&c file (default: dekspec/guidance-and-corrections.md).",
    )
    parser.add_argument(
        "--glossary",
        default="dekspec/domain-glossary.md",
        help="Path to the glossary (default: dekspec/domain-glossary.md).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_slug = sub.add_parser("slugify", help="Generate a slug from text.")
    p_slug.add_argument("text", help="Free text to slugify.")

    p_add = sub.add_parser(
        "add-recurrence", help="Append a recurrence to a g&c entry."
    )
    p_add.add_argument("slug", help="The g&c entry slug.")
    p_add.add_argument("--source", required=True, help="Source artifact/context.")
    p_add.add_argument("--desc", required=True, help="Brief mistake description.")
    p_add.add_argument("--date", help="Override date (YYYY-MM-DD).")

    p_prom = sub.add_parser("promote", help="Mark a g&c entry promoted.")
    p_prom.add_argument("slug", help="The g&c entry slug.")
    p_prom.add_argument("--date", help="Override date (YYYY-MM-DD).")

    p_syn = sub.add_parser(
        "find-synonym", help="Find candidate glossary/g&c synonym matches."
    )
    p_syn.add_argument("term", help="Term to search for.")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "slugify":
            print(json.dumps({"slug": slugify(args.text)}))
            return 0
        if args.cmd == "add-recurrence":
            result = add_recurrence(
                Path(args.gc_file),
                args.slug,
                args.source,
                args.desc,
                args.date,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.cmd == "promote":
            result = promote(Path(args.gc_file), args.slug, args.date)
            print(json.dumps(result, indent=2))
            return 0
        if args.cmd == "find-synonym":
            result = find_synonym(
                args.term, Path(args.glossary), Path(args.gc_file)
            )
            print(json.dumps(result, indent=2))
            return 0
    except (FileNotFoundError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error("unknown subcommand")
    return 1


if __name__ == "__main__":
    sys.exit(main())
