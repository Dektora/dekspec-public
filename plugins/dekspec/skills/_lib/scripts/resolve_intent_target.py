#!/usr/bin/env python3
"""Resolve an orchestrate-intent / spec-intent target argument to a concrete
Intent file — canonical OR provisional (ds-jtfn).

The conductor (`orchestrate-intent`) and the spec phase-executor
(`spec-intent`) historically resolved only a CANONICAL `INT-NNN` id/path under
`dekspec/intents/`. Per the provisional-first default (INT-133) most freshly
authored Intents start life in a provisional incubation
(`dekspec/provisional/<slug>/`, no canonical id allocated yet). This resolver
accepts either form so the lifecycle walk can START on a provisional Intent;
the canonical `INT-NNN` is allocated later at the accept gate's INT-082
Provisional Promotion step (which `--auto` already governs via the existing
`analyze-complete` / `accept-clean` pre-conditions — no new gate).

Accepted argument forms:
  - canonical id            `INT-036`
  - canonical path          `dekspec/intents/INT-036-foo.md`
  - provisional slug        `my-incubation-slug`     (-> dekspec/provisional/<slug>/INT*.md)
  - provisional path        `dekspec/provisional/<slug>/INT-provisional-foo.md`

Emits JSON: {"kind": "canonical"|"provisional", "path": "...",
             "intent_id": "INT-NNN"|null, "status": "...", "is_provisional": bool}

Exit 0 on a unique resolution; exit 1 (with a stderr message) when the target
cannot be resolved or is ambiguous.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_INT_ID_RE = re.compile(r"^INT-\d{3,}$")
_INT_ID_IN_NAME_RE = re.compile(r"\bINT-\d{3,}\b")
_STATUS_RE = re.compile(r"^##[ \t]+Status[ \t]*$", re.MULTILINE)


class ResolveError(Exception):
    pass


def _read_status(path: Path) -> str | None:
    """Return the first token of the `## Status` section body, or None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _STATUS_RE.search(text)
    if not m:
        return None
    tail = text[m.end():]
    for line in tail.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            if s.startswith("##"):
                break
            continue
        return s.split()[0].strip("`*")
    return None


def _intent_id_from_name(name: str) -> str | None:
    m = _INT_ID_IN_NAME_RE.search(name)
    return m.group(0) if m else None


def _provisional_int_file(folder: Path) -> Path:
    """Return the single Intent (`INT*.md`) file inside a provisional folder."""
    matches = sorted(folder.glob("INT*.md"))
    if not matches:
        raise ResolveError(
            f"no Intent file (INT*.md) found in provisional incubation {folder}"
        )
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise ResolveError(
            f"ambiguous provisional incubation {folder} — multiple Intent "
            f"files: {names}. Pass the explicit file path."
        )
    return matches[0]


def resolve(arg: str, repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    arg = arg.strip()

    # 1. An existing path (canonical or provisional) — use it directly.
    candidate = (repo_root / arg) if not Path(arg).is_absolute() else Path(arg)
    if candidate.is_file():
        is_prov = "provisional" in {p.name for p in candidate.parents}
        return _result(candidate, repo_root, is_prov)

    # 2. A provisional incubation folder path.
    if candidate.is_dir() and "provisional" in {p.name for p in [candidate, *candidate.parents]}:
        return _result(_provisional_int_file(candidate), repo_root, True)

    # 3. A bare canonical id `INT-NNN`.
    if _INT_ID_RE.match(arg):
        hits = sorted((repo_root / "dekspec" / "intents").glob(f"{arg}-*.md"))
        if len(hits) == 1:
            return _result(hits[0], repo_root, False)
        if len(hits) > 1:
            raise ResolveError(f"ambiguous canonical id {arg}: {[h.name for h in hits]}")
        # Fall back: the id may live in a provisional folder (pre-numbered).
        prov = sorted((repo_root / "dekspec" / "provisional").glob(f"*/{arg}-*.md"))
        if len(prov) == 1:
            return _result(prov[0], repo_root, True)
        if len(prov) > 1:
            raise ResolveError(f"ambiguous provisional id {arg}: {[h.name for h in prov]}")
        raise ResolveError(f"no Intent file found for canonical id {arg}")

    # 4. A bare provisional slug -> dekspec/provisional/<slug>/INT*.md.
    folder = repo_root / "dekspec" / "provisional" / arg
    if folder.is_dir():
        return _result(_provisional_int_file(folder), repo_root, True)

    raise ResolveError(
        f"could not resolve {arg!r} to a canonical INT-NNN, a canonical/"
        f"provisional Intent path, or a provisional incubation slug"
    )


def _result(path: Path, repo_root: Path, is_provisional: bool) -> dict:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    return {
        "kind": "provisional" if is_provisional else "canonical",
        "path": rel,
        "intent_id": None if is_provisional else _intent_id_from_name(path.name),
        "status": _read_status(path),
        "is_provisional": is_provisional,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Resolve an Intent target (canonical or provisional) for orchestrate-intent / spec-intent.")
    ap.add_argument("target", help="INT-NNN, a canonical/provisional Intent path, or a provisional incubation slug.")
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args(argv)
    try:
        result = resolve(args.target, Path(args.repo_root))
    except ResolveError as exc:
        print(f"resolve-intent-target: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
