#!/usr/bin/env python3
"""Deterministic corrections-log operations for /write-corrections.

Split out of `write-ggc/scripts/ggc_ops.py` by INT-191, which partitioned that
skill into `/write-glossary` (terms) and `/write-corrections` (the recurrence
pipeline). This file carries the **correction-side** half: slug generation,
appending a dated recurrence line + recomputing the count, detecting the
promotion threshold, and flipping a promoted entry's status. The glossary-side
half (`find-synonym`) went to `write-glossary/scripts/glossary_ops.py`.

The seam between the two skills is `promote`, and it is deliberate. This
script owns the threshold and the decision that an entry has earned promotion;
it marks the entry promoted and returns its Correction text. **Composing and
writing the glossary row is `/write-glossary`'s job** — nothing here touches
`dekspec/domain-glossary.md`.

Subcommands:

  slugify <text>
      Emit a lowercase, hyphenated slug derived from the correction text.

  add-recurrence <slug> --source S --desc D [--date YYYY-MM-DD]
      Append a `- DATE — SOURCE — DESC` recurrence line under the entry's
      `- **Recurrences:**` list in the corrections log, update its count, and
      report the new count plus `promote_ready` (True when count >= 3).

  promote <slug>
      Mark the entry `- **Status:** promoted to glossary DATE` and report its
      Correction text so `/write-glossary` can compose the row from it. This
      command does not read or write the glossary.

The corrections log defaults to `dekspec/terminology-corrections.md` (renamed
from `guidance-and-corrections.md` by INT-191) and may not exist; commands
degrade gracefully. Promotion threshold is 3 — a system constant per
write-corrections/SKILL.md Rules, unchanged by the split.

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

CORRECTIONS_PATH = "dekspec/terminology-corrections.md"
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
# corrections-log entry parsing
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
    corrections_path: Path,
    slug: str,
    source: str,
    desc: str,
    date: str | None = None,
) -> dict[str, object]:
    if not corrections_path.is_file():
        raise FileNotFoundError(f"corrections log not found: {corrections_path}")
    date = date or datetime.date.today().isoformat()
    text = corrections_path.read_text(encoding="utf-8")
    span = _entry_span(text, slug)
    if span is None:
        raise KeyError(f"no correction entry with slug '{slug}'")
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
    corrections_path.write_text(new_text, encoding="utf-8")

    count = _count_recurrences(block)
    return {
        "slug": slug,
        "count": count,
        "threshold": PROMOTION_THRESHOLD,
        "promote_ready": count >= PROMOTION_THRESHOLD,
        "recurrence_added": new_line.strip(),
    }


# --------------------------------------------------------------------------
# promote — the hand-off seam to /write-glossary
# --------------------------------------------------------------------------
def promote(
    corrections_path: Path, slug: str, date: str | None = None
) -> dict[str, object]:
    if not corrections_path.is_file():
        raise FileNotFoundError(f"corrections log not found: {corrections_path}")
    date = date or datetime.date.today().isoformat()
    text = corrections_path.read_text(encoding="utf-8")
    span = _entry_span(text, slug)
    if span is None:
        raise KeyError(f"no correction entry with slug '{slug}'")
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
    corrections_path.write_text(new_text, encoding="utf-8")
    return {
        "slug": slug,
        "count": count,
        "below_threshold": count < PROMOTION_THRESHOLD,
        "status_set": status_line,
        "correction": _correction_text(block),
        "note": (
            "Corrections-log status flipped. Hand the Correction text above "
            "to /dekspec:write-glossary --add-term — composing and writing "
            "the glossary row is that skill's job, not this one's."
        ),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="corrections_ops.py",
        description="Deterministic corrections-log operations.",
    )
    parser.add_argument(
        "--corrections-file",
        default=CORRECTIONS_PATH,
        help=f"Path to the corrections log (default: {CORRECTIONS_PATH}).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_slug = sub.add_parser("slugify", help="Generate a slug from text.")
    p_slug.add_argument("text", help="Free text to slugify.")

    p_add = sub.add_parser(
        "add-recurrence", help="Append a recurrence to a correction entry."
    )
    p_add.add_argument("slug", help="The correction entry slug.")
    p_add.add_argument("--source", required=True, help="Source artifact/context.")
    p_add.add_argument("--desc", required=True, help="Brief mistake description.")
    p_add.add_argument("--date", help="Override date (YYYY-MM-DD).")

    p_prom = sub.add_parser("promote", help="Mark a correction entry promoted.")
    p_prom.add_argument("slug", help="The correction entry slug.")
    p_prom.add_argument("--date", help="Override date (YYYY-MM-DD).")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "slugify":
            print(json.dumps({"slug": slugify(args.text)}))
            return 0
        if args.cmd == "add-recurrence":
            result = add_recurrence(
                Path(args.corrections_file),
                args.slug,
                args.source,
                args.desc,
                args.date,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.cmd == "promote":
            result = promote(Path(args.corrections_file), args.slug, args.date)
            print(json.dumps(result, indent=2))
            return 0
    except (FileNotFoundError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error("unknown subcommand")
    return 1


if __name__ == "__main__":
    sys.exit(main())
