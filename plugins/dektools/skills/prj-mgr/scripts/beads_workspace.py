#!/usr/bin/env python3
"""Resolve the `br` bead workspaces (ADR-052) with zero hard dependencies.

Three bead kinds, three `br` workspaces, distinguished by ID prefix:

    .beads/          cb-*    code beads      -- executor input, bare `br ready`
    .beads-issues/   iss-*   product issues  -- the repo's own tracking
    .beads-dekspec/  ds-*    DekSpec work    -- governance items

Per ADR-052 the location is *discoverable*, never hardcoded. Three layers,
each usable on its own, tried in order:

1. **Convention** -- the sibling directories above, relative to the repo root.
   Needs nothing installed but `br`. This is the layer that lets a tool with
   no DekSpec present find the tracker.
2. **Declaration** -- ``.dekspec/config.yaml`` may name workspace locations
   under ``issue_tracker``, for repos that put them elsewhere.
3. **Resolution verb** -- ``dekspec beads workspaces --json``, when the engine
   is on PATH. The ergonomic path; never required.

This module imports only the standard library, so it works in a repo with no
DekSpec engine, no DekSpec plugin, and no marketplace entry. That is the
``dekspec-enhanced`` dependency tier of ADR-047, and it is enforced by test.

Pre-migration compatibility: until a repo has been split (ds-x74v), the
issue and DekSpec kinds still live in the single root workspace. Resolution
falls back to it rather than reporting "no tracker", so this tool works
before, during, and after the migration.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# kind -> (directory CONTAINING the `.beads/` dir, ID prefix).
# The code workspace is the repo root itself, so `br` auto-discovers it and
# bare `br ready` needs no flag (ADR-052 §2).
CONVENTION: dict[str, tuple[str, str]] = {
    "code": (".", "cb"),
    "issue": (".beads-issues", "iss"),
    "dekspec": (".beads-dekspec", "ds"),
}

KINDS = tuple(CONVENTION)

#: Kinds the project manager may touch. Code beads are DELIBERATELY excluded:
#: they are the coding agent's queue, not project-managed work. `prj-mgr` must
#: never read, render, or sync them -- see `pm_workspaces()`.
PM_KINDS: tuple[str, ...] = ("issue", "dekspec")

#: The one kind `prj-mgr` must never operate on.
FORBIDDEN_FOR_PM = "code"


@dataclass(frozen=True)
class Workspace:
    """A resolved `br` workspace."""

    kind: str
    prefix: str
    directory: Path
    #: How this workspace was found -- "convention", "declaration", "verb",
    #: or "fallback" (pre-migration single-workspace repo).
    source: str

    @property
    def db(self) -> Path:
        """Path to the workspace's `br` database."""
        return self.directory / ".beads" / "beads.db"

    @property
    def jsonl(self) -> Path:
        """Path to the workspace's durable JSONL export."""
        return self.directory / ".beads" / "issues.jsonl"

    @property
    def exists(self) -> bool:
        """True when the workspace is present in ANY usable form.

        The `.db` is a local cache that `br` rebuilds and that `br`'s own
        gitignore excludes, so a fresh clone has only `issues.jsonl` -- the
        durable, committed record. Keying existence on the database alone
        makes every freshly-cloned repo look tracker-less.
        """
        return self.db.is_file() or self.jsonl.is_file()

    def br_args(self) -> list[str]:
        """`br` arguments selecting this workspace.

        Empty for the repo-default workspace so that bare `br ready` keeps
        working untouched -- the property ADR-052 §2 exists to protect.
        """
        if (self.directory / ".beads").is_dir() and self.kind == "code":
            return []
        return ["--db", str(self.db)]


def _present(directory: Path) -> bool:
    """Is a `br` workspace present at `directory`?

    Accepts either the database OR the JSONL. `br`'s gitignore excludes the
    `.db`, so on a fresh clone the JSONL is the only evidence a workspace
    exists -- and it is the durable record either way.
    """
    beads = directory / ".beads"
    return (beads / "beads.db").is_file() or (beads / "issues.jsonl").is_file()


def repo_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (or CWD) to the git repo root.

    Falls back to the starting directory when there is no `.git`, so the
    tool still functions outside a repository.
    """
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            return candidate
    return cur


def _from_declaration(root: Path, kind: str) -> Path | None:
    """Layer 2 -- an explicit location in `.dekspec/config.yaml`.

    Parsed with a deliberately small hand-rolled reader rather than PyYAML:
    this module must stay standard-library-only, and the shape we need is a
    flat `issue_tracker:` mapping. A repo doing something more elaborate can
    use the resolution verb instead.
    """
    config = root / ".dekspec" / "config.yaml"
    if not config.is_file():
        return None
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None

    in_tracker = False
    want = f"{kind}_workspace"
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[:1].isspace():
            in_tracker = raw.split(":", 1)[0].strip() == "issue_tracker"
            continue
        if not in_tracker:
            continue
        key, _, value = raw.strip().partition(":")
        if key.strip() == want and value.strip():
            return root / value.strip().strip("\"'")
    return None


def _from_verb(root: Path, kind: str) -> Path | None:
    """Layer 3 -- ask the DekSpec engine, when it happens to be installed.

    Never required. Any failure -- engine absent, verb not yet shipped,
    malformed output -- falls through to the layers above.
    """
    if shutil.which("dekspec") is None:
        return None
    try:
        proc = subprocess.run(
            ["dekspec", "beads", "workspaces", "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    entry = (payload or {}).get(kind) if isinstance(payload, dict) else None
    if isinstance(entry, dict) and entry.get("directory"):
        return root / str(entry["directory"])
    return None


def resolve(kind: str, root: Path | None = None) -> Workspace:
    """Resolve one workspace by kind. Never raises for a missing workspace.

    Returns a `Workspace` whose `.exists` is False when nothing is present;
    callers decide whether that is an error or an empty board.
    """
    if kind not in CONVENTION:
        raise ValueError(f"unknown bead kind {kind!r}; expected one of {KINDS}")
    root = root or repo_root()
    conv_dir, prefix = CONVENTION[kind]

    declared = _from_declaration(root, kind)
    if declared is not None and _present(declared):
        return Workspace(kind, prefix, declared, "declaration")

    resolved = _from_verb(root, kind)
    if resolved is not None and _present(resolved):
        return Workspace(kind, prefix, resolved, "verb")

    conventional = (root / conv_dir).resolve()
    if _present(conventional):
        return Workspace(kind, prefix, conventional, "convention")

    # Pre-migration: the split has not happened, so every kind still lives in
    # the single root workspace. Report it rather than claiming no tracker.
    if kind != "code" and _present(root):
        return Workspace(kind, prefix, root, "fallback")

    return Workspace(kind, prefix, conventional, "convention")


def resolve_all(root: Path | None = None) -> dict[str, Workspace]:
    """Resolve all three kinds at once."""
    root = root or repo_root()
    return {kind: resolve(kind, root) for kind in KINDS}


def pm_workspaces(root: Path | None = None) -> list[Workspace]:
    """Workspaces the project manager operates on: issue + dekspec, never code.

    `prj-mgr` manages BOTH generic product issues and DekSpec governance work
    -- they are different backlogs but both are project-managed. Code beads are
    excluded by construction: they are executor input, pulled by the coding
    agent via bare `br ready`, and are not project-managed work at all.

    Returns only workspaces that exist, so a repo with just one of the two
    still renders boards.
    """
    root = root or repo_root()
    out = [resolve(kind, root) for kind in PM_KINDS]
    return [ws for ws in out if ws.exists]


def assert_not_code(ws: Workspace) -> None:
    """Guard: refuse a code workspace anywhere in the project-manager path."""
    if ws.kind == FORBIDDEN_FOR_PM:
        raise ValueError(
            "prj-mgr must never operate on the code-bead workspace: code beads "
            "are the coding agent's queue (bare `br ready`), not project-managed "
            "work. Use the issue or dekspec workspace."
        )


def main(argv: list[str] | None = None) -> int:
    """Print the resolved workspaces as JSON -- the discoverability surface.

    Any tool or agent can run this to learn what trackers exist, where they
    live, and how they were found, without importing anything.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve the br bead workspaces (ADR-052)."
    )
    parser.add_argument("--kind", choices=KINDS, help="resolve a single kind")
    parser.add_argument("--at", type=Path, default=None, help="repo root")
    args = parser.parse_args(argv)

    root = repo_root(args.at)
    kinds = [args.kind] if args.kind else list(KINDS)
    payload = {}
    for kind in kinds:
        ws = resolve(kind, root)
        payload[kind] = {
            "prefix": ws.prefix,
            "directory": str(ws.directory.relative_to(root))
            if ws.directory.is_relative_to(root)
            else str(ws.directory),
            "db": str(ws.db),
            "exists": ws.exists,
            "source": ws.source,
            "br_args": ws.br_args(),
        }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
