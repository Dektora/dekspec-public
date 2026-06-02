#!/usr/bin/env python3
"""Resolve Constitution ADR / AE cross-references against the artifact tree.

This script replaces the deterministic L-CONSTITUTION linkage step of the
`/write-constitution` Audit / Resync modes: it parses every `ADR-NNN` token in
Article 4 (Architecture Principles) and Article 7 (Boundaries), plus every
`AE-NNN` token in Article 7, and checks each id resolves to an existing file
under the repo's `dekspec/adrs/` and `dekspec/architecture-elements/` dirs.

The skill keeps the AI-judgment work (deciding whether a broken ref is a typo,
a deleted artifact, or a not-yet-authored one). This script only emits the
mechanical resolve-or-not result.

Output is JSON: {"adr_refs": [...], "ae_refs": [...], "broken": [...]} where
`broken` lists `{"id", "kind", "article"}` for every unresolved reference.
Exit 0 = all refs resolve; exit 1 = at least one broken ref.

Stdlib-only by design: vendored into consumer repos where `dekspec` is not
guaranteed importable.

Runnable:   python validate_linkage.py dekspec/constitution.md
Importable: from validate_linkage import collect_refs, check_linkage
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ADR_RE = re.compile(r"\bADR-(\d+)\b")
_AE_RE = re.compile(r"\bAE-(\d+)\b")

# Article headings are `## Article N: <name>`. We only mine refs from
# Article 4 (ADRs) and Article 7 (ADRs + AEs).
_ARTICLE_RE = re.compile(r"^##\s+Article\s+(\d+)\b.*$", re.MULTILINE)


def _repo_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (or CWD) until a `dekspec/` directory is found."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "dekspec").is_dir():
            return candidate
    return cur


def _article_body(text: str, number: int) -> str:
    """Return the body of `## Article <number>:` up to the next Article heading."""
    bounds: list[tuple[int, int, int]] = []
    for m in _ARTICLE_RE.finditer(text):
        bounds.append((int(m.group(1)), m.start(), m.end()))
    for idx, (num, _start, end) in enumerate(bounds):
        if num != number:
            continue
        next_start = bounds[idx + 1][1] if idx + 1 < len(bounds) else len(text)
        return text[end:next_start]
    return ""


def collect_refs(text: str) -> dict[str, list[dict[str, object]]]:
    """Extract ADR refs (Articles 4, 7) and AE refs (Article 7).

    Returns {"adr_refs": [...], "ae_refs": [...]} where each entry is
    {"id": "ADR-003", "article": 4}. Ids are de-duplicated per article.
    """
    adr_refs: list[dict[str, object]] = []
    ae_refs: list[dict[str, object]] = []

    for article in (4, 7):
        body = _article_body(text, article)
        seen_adr: set[str] = set()
        for m in _ADR_RE.finditer(body):
            ref_id = f"ADR-{int(m.group(1)):03d}"
            if ref_id not in seen_adr:
                seen_adr.add(ref_id)
                adr_refs.append({"id": ref_id, "article": article})

    body7 = _article_body(text, 7)
    seen_ae: set[str] = set()
    for m in _AE_RE.finditer(body7):
        ref_id = f"AE-{int(m.group(1)):03d}"
        if ref_id not in seen_ae:
            seen_ae.add(ref_id)
            ae_refs.append({"id": ref_id, "article": 7})

    return {"adr_refs": adr_refs, "ae_refs": ae_refs}


def _id_resolves(directory: Path, prefix: str, number: int) -> bool:
    """True if a `<prefix>-<NNN>-*.md` (or `<prefix>-NNN*.md`) file exists."""
    if not directory.is_dir():
        return False
    padded = f"{prefix}-{number:03d}"
    unpadded = f"{prefix}-{number}"
    for entry in directory.iterdir():
        name = entry.name
        if name.startswith(padded) or name.startswith(unpadded + "-"):
            return True
        if name in (f"{padded}.md", f"{unpadded}.md"):
            return True
    return False


def check_linkage(
    text: str,
    *,
    adr_dir: Path,
    ae_dir: Path,
) -> dict[str, object]:
    """Collect refs and resolve each against the artifact directories.

    Returns {"adr_refs", "ae_refs", "broken"}; `broken` lists
    {"id", "kind", "article"} for every unresolved reference.
    """
    refs = collect_refs(text)
    broken: list[dict[str, object]] = []

    for ref in refs["adr_refs"]:
        num = int(str(ref["id"]).split("-")[1])
        if not _id_resolves(adr_dir, "ADR", num):
            broken.append({"id": ref["id"], "kind": "adr", "article": ref["article"]})

    for ref in refs["ae_refs"]:
        num = int(str(ref["id"]).split("-")[1])
        if not _id_resolves(ae_dir, "AE", num):
            broken.append({"id": ref["id"], "kind": "ae", "article": ref["article"]})

    return {
        "adr_refs": [r["id"] for r in refs["adr_refs"]],
        "ae_refs": [r["id"] for r in refs["ae_refs"]],
        "broken": broken,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate_linkage.py",
        description="Resolve Constitution ADR / AE cross-references.",
    )
    p.add_argument("path", help="path to the Constitution markdown file")
    p.add_argument(
        "--adr-dir",
        default=None,
        help="ADR directory (default: <repo-root>/dekspec/adrs)",
    )
    p.add_argument(
        "--ae-dir",
        default=None,
        help="AE directory (default: <repo-root>/dekspec/architecture-elements)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    path = Path(args.path)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    root = _repo_root()
    adr_dir = Path(args.adr_dir) if args.adr_dir else root / "dekspec" / "adrs"
    ae_dir = (
        Path(args.ae_dir)
        if args.ae_dir
        else root / "dekspec" / "architecture-elements"
    )

    text = path.read_text(encoding="utf-8")
    result = check_linkage(text, adr_dir=adr_dir, ae_dir=ae_dir)
    print(json.dumps(result, indent=2))
    return 1 if result["broken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
