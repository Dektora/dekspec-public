#!/usr/bin/env python3
"""Enrich RAW structural slices into the durable six-field slice manifest.

This is the ENRICHMENT layer above the LLM-free clustering ENGINE (ds-mrsu).
The engine verb `dekspec slices` builds the import graph, clusters it, and
writes a RAW four-field manifest (`member_modules` / `globs` / `cohesion_stats`
/ `coupling_stats`) to `<repo>/.dekspec/slices.json`. This module RE-RUNS that
engine (never re-implements it) via `discover_slices`, then enriches each raw
slice with the two helper-owned fields IC-018 pins:

    name         required, non-null, NON-EMPTY, UNIQUE across the array
    domain_name  string OR null — null iff no glossary / CONTEXT.md / AE anchor

It writes the FULL six-field array back to `<repo>/.dekspec/slices.json`,
conforming to Interface Contract IC-018.

NO-PARTIAL-MANIFEST ordering: the engine writes the raw array FIRST (inside
`discover_slices`). If enrichment then failed we could be left with a raw, not
enriched, file. To guarantee the FINAL committed manifest is never left in a
half-enriched state, enrichment is done fully IN MEMORY and the enriched array
is written in a SINGLE `write_text`; on any enrichment exception we re-raise
WITHOUT writing the enriched form. If the engine itself raises, we never reach
the write and surface the error.

The companion of the `_lib/discover_slices.md` prose helper: the prose is the
operator-facing routine, this script is the mechanism. Importable
(`enrich_and_write(repo)`) for tests, and CLI-runnable for the prose to shell.

Style mirrors `resolve_bead_context.py`: argparse, `cmd_*` dispatcher, `int`
return codes, `main(argv)` entry point. Stdlib + the dekspec engine only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from dekspec.constraint_compiler.slice_discovery import discover_slices

# A domain noun: a Title-Case or lower word of >=3 letters. Used to harvest
# candidate anchors from CONTEXT.md / domain-glossary.md / AE filenames.
_NOUN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")

# Glossary / AE headings of the form `## Constraint Compiler` or `# Foo`.
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _slugify(text: str) -> str:
    """Lower-case, hyphenate a phrase into a stable slice-name slug.

    `Constraint Compiler` -> `constraint-compiler`; `tooling/dekspec` ->
    `tooling-dekspec`. Collapses runs of non-alphanumerics to a single hyphen
    and strips leading/trailing hyphens. Never returns an empty string for
    non-empty alphanumeric input.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug


def _harvest_domain_nouns(repo: Path) -> dict[str, str]:
    """Collect domain anchors from CONTEXT.md / domain-glossary.md / AE files.

    Returns a mapping of lower-cased anchor TOKEN -> the original domain noun
    phrase (preserving its display casing). Best-effort and v1-lightweight: it
    reads headings from `CONTEXT.md`, `dekspec/domain-glossary.md`, and the
    filenames of declared AEs under `dekspec/`. On a non-dekspec repo (no
    `dekspec/` tree) the AE / glossary sources are simply absent and the map is
    built from `CONTEXT.md` alone (or is empty), driving the structural
    fallback in `_derive_name`.
    """
    anchors: dict[str, str] = {}

    def _register(phrase: str) -> None:
        phrase = phrase.strip()
        if not phrase:
            return
        for token in _NOUN_RE.findall(phrase):
            anchors.setdefault(token.lower(), phrase)

    context_md = repo / "CONTEXT.md"
    if context_md.is_file():
        for heading in _HEADING_RE.findall(context_md.read_text(encoding="utf-8")):
            _register(heading)

    glossary = repo / "dekspec" / "domain-glossary.md"
    if glossary.is_file():
        for heading in _HEADING_RE.findall(glossary.read_text(encoding="utf-8")):
            _register(heading)

    dekspec_dir = repo / "dekspec"
    if dekspec_dir.is_dir():
        # Declared AEs: `dekspec/.../AE-002-constraint-compiler.md` — the slug
        # tail after the `AE-NNN-` prefix is the domain noun phrase.
        for ae_path in sorted(dekspec_dir.glob("**/AE-*.md")):
            stem = re.sub(r"^AE-\d+-", "", ae_path.stem)
            _register(stem.replace("-", " "))

    return anchors


def _path_tokens(members: list[str], globs: list[str]) -> list[str]:
    """Ordered, de-duplicated path nouns from a slice's members + globs.

    The dominant top-level dir/package comes first (it drives the structural
    fallback name), followed by the remaining distinct path segments.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    for source in (members, globs):
        for item in source:
            for seg in re.split(r"[/.]", item):
                seg = seg.strip()
                if not seg or seg in {"py", "**", "__init__"}:
                    continue
                low = seg.lower()
                if low not in seen:
                    seen.add(low)
                    tokens.append(seg)
    return tokens


def _dominant_package(members: list[str]) -> str:
    """The most common top-level path segment across member modules.

    `alpha/a1.py`, `alpha/a2.py` -> `alpha`. Falls back to the first member's
    stem for flat single-file slices. Never empty for a non-empty slice.
    """
    counts: dict[str, int] = {}
    order: list[str] = []
    for mod in members:
        head = mod.split("/", 1)[0]
        head = head[:-3] if head.endswith(".py") else head
        if head not in counts:
            order.append(head)
        counts[head] = counts.get(head, 0) + 1
    # Most frequent wins; ties break on first-seen order for determinism.
    return max(order, key=lambda h: (counts[h], -order.index(h)))


def _derive_name(
    raw: dict[str, Any], anchors: dict[str, str]
) -> tuple[str, str | None]:
    """Derive a (name, domain_name) pair for one raw slice.

    Matches the slice's path nouns against harvested domain anchors. On a hit,
    `domain_name` is the anchor's display phrase and `name` is its slug. On no
    hit (e.g. a non-dekspec repo), `domain_name` is `None` and `name` falls
    back to the slug of the slice's dominant top-level package. Never empty.
    """
    members = list(raw.get("member_modules", []))
    globs = list(raw.get("globs", []))

    for token in _path_tokens(members, globs):
        phrase = anchors.get(token.lower())
        if phrase:
            name = _slugify(phrase) or _slugify(token)
            return name or token.lower(), phrase

    # Structural fallback: no domain anchor found.
    dominant = _dominant_package(members) if members else ""
    name = _slugify(dominant) or _slugify(members[0] if members else "slice")
    return name or "slice", None


def _disambiguate(name: str, taken: set[str], raw: dict[str, Any]) -> str:
    """Make `name` unique against `taken`, deterministically.

    First tries appending a distinguishing path segment from the slice's
    dominant member; if still colliding (or none available), appends `-2`,
    `-3`, … until free. The chosen name is registered in `taken` by the caller.
    """
    if name not in taken:
        return name

    members = list(raw.get("member_modules", []))
    if members:
        # Append the second path segment of the first member as a discriminator.
        first = members[0]
        segs = [s for s in re.split(r"[/.]", first) if s and not s.endswith("py")]
        if len(segs) >= 2:
            candidate = f"{name}-{_slugify(segs[1])}"
            if candidate and candidate not in taken:
                return candidate

    suffix = 2
    while f"{name}-{suffix}" in taken:
        suffix += 1
    return f"{name}-{suffix}"


def _enrich(raw_slices: list[dict[str, Any]], repo: Path) -> list[dict[str, Any]]:
    """Enrich every raw slice into a six-field entry, in memory.

    Builds the domain-anchor map once, derives (name, domain_name) per slice,
    and enforces `name` uniqueness across the array before returning. Does no
    I/O — the caller is responsible for the single atomic write so a failure
    here leaves no partial manifest.
    """
    anchors = _harvest_domain_nouns(repo)
    enriched: list[dict[str, Any]] = []
    taken: set[str] = set()

    for raw in raw_slices:
        name, domain_name = _derive_name(raw, anchors)
        name = _disambiguate(name, taken, raw)
        taken.add(name)
        # Preserve the four engine-owned fields verbatim; add the two
        # helper-owned fields. domain_name is independent of name — a null
        # domain_name never empties out name.
        enriched.append(
            {
                "name": name,
                "globs": raw["globs"],
                "member_modules": raw["member_modules"],
                "cohesion_stats": raw["cohesion_stats"],
                "coupling_stats": raw["coupling_stats"],
                "domain_name": domain_name,
            }
        )
    return enriched


def _write_manifest(repo: Path, slices: list[dict[str, Any]]) -> Path:
    """Write the enriched array to `<repo>/.dekspec/slices.json`.

    Mirrors the engine's `_write_manifest` encoding: UTF-8, two-space indent,
    trailing newline. A single `write_text` — the no-partial-manifest guarantee.
    """
    state_dir = repo / ".dekspec"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "slices.json"
    manifest.write_text(json.dumps(slices, indent=2) + "\n", encoding="utf-8")
    return manifest


def enrich_and_write(repo: str | Path) -> Path:
    """Re-run the engine, enrich the raw slices, and write the manifest.

    1. `discover_slices(repo)` re-runs the engine (building + clustering the
       import graph) and returns the RAW four-field slices. If the engine
       raises, the error PROPAGATES and NO enriched manifest is written.
    2. Enrichment is performed fully IN MEMORY (`_enrich`); on any enrichment
       exception we re-raise WITHOUT writing the enriched form.
    3. Only once every entry is enriched do we write the full six-field array
       in a single `write_text`.

    Returns the manifest Path (`<repo>/.dekspec/slices.json`).
    """
    repo_path = Path(repo).resolve()
    raw_slices = discover_slices(repo_path)  # may raise -> propagates, no write
    enriched = _enrich(raw_slices, repo_path)  # may raise -> propagates, no write
    return _write_manifest(repo_path, enriched)


def cmd_enrich(args: argparse.Namespace) -> int:
    """CLI dispatcher: enrich and report the written manifest path."""
    manifest = enrich_and_write(args.at)
    print(str(manifest))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="enrich_slices.py",
        description=(
            "Re-run the dekspec slices engine, enrich each raw slice with a "
            "domain-anchored name + domain_name (IC-018), and write the full "
            "six-field manifest to <repo>/.dekspec/slices.json."
        ),
    )
    parser.add_argument(
        "at",
        nargs="?",
        default=".",
        metavar="REPO_PATH",
        help="Repository root to enrich (default: current directory).",
    )
    parser.set_defaults(func=cmd_enrich)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover — exercised via import in tests
    sys.exit(main())
