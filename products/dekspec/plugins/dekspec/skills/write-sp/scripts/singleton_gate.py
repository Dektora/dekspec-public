#!/usr/bin/env python3
"""Singleton-vs-multi-context decision gate for the /write-sp skill.

write-sp Create Mode Step 2 asks: if the corpus already has an SP-001 *singleton*
(an SP whose `bounded_context` is ABSENT — it covers the whole repo), then any
new SP MUST declare its own `bounded_context`. This script does the mechanical
half of that gate: it scans `dekspec/security-profiles/` and reports whether a
singleton SP-001 exists.

`requires_bounded_context` is True when a singleton SP-001 is present — meaning
the Create-Mode subagent must require the engineer to name a `bounded_context`
for the new SP. It is False when the corpus has no SP at all (the engineer is
free to author the singleton or a first-of-many) OR when SP-001 already declares
a `bounded_context` (the corpus is already multi-context; consistency is fine).

"Singleton" detection: an SP file is a singleton iff it has NO `## Bounded
Context` section, or that section's body resolves to an absent value (`none` /
`n/a` / empty / `<engineer-fills-here>`). This mirrors SP-001's on-disk shape,
which omits the section entirely.

Stdlib-only. Importable + argparse CLI.

Runnable:   python singleton_gate.py [--sp-dir DIR] [--json]
Importable: from singleton_gate import inspect_corpus
Exit codes: 0 always on a successful scan; 1 on error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ABSENT_TOKENS = {"none", "n/a", "na", "-", "absent", "", "<engineer-fills-here>"}
_BOUNDED_SECTION = re.compile(
    r"^#+[ \t]+Bounded Context[ \t]*$", re.MULTILINE
)


def _bounded_context(text: str) -> str | None:
    """Return the SP's bounded_context value, or None if absent/unset."""
    m = _BOUNDED_SECTION.search(text)
    if not m:
        return None
    for line in text[m.end():].splitlines():
        s = line.strip()
        if s.startswith("#"):
            break
        if not s:
            continue
        # Skip table headers / separators / italic annotations.
        if s.startswith("|") or s.startswith("*"):
            continue
        token = s.strip("`* ").lower()
        if token in _ABSENT_TOKENS:
            return None
        return s.strip("`* ")
    return None


def _sp_id(text: str, path: Path) -> str:
    m = re.search(r"^#+[ \t]+ID[ \t]*$\n+(?P<v>SP-\d+)", text, re.MULTILINE)
    if m:
        return m.group("v")
    fm = re.search(r"SP-(\d+)", path.name, re.IGNORECASE)
    return f"SP-{fm.group(1)}" if fm else path.stem


def inspect_corpus(sp_dir: Path) -> dict[str, object]:
    """Scan the SP directory; report singleton state + the gate decision."""
    profiles: list[dict[str, object]] = []
    if sp_dir.is_dir():
        for path in sorted(sp_dir.glob("SP-*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            bc = _bounded_context(text)
            profiles.append(
                {
                    "id": _sp_id(text, path),
                    "path": str(path),
                    "bounded_context": bc,
                    "is_singleton": bc is None,
                }
            )

    sp001 = next(
        (p for p in profiles if str(p["id"]).upper() == "SP-001"), None
    )
    singleton_sp001 = bool(sp001 and sp001["is_singleton"])

    return {
        "sp_dir": str(sp_dir),
        "profile_count": len(profiles),
        "profiles": profiles,
        "singleton_sp001_present": singleton_sp001,
        "requires_bounded_context": singleton_sp001,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="singleton_gate.py",
        description="Decide whether a new SP must declare a bounded_context.",
    )
    parser.add_argument(
        "--sp-dir",
        default="dekspec/security-profiles",
        help="Security-profile directory (default: dekspec/security-profiles).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    args = parser.parse_args(argv)

    try:
        result = inspect_corpus(Path(args.sp_dir))
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["requires_bounded_context"]:
            print(
                "GATE: a singleton SP-001 exists — any new SP MUST declare a "
                "bounded_context."
            )
        elif result["profile_count"] == 0:
            print(
                "GATE: no SP in the corpus — the engineer may author the "
                "singleton SP-001 (no bounded_context) or a first-of-many."
            )
        else:
            print(
                "GATE: corpus is already multi-context (SP-001 declares a "
                "bounded_context or is absent) — no singleton constraint."
            )
        for p in result["profiles"]:  # type: ignore[union-attr]
            bc = p["bounded_context"] or "(singleton — no bounded_context)"
            print(f"  {p['id']}: {bc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
