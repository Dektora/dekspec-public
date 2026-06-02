#!/usr/bin/env python3
"""Intent serialization advisory for the /write-intent skill.

ADR-016 (Scope Intent serialization to per-Mission and downgrade enforcement to
advisory) governs this check. The pre-ADR-016 rule — one active Intent at a time
across the whole repo, hard-enforced as a creation-blocking refuse — is retired.

Current model (ADR-016):
  - Within a single Mission, at most one child Intent should be in active status
    at a time — child Intents are dependency-ordered, so the Mission's Intent
    queue is also its serialization queue.
  - Across distinct Missions, and for Mission-less standalone Intents, there is
    no serialization limit.
  - Enforcement is advisory: this script REPORTS per-Mission concurrency; it
    never refuses creation. The gate of record is `dekspec audit linkage`.

Active (in-flight) statuses: DRAFT | PROPOSED | ACCEPTED | IMPLEMENTING |
TESTPASS | MERGED. OVERSIZED (paused), LOCKED and SUPERSEDED (terminal) are
not counted as active. (`TODO` + `TESTFAIL` retired 2026-05-25 — E3 audit —
and are no longer in the Intent enum.)

Stdlib-only (vendored where the `dekspec` engine is not importable).

Runnable:   python serialization_guard.py [--intents-dir DIR] [--json]
Importable: from serialization_guard import scan_active_intents, missions_over_cap
Exit codes: 0 = scan completed (always — advisory, never refuses); 1 = error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Statuses counted as in-flight for the per-Mission advisory (ADR-016).
# `TODO` + `TESTFAIL` retired from the Intent enum 2026-05-25 (E3 audit).
ACTIVE_STATUSES: frozenset[str] = frozenset(
    {
        "DRAFT",
        "PROPOSED",
        "ACCEPTED",
        "IMPLEMENTING",
        "TESTPASS",
        "MERGED",
    }
)
# Not counted: OVERSIZED (paused), LOCKED / SUPERSEDED (terminal).

_STATUS_SECTION = re.compile(r"^#+[ \t]+Status[ \t]*$", re.MULTILINE)
_MISSION_SECTION = re.compile(r"^#+[ \t]+Mission[ \t]*$", re.MULTILINE)
_TITLE_LINE = re.compile(r"^#[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
_MSN_TOKEN = re.compile(r"MSN-\d+", re.IGNORECASE)


def _read_section_token(text: str, section_re: re.Pattern[str]) -> str | None:
    """Return the first non-blank, non-italic content line of a `## <Section>`."""
    m = section_re.search(text)
    if not m:
        return None
    for line in text[m.end():].splitlines():
        s = line.strip()
        if s.startswith("#"):
            break
        if not s:
            continue
        # Skip italic annotation lines (*Valid statuses:* ..., rationale prose).
        if s.startswith("*") and s.endswith("*"):
            continue
        return s
    return None


def _read_status(text: str) -> str | None:
    line = _read_section_token(text, _STATUS_SECTION)
    return line.split()[0].strip("`*") if line else None


def _read_mission(text: str) -> str:
    """Return the Mission ID (MSN-NNN, upper-cased) or "none" if Mission-less."""
    line = _read_section_token(text, _MISSION_SECTION)
    if not line:
        return "none"
    m = _MSN_TOKEN.search(line)
    return m.group(0).upper() if m else "none"


def _read_title(text: str) -> str:
    m = _TITLE_LINE.search(text)
    return m.group("title").strip() if m else "(untitled)"


def scan_active_intents(intents_dir: Path) -> list[dict[str, str]]:
    """Return a list of {path, status, mission, title} for every active Intent.

    A non-existent `intents_dir` yields an empty list (first Intent in the repo).
    """
    if not intents_dir.is_dir():
        return []
    active: list[dict[str, str]] = []
    for path in sorted(intents_dir.glob("INT-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        status = _read_status(text)
        if status and status.upper() in ACTIVE_STATUSES:
            active.append(
                {
                    "path": str(path),
                    "status": status.upper(),
                    "mission": _read_mission(text),
                    "title": _read_title(text),
                }
            )
    return active


def missions_over_cap(
    active: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Return {MSN-NNN: [active Intent records]} for Missions with > 1 active Intent.

    Mission-less Intents (mission == "none") are never reported — ADR-016 places
    no serialization limit on the standalone pool.
    """
    by_mission: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rec in active:
        if rec["mission"] != "none":
            by_mission[rec["mission"]].append(rec)
    return {msn: recs for msn, recs in by_mission.items() if len(recs) > 1}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="serialization_guard.py",
        description=(
            "Advisory per-Mission Intent serialization report (ADR-016). "
            "Never refuses creation."
        ),
    )
    parser.add_argument(
        "--intents-dir",
        default="dekspec/intents",
        help="Directory holding INT-*.md files (default: dekspec/intents).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    args = parser.parse_args(argv)

    intents_dir = Path(args.intents_dir)
    active = scan_active_intents(intents_dir)
    over_cap = missions_over_cap(active)

    if args.json:
        print(
            json.dumps(
                {
                    "active_count": len(active),
                    "active": active,
                    "missions_over_cap": over_cap,
                },
                indent=2,
            )
        )
    else:
        if not over_cap:
            print(
                f"Serialization advisory: clean. {len(active)} active Intent(s); "
                "no Mission carries more than one."
            )
        else:
            print(
                "Serialization advisory (ADR-016): the following Mission(s) "
                "carry more than one active Intent. Child Intents are "
                "dependency-ordered — review before authoring concurrently. "
                "This is advisory; creation is NOT blocked."
            )
            for msn, recs in sorted(over_cap.items()):
                print(f"  {msn}: {len(recs)} active")
                for rec in recs:
                    print(f"    [{rec['status']}] {rec['path']} — {rec['title']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
