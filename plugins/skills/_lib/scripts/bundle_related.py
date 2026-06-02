"""Deterministic related-artifact bundler for DekSpec authoring skills.

This script replaces prose instructions in the authoring skills
(`write-adr`, `write-ws`, `write-ae`, `write-constitution`) that ask the
model to "grep the architecture-elements tree for AEs whose linkage
sections reference the decision's domain" and similar. The linkage scan
is deterministic — it belongs in a script, not in skill prose.

Two query modes:

  bundle_related.py --for <artifact-path> [--include ae,adr,ic,ib]
      Parse the given artifact's typed linkage / reference sections and
      return the paths of the artifacts it references. With --backlinks,
      also return artifacts elsewhere in the tree that reference IT.

  bundle_related.py --keywords "auth,middleware,session" [--include ae,adr]
      Grep the dekspec/ tree for artifacts whose linkage-relevant
      sections mention any of those keywords; return the paths.

Output: JSON {"ae": [...paths], "adr": [...paths], "ic": [...paths],
"ib": [...paths]} — sorted, deduplicated, repo-relative where possible.

Standalone + stdlib-only by design: vendored skills run inside consumer
repos where the `dekspec` Python engine is not necessarily importable
from the skill's path. The structured-grep approach mirrors the existing
`_lib/scripts/artifact_ops.py` precedent (which also re-implements its
own `find_refs` rather than importing `SpecGraph`). The known section
names + reference patterns below are the deterministic contract.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #

# Artifact-kind -> (subdirectory under dekspec/, filename-id prefix).
KIND_DIRS: dict[str, tuple[str, str]] = {
    "ae": ("architecture-elements", "AE-"),
    "adr": ("adrs", "ADR-"),
    "ic": ("interface-contracts", "IC-"),
    "ib": ("impl-briefs", "IB-"),
}

ALL_KINDS = ("ae", "adr", "ic", "ib")

# Reference-id patterns, by kind. A bare AE-001 / ADR-12 / IC-4 / IB-040.
_ID_RE: dict[str, re.Pattern[str]] = {
    "ae": re.compile(r"\bAE-\d{1,4}\b"),
    "adr": re.compile(r"\bADR-\d{1,4}\b"),
    "ic": re.compile(r"\bIC-\d{1,4}\b"),
    "ib": re.compile(r"\bIB-\d{1,4}\b"),
}

# Section headings whose bodies carry cross-artifact linkage. Used both
# when parsing the --for artifact and when keyword-scanning the tree.
# Lower-cased substrings matched against `## <Heading>` lines.
_LINKAGE_HEADINGS = (
    "linked artifacts",
    "related architecture elements",
    "related adrs",
    "governing adrs",
    "components affected",
    "components-affected",
    "constraints",
    "linkage",
    "relationships and dependencies",
)

# IB linkage lives in bold inline header lines, not `##` sections:
#   **Spec:** `...`   **Source AEs:** AE-004, AE-007
_IB_HEADER_RE = re.compile(
    r"^\*\*(Spec|Intent|Source AEs|Depends on)\:\*\*", re.IGNORECASE
)


# --------------------------------------------------------------------------- #
# Repo discovery
# --------------------------------------------------------------------------- #


def _repo_root(start: Path) -> Path:
    """Walk upward from `start` until a directory containing `dekspec/`.

    Falls back to the start directory if no such ancestor exists, so the
    script degrades to a no-op rather than crashing in an odd layout.
    """
    cur = start.resolve()
    for cand in (cur, *cur.parents):
        if (cand / "dekspec").is_dir():
            return cand
    return cur


def _dekspec_dir(repo_root: Path) -> Path:
    return repo_root / "dekspec"


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return str(path.resolve())


# --------------------------------------------------------------------------- #
# Section extraction
# --------------------------------------------------------------------------- #


def _linkage_text(body: str) -> str:
    """Return the concatenated text of every linkage-relevant section.

    A section runs from a `## <Heading>` line (matching one of
    `_LINKAGE_HEADINGS`) to the next `## ` heading. IB-style bold inline
    header lines are also harvested. Falls back to the whole body if no
    structured section is found, so an oddly formatted artifact still
    yields its references rather than silently returning nothing.
    """
    lines = body.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            in_section = any(h in heading for h in _LINKAGE_HEADINGS)
            continue
        if stripped.startswith("# "):
            in_section = False
            continue
        if in_section:
            out.append(line)
        elif _IB_HEADER_RE.match(stripped):
            out.append(line)
    return "\n".join(out) if out else body


def _self_id(body: str, path: Path) -> str | None:
    """Best-effort artifact id of the artifact at `path`.

    Prefers a leading `# AE-001: ...` / `# ADR-3: ...` title line; falls
    back to the filename prefix. Used to exclude self-references.
    """
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            for pat in _ID_RE.values():
                m = pat.search(stripped)
                if m:
                    return m.group(0)
            break
    stem = path.stem
    for pat in _ID_RE.values():
        m = pat.match(stem)
        if m:
            return m.group(0)
    return None


# --------------------------------------------------------------------------- #
# Id -> path resolution
# --------------------------------------------------------------------------- #


def _index_by_id(dekspec_dir: Path) -> dict[str, Path]:
    """Map every artifact id (AE-001, ADR-12, ...) to its file path."""
    index: dict[str, Path] = {}
    for kind, (subdir, prefix) in KIND_DIRS.items():
        kind_dir = dekspec_dir / subdir
        if not kind_dir.is_dir():
            continue
        for path in sorted(kind_dir.rglob(f"{prefix}*.md")):
            stem = path.stem
            m = _ID_RE[kind].match(stem)
            if m:
                index.setdefault(m.group(0), path)
    return index


def _kind_of(artifact_id: str) -> str | None:
    for kind, pat in _ID_RE.items():
        if pat.fullmatch(artifact_id):
            return kind
    return None


# --------------------------------------------------------------------------- #
# Query modes
# --------------------------------------------------------------------------- #


def _empty_result() -> dict[str, list[str]]:
    return {k: [] for k in ALL_KINDS}


def refs_for_artifact(
    artifact_path: Path,
    repo_root: Path,
    include: tuple[str, ...],
    backlinks: bool,
) -> dict[str, list[str]]:
    """Resolve the artifacts referenced by (and optionally referencing)
    the artifact at `artifact_path`.

    Returns a {kind: [repo-relative paths]} dict, sorted + deduplicated.
    Self-references and ids that resolve to no file on disk are dropped.
    """
    dekspec_dir = _dekspec_dir(repo_root)
    id_index = _index_by_id(dekspec_dir)
    body = artifact_path.read_text(encoding="utf-8")
    self_id = _self_id(body, artifact_path)

    found_ids: set[str] = set()
    linkage = _linkage_text(body)
    for kind in include:
        for m in _ID_RE[kind].finditer(linkage):
            found_ids.add(m.group(0))

    if backlinks and self_id is not None:
        back_pat = re.compile(rf"\b{re.escape(self_id)}\b")
        for kind in include:
            subdir, prefix = KIND_DIRS[kind]
            kind_dir = dekspec_dir / subdir
            if not kind_dir.is_dir():
                continue
            for path in kind_dir.rglob(f"{prefix}*.md"):
                if path.resolve() == artifact_path.resolve():
                    continue
                other_body = path.read_text(encoding="utf-8")
                if back_pat.search(_linkage_text(other_body)):
                    other_id = _self_id(other_body, path)
                    if other_id:
                        found_ids.add(other_id)

    result = _empty_result()
    for artifact_id in found_ids:
        if artifact_id == self_id:
            continue
        kind = _kind_of(artifact_id)
        if kind is None or kind not in include:
            continue
        path = id_index.get(artifact_id)
        if path is not None:
            result[kind].append(_rel(path, repo_root))
    return {k: sorted(set(v)) for k, v in result.items()}


def refs_for_keywords(
    keywords: tuple[str, ...],
    repo_root: Path,
    include: tuple[str, ...],
) -> dict[str, list[str]]:
    """Grep the dekspec/ tree for artifacts whose linkage-relevant
    sections mention any of `keywords` (case-insensitive substring).

    Returns a {kind: [repo-relative paths]} dict, sorted + deduplicated.
    """
    dekspec_dir = _dekspec_dir(repo_root)
    lowered = tuple(k.lower() for k in keywords if k.strip())
    result = _empty_result()
    if not lowered:
        return result

    for kind in include:
        subdir, prefix = KIND_DIRS[kind]
        kind_dir = dekspec_dir / subdir
        if not kind_dir.is_dir():
            continue
        for path in sorted(kind_dir.rglob(f"{prefix}*.md")):
            linkage = _linkage_text(path.read_text(encoding="utf-8")).lower()
            if any(kw in linkage for kw in lowered):
                result[kind].append(_rel(path, repo_root))
    return {k: sorted(set(v)) for k, v in result.items()}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _parse_include(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ALL_KINDS
    kinds = tuple(k.strip().lower() for k in raw.split(",") if k.strip())
    bad = [k for k in kinds if k not in ALL_KINDS]
    if bad:
        raise SystemExit(
            f"bundle_related: unknown --include kind(s): {', '.join(bad)} "
            f"(valid: {', '.join(ALL_KINDS)})"
        )
    return kinds or ALL_KINDS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bundle_related.py",
        description=(
            "Return the related DekSpec artifact paths an orchestrator "
            "should bundle for a fan-out subagent."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--for",
        dest="artifact",
        metavar="ARTIFACT_PATH",
        help="parse this artifact's linkage sections; return what it references",
    )
    group.add_argument(
        "--keywords",
        metavar="KW1,KW2,...",
        help="grep the dekspec/ tree for artifacts mentioning these keywords",
    )
    parser.add_argument(
        "--include",
        metavar="KINDS",
        help="comma-separated subset of ae,adr,ic,ib (default: all)",
    )
    parser.add_argument(
        "--backlinks",
        action="store_true",
        help="(--for only) also return artifacts that reference the target",
    )
    parser.add_argument(
        "--at",
        metavar="REPO_PATH",
        help="repo root to scan (default: discovered from artifact / cwd)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    include = _parse_include(args.include)

    if args.artifact:
        artifact_path = Path(args.artifact)
        if not artifact_path.is_file():
            raise SystemExit(f"bundle_related: artifact not found: {args.artifact}")
        repo_root = (
            _repo_root(Path(args.at)) if args.at else _repo_root(artifact_path.parent)
        )
        result = refs_for_artifact(
            artifact_path, repo_root, include, backlinks=args.backlinks
        )
    else:
        repo_root = _repo_root(Path(args.at) if args.at else Path.cwd())
        keywords = tuple(k.strip() for k in args.keywords.split(",") if k.strip())
        result = refs_for_keywords(keywords, repo_root, include)

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
