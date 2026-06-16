#!/usr/bin/env python3
"""Find existing beads whose `external_ref` matches a given IB, by status.

`/write-code-beads` performs this lookup three times in prose:

  - Safety Check  — "are there already open beads for this IB?"
  - Audit Mode    — "which beads belong to this IB to re-audit?"
  - Rebuild Mode  — "which open beads can I delete; are any in_progress/closed?"

All three are deterministic queries: list beads, keep the ones whose
`external_ref` resolves to this IB, group them by status. This module turns
the prose into one lookup. It is a CLI (`find_beads_for_ib.py <ib>`) and
importable (`find_beads_for_ib(ib, repo_root, runner=...)`).

The audit suggested a `.sh` (`br list --json | jq ...`). A stdlib-Python
script that shells `br` is preferred here: it is more testable (the `br`
layer is injectable) and degrades gracefully when `br` is absent — it falls
back to scanning `.beads/issues.jsonl` directly.

Output (JSON on stdout):

    {
      "ib": "IB-019",
      "by_status": {"open": ["bd-1", "bd-2"], "in_progress": [], "closed": ["bd-3"]},
      "total": 3,
      "source": "br"          # or "jsonl" when br was unavailable
    }

Exit codes:
  0 — query ran (even if zero beads matched)
  2 — neither `br` nor `.beads/issues.jsonl` was available

Style mirrors `tooling/dekspec/cli.py`. Stdlib-only — vendored into consumer
repos where the `dekspec` engine is not importable.
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

# A runner: given an argv list + cwd, return (returncode, stdout, stderr).
# Injectable so tests need not depend on a real `br` install or bead state.
Runner = Callable[[list[str], Path], "tuple[int, str, str]"]

# Match an `IB-NNN` or `INT-NNN` token anywhere in an external_ref. Refs may be
# bare (`IB-019`, `INT-133`), pathed (`dekspec/impl-briefs/IB-019-foo.md`,
# `dekspec/intents/INT-133-foo.md`), or carry a `:suffix` slice qualifier
# (`IB-019:phase-2`) — the token match handles all. The `INT-NNN` form supports
# the `--decompose` single-WS-fan-in direct-bead path (Decision #12), where beads
# hang directly off the Intent with no intermediate IB (ds-frua).
_IB_TOKEN_RE = re.compile(r"\b(?:IB|INT)-\d{3,}\b")


class BeadQueryError(Exception):
    """Raised when no bead data source (br or JSONL) is available."""


def _default_runner(argv: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a subprocess with list argv (never shell=True). Returns triple."""
    proc = subprocess.run(
        argv, capture_output=True, text=True, cwd=cwd, check=False
    )
    return proc.returncode, proc.stdout, proc.stderr


def _ib_token(ref: str) -> str | None:
    """Extract the canonical `IB-NNN` or `INT-NNN` token from a ref string."""
    if not ref:
        return None
    match = _IB_TOKEN_RE.search(ref)
    return match.group(0) if match else None


def _normalize_ib(ib: str) -> str:
    """Reduce an IB/Intent argument (path, bare id, or :suffix form) to its `IB-NNN` / `INT-NNN` token."""
    token = _ib_token(ib)
    if token is None:
        raise BeadQueryError(f"could not parse an IB-NNN or INT-NNN id from: {ib!r}")
    return token


def _resolve_lookup(ib: str) -> tuple[str, str]:
    """Resolve an IB/Intent argument to a `(mode, key)` lookup pair.

    - Canonical `IB-NNN` / `INT-NNN` ids (bare, pathed, or `:suffix` form) match
      by **token** — `mode="token"`, `key` = the `IB-NNN`/`INT-NNN` token.
    - Provisional bare-slug IB paths carry no NNN token
      (e.g. `dekspec/provisional/<slug>/IB-provisional-<slug>-ib.md`). They match
      by **literal** — `mode="literal"`, `key` = the filename stem (dir, `.md`,
      and any `#bead-N` / `:slice` qualifier stripped), tested as a substring of
      each bead's `external_ref`. This mirrors the read side of the convention
      `/write-code-beads` uses when it anchors provisional beads' `external_ref` to
      the provisional IB path (ds-nv1i).
    """
    token = _ib_token(ib)
    if token is not None:
        return ("token", token)
    stem = Path(ib).name
    for sep in ("#", ":"):
        stem = stem.split(sep, 1)[0]
    if stem.endswith(".md"):
        stem = stem[:-3]
    stem = stem.strip()
    if not stem:
        raise BeadQueryError(
            f"could not derive an IB-NNN/INT-NNN token or a provisional "
            f"filename-stem lookup key from: {ib!r}"
        )
    return ("literal", stem)


def _query_br(ib_token: str, repo_root: Path, runner: Runner) -> list[dict] | None:
    """List beads via `br list --json`. Returns bead dicts, or None on failure."""
    if not shutil.which("br"):
        return None
    try:
        code, out, _ = runner(["br", "list", "--json"], repo_root)
    except OSError:
        return None
    if code != 0 or not out.strip():
        return None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None
    # `br list --json` may emit a bare list or an object wrapping `issues`.
    if isinstance(payload, dict):
        payload = payload.get("issues") or payload.get("beads") or []
    return payload if isinstance(payload, list) else []


def _query_jsonl(repo_root: Path) -> list[dict] | None:
    """Parse `.beads/issues.jsonl` directly. Returns bead dicts, or None."""
    jsonl_path = repo_root / ".beads" / "issues.jsonl"
    if not jsonl_path.is_file():
        return None
    beads: list[dict] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            bead = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(bead, dict):
            beads.append(bead)
    return beads


def find_beads_for_ib(
    ib: str,
    repo_root: Path,
    runner: Runner | None = None,
) -> dict[str, object]:
    """Return beads matching an IB, grouped by status.

    Tries `br list --json` first; falls back to scanning the JSONL store.
    Raises BeadQueryError when neither source is available.
    """
    run = runner or _default_runner
    repo_root = Path(repo_root)
    mode, key = _resolve_lookup(ib)

    source = "br"
    beads = _query_br(key, repo_root, run)
    if beads is None:
        source = "jsonl"
        beads = _query_jsonl(repo_root)
    if beads is None:
        raise BeadQueryError(
            "no bead data source available — `br` not found and "
            f"{repo_root / '.beads' / 'issues.jsonl'} does not exist"
        )

    by_status: dict[str, list[str]] = {}
    for bead in beads:
        if not isinstance(bead, dict):
            continue
        ref = str(bead.get("external_ref") or bead.get("externalRef") or "")
        if mode == "token":
            if _ib_token(ref) != key:
                continue
        else:  # literal — provisional bare-slug match by filename stem
            if key not in ref:
                continue
        status = str(bead.get("status") or "unknown")
        bead_id = str(bead.get("id") or bead.get("bead_id") or "?")
        by_status.setdefault(status, []).append(bead_id)

    for ids in by_status.values():
        ids.sort()
    total = sum(len(ids) for ids in by_status.values())
    return {
        "ib": key,
        "by_status": by_status,
        "total": total,
        "source": source,
    }


def cmd_find(args: argparse.Namespace) -> int:
    """CLI dispatcher: print the grouped-by-status bead JSON for one IB."""
    try:
        result = find_beads_for_ib(args.ib, Path(args.repo_root))
    except BeadQueryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="find_beads_for_ib.py",
        description="Find beads whose external_ref matches an IB, grouped by status.",
    )
    parser.add_argument(
        "ib",
        help="IB or Intent path, bare `IB-NNN` / `INT-NNN` id, or `IB-NNN:suffix` form",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="repository root (default: current directory)",
    )
    parser.set_defaults(func=cmd_find)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
