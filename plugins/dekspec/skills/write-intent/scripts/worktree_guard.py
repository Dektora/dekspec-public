#!/usr/bin/env python3
"""Spec-phase worktree-collision guard (ds-2tky).

The Intent spec-phase lifecycle (Creation / provisional / `--analyze` /
`--accept` / `--decompose`) historically isolated work with a git BRANCH
(`git checkout -b int/INT-NNN-<slug>`) on the *shared* working tree. When a
second Intent lifecycle (spec or coding) runs in the same checkout, the two
flip HEAD against each other: commits from one Intent leak into the other's
ancestry, polluting its diff and tripping `--testpass` diff-confinement. The
coding phase already isolates per-bead work in git worktrees
(`exec-coding-session`); the spec phase did not.

This guard runs *before* `git checkout -b` at Intent-branch creation. It
REFUSES (exit 2) to create a new Intent branch on top of another Intent's
branch, and points the operator at an isolated `git worktree add` instead.
On a clean base it allows the checkout (exit 0), emitting an advisory when
other Intent branches are already in flight.

Exit codes:
  0 — safe to `git checkout -b` on this tree (on a non-Intent base).
  2 — COLLISION: currently on an `int/INT-*` branch; refuse + print the
      worktree command to run instead.
  3 — not a git repo / git unavailable (advisory; caller may proceed).

Usage:
  python worktree_guard.py --new-branch int/INT-049-foo [--repo-root .]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_INTENT_BRANCH_PREFIX = "int/"


def _git(args: list[str], repo_root: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=False,
        )
    except OSError:
        return 1, ""
    return proc.returncode, proc.stdout.strip()


def _current_branch(repo_root: Path) -> str | None:
    code, out = _git(["branch", "--show-current"], repo_root)
    if code != 0:
        return None
    return out or None  # empty == detached HEAD


def _intent_branches(repo_root: Path) -> list[str]:
    code, out = _git(["branch", "--list", f"{_INTENT_BRANCH_PREFIX}*"], repo_root)
    if code != 0 or not out:
        return []
    return [ln.lstrip("* ").strip() for ln in out.splitlines() if ln.strip()]


def _worktree_cmd(new_branch: str, repo_root: Path) -> str:
    slug = new_branch.split("/", 1)[-1]
    sibling = f"../{repo_root.resolve().name}-{slug}"
    return f"git worktree add {sibling} -b {new_branch} main"


def check(new_branch: str, repo_root: Path) -> int:
    code, _ = _git(["rev-parse", "--is-inside-work-tree"], repo_root)
    if code != 0:
        print("worktree-guard: not a git repository (skipping check).", file=sys.stderr)
        return 3

    current = _current_branch(repo_root)
    if current and current.startswith(_INTENT_BRANCH_PREFIX) and current != new_branch:
        print(
            f"worktree-guard: REFUSED — HEAD is on Intent branch '{current}'. "
            f"Creating '{new_branch}' with `git checkout -b` here would branch "
            f"one Intent off another's HEAD and let their commits collide "
            f"(ds-2tky). Create an isolated worktree from a clean base instead:\n"
            f"  {_worktree_cmd(new_branch, repo_root)}\n"
            f"then run the Intent lifecycle inside that worktree.",
            file=sys.stderr,
        )
        return 2

    others = [b for b in _intent_branches(repo_root) if b != new_branch]
    if others:
        print(
            "worktree-guard: advisory — other Intent branches are in flight "
            f"({', '.join(sorted(others))}). `git checkout -b {new_branch}` on "
            "this shared tree is allowed (HEAD is on a clean base), but if a "
            "coding or spec session for any of those is active in THIS "
            "checkout, prefer an isolated worktree:\n"
            f"  {_worktree_cmd(new_branch, repo_root)}",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Spec-phase worktree-collision guard (ds-2tky).")
    ap.add_argument("--new-branch", required=True, help="The Intent branch about to be created (e.g. int/INT-049-foo).")
    ap.add_argument("--repo-root", default=".", help="Repository root (default: cwd).")
    args = ap.parse_args(argv)
    return check(args.new_branch, Path(args.repo_root))


if __name__ == "__main__":
    raise SystemExit(main())
