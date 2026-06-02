#!/usr/bin/env python3
"""Resolve the IB / WS / Intent / files-under-test chain for a bead.

Three DekSpec skills (`write-tests`, `write-evals`, `exec-coding-session`) ask
the model in prose to perform a deterministic multi-hop walk:

    bead ID
      -> the bead's `external_ref` names a parent Implementation Brief (IB)
      -> the IB's `**Spec:**` field names the parent Working Spec (WS)
      -> the IB's `**Intent:**` field names the parent Intent
      -> the IB's `## Files to Modify` table lists the files under test

This module turns that prose walk into a single deterministic lookup. It is
both a CLI (`resolve_bead_context.py <bead-id>`) and importable
(`resolve_bead_context(bead_id, repo_root)`).

Style mirrors `tooling/dekspec/cli.py`: argparse, `cmd_*` dispatcher,
`int` return codes, `main(argv)` entry point.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

# A bead-lookup function: given a bead ID + repo root, return the bead's typed
# dict (must include at least `id`; `external_ref` is optional). Injectable so
# tests need not depend on `br` state.
BeadLookup = Callable[[str, Path], "dict[str, object] | None"]

# `external_ref` may carry a `:suffix` qualifier, e.g. `IB-037:phase-2` or
# `dekspec/impl-briefs/IB-037-foo.md:phase-2`. The suffix scopes the bead to a
# slice of the IB; it is not part of the IB identity, so it is stripped.
_IB_TOKEN_RE = re.compile(r"\bIB-\d{3,}\b")
_INTENT_TOKEN_RE = re.compile(r"\bINT-\d{3,}\b")

# IB field lines, e.g. `**Spec:** \`dekspec/working-specs/WS-012-foo.md\``.
_SPEC_FIELD_RE = re.compile(r"^\*\*Spec:\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
_INTENT_FIELD_RE = re.compile(r"^\*\*Intent:\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)

# A `## Files to Modify` markdown table row: `| \`path/to/file.py\` | change |`.
# The first cell holds the file path, optionally backtick-wrapped.
_FILES_TABLE_ROW_RE = re.compile(r"^\|\s*`?([^`|]+?)`?\s*\|", re.MULTILINE)


class BeadResolutionError(Exception):
    """Raised when a bead cannot be located at all (a hard failure)."""


def _strip_suffix(external_ref: str) -> str:
    """Drop a trailing `:suffix` qualifier from an external_ref.

    `IB-037:phase-2` -> `IB-037`; `path/IB-037-foo.md:slice` -> `path/IB-037-foo.md`.
    A bare `IB-037` (no colon) is returned unchanged. Windows-style drive
    letters are not a concern — external_refs are POSIX repo-relative paths.
    """
    return external_ref.split(":", 1)[0].strip()


def _br_bead_lookup(bead_id: str, repo_root: Path) -> dict[str, object] | None:
    """Look up a bead via `br show <id> --format json`, JSONL as fallback.

    Returns the bead's typed dict, or None if not found. Raises
    BeadResolutionError only on a tooling failure (not a missing bead).
    """
    if shutil.which("br"):
        try:
            proc = subprocess.run(
                ["br", "show", bead_id, "--format", "json"],
                capture_output=True,
                text=True,
                cwd=repo_root,
                check=False,
            )
        except OSError as exc:  # pragma: no cover — br present but unrunnable
            raise BeadResolutionError(f"failed to invoke `br`: {exc}") from exc
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                payload = None
            # `br show` emits a list of beads; take the first matching id.
            if isinstance(payload, list):
                for bead in payload:
                    if isinstance(bead, dict) and bead.get("id") == bead_id:
                        return bead
                if payload and isinstance(payload[0], dict):
                    return payload[0]
            elif isinstance(payload, dict):
                return payload
        # br ran but found nothing — fall through to the JSONL scan, which is
        # authoritative for closed/compacted beads br may not surface.
    return _jsonl_bead_lookup(bead_id, repo_root)


def _jsonl_bead_lookup(bead_id: str, repo_root: Path) -> dict[str, object] | None:
    """Parse `.beads/issues.jsonl` directly for a bead row.

    Used when `br` is unavailable or returns nothing.
    """
    jsonl_path = repo_root / ".beads" / "issues.jsonl"
    if not jsonl_path.is_file():
        return None
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            bead = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(bead, dict) and bead.get("id") == bead_id:
            return bead
    return None


def _is_ib_file(path: Path) -> bool:
    """True if `path` looks like an Implementation Brief, not a WS / IC / etc.

    An IB lives under `dekspec/impl-briefs/` *or* its filename carries an
    `IB-NNN` token. Either signal is sufficient.
    """
    if _IB_TOKEN_RE.search(path.name):
        return True
    return "impl-briefs" in path.parts


def _resolve_ib_path(external_ref: str, repo_root: Path) -> Path | None:
    """Resolve an external_ref to a concrete IB file path.

    The ref may be a repo-relative path (`dekspec/impl-briefs/IB-012-foo.md`)
    or a bare token (`IB-012`). Bare tokens are globbed against the impl-briefs
    tree (including the `active/` and `queued/` subdirectories some repos use).
    Returns None if no file is found.
    """
    ref = _strip_suffix(external_ref)
    if not ref:
        return None

    # Path-shaped ref: trust it relative to the repo root, but only if it
    # actually points at an Implementation Brief. Some beads carry an
    # external_ref to a WS or IC (e.g. `dekspec/interface-contracts/IC-004-*.md`) —
    # those are not IBs and must not be returned as `ib_path`.
    if "/" in ref or ref.endswith(".md"):
        candidate = repo_root / ref
        if candidate.is_file() and _is_ib_file(candidate):
            return candidate
        # The ref may still embed an IB token (e.g. a stale path) — fall
        # through to token globbing rather than giving up.

    token_match = _IB_TOKEN_RE.search(ref)
    if not token_match:
        return None
    token = token_match.group(0)
    briefs_root = repo_root / "dekspec" / "impl-briefs"
    if not briefs_root.is_dir():
        return None
    matches = sorted(briefs_root.glob(f"**/{token}-*.md"))
    return matches[0] if matches else None


def _parse_ib(ib_path: Path) -> dict[str, object]:
    """Extract ws_path, intent_id, and files-under-test from an IB file.

    Returns a dict; any hop that cannot be resolved is left as None / [] with
    an explanatory note rather than raising.
    """
    text = ib_path.read_text(encoding="utf-8")
    notes: list[str] = []

    # WS hop: the IB's `**Spec:**` field names the parent Working Spec.
    ws_path: str | None = None
    spec_match = _SPEC_FIELD_RE.search(text)
    if spec_match:
        ws_path = spec_match.group(1).strip()
    else:
        notes.append(f"{ib_path.name} has no `**Spec:**` field — ws_path unresolved")

    # Intent hop: the IB co-locates a `**Intent:**` field. (Working Specs in
    # this corpus carry no structured Intent field, so the IB is the
    # authoritative source for intent_id.)
    intent_id: str | None = None
    intent_match = _INTENT_FIELD_RE.search(text)
    if intent_match:
        intent_value = intent_match.group(1).strip()
        token_match = _INTENT_TOKEN_RE.search(intent_value)
        intent_id = token_match.group(0) if token_match else intent_value or None
    else:
        notes.append(f"{ib_path.name} has no `**Intent:**` field — intent_id unresolved")

    # Files under test: first column of the `## Files to Modify` table.
    files: list[str] = []
    files_section = _slice_files_section(text)
    if files_section is not None:
        for row in _FILES_TABLE_ROW_RE.finditer(files_section):
            cell = row.group(1).strip()
            # Skip the markdown header/divider rows.
            if not cell or cell.lower() == "file" or set(cell) <= {"-", " "}:
                continue
            files.append(cell)
    else:
        notes.append(f"{ib_path.name} has no `## Files to Modify` section — files empty")

    return {"ws_path": ws_path, "intent_id": intent_id, "files": files, "notes": notes}


def _slice_files_section(text: str) -> str | None:
    """Return the text of the `## Files to Modify` section, or None."""
    match = re.search(r"^##\s+Files to Modify\s*$", text, re.MULTILINE)
    if not match:
        return None
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def resolve_bead_context(
    bead_id: str,
    repo_root: Path | None = None,
    bead_lookup: BeadLookup = _br_bead_lookup,
) -> dict[str, object]:
    """Resolve the full bead -> IB -> WS -> Intent -> files chain.

    Returns a dict with keys: bead_id, bead_path, ib_path, ws_path, intent_id,
    files, notes. Broken hops yield null / empty values plus a `notes` entry;
    only a missing bead raises (BeadResolutionError).

    `bead_lookup` is injectable so tests can supply a synthetic bead store.
    """
    repo_root = (repo_root or Path.cwd()).resolve()
    notes: list[str] = []

    bead = bead_lookup(bead_id, repo_root)
    if bead is None:
        raise BeadResolutionError(
            f"bead {bead_id!r} not found (checked `br` and .beads/issues.jsonl)"
        )

    result: dict[str, object] = {
        "bead_id": bead_id,
        # Beads are tracker rows, not files; bead_path is the JSONL store the
        # row was read from, kept for traceability.
        "bead_path": str(repo_root / ".beads" / "issues.jsonl"),
        "ib_path": None,
        "ws_path": None,
        "intent_id": None,
        "files": [],
        "notes": notes,
    }

    external_ref = bead.get("external_ref")
    if not external_ref or not isinstance(external_ref, str):
        notes.append(f"bead {bead_id} has no external_ref — IB / WS / Intent unresolved")
        return result

    ib_path = _resolve_ib_path(external_ref, repo_root)
    if ib_path is None:
        notes.append(
            f"external_ref {external_ref!r} did not resolve to an IB file "
            "— WS / Intent / files unresolved"
        )
        return result
    result["ib_path"] = str(ib_path)

    ib_data = _parse_ib(ib_path)
    result["ws_path"] = ib_data["ws_path"]
    result["intent_id"] = ib_data["intent_id"]
    result["files"] = ib_data["files"]
    notes.extend(ib_data["notes"])  # type: ignore[arg-type]
    return result


def cmd_resolve(args: argparse.Namespace) -> int:
    """CLI dispatcher: resolve and print the bead context as JSON."""
    try:
        result = resolve_bead_context(args.bead_id, repo_root=Path(args.at))
    except BeadResolutionError as exc:
        print(f"resolve_bead_context: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="resolve_bead_context.py",
        description=(
            "Resolve a bead's IB / WS / Intent / files-under-test chain "
            "and print it as JSON."
        ),
    )
    parser.add_argument("bead_id", help="The bead ID to resolve (e.g. ds-jzg).")
    parser.add_argument(
        "--at",
        default=".",
        metavar="REPO_PATH",
        help="Repository root to resolve against (default: current directory).",
    )
    parser.set_defaults(func=cmd_resolve)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess in tests
    sys.exit(main())
