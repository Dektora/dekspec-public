#!/usr/bin/env python3
"""Create the `br` bead workspaces for a repo, in one of two modes.

Answers "I have neither prj-mgr nor DekSpec -- how do I set up `br`?" Needs only
`br` on PATH and the Python standard library. Copy it anywhere; it imports
nothing from this repo.

    --mode independent  (default)  one workspace, issue tracking only
    --mode dekspec                 three workspaces, DekSpec-integrated

INDEPENDENT MODE (the default) -- one kind, one store:

    .beads/          iss-*   issues          -- bare `br`, no --db, no DekSpec

Most repos want this. The repo tracks issues; there is no coding-agent queue to
keep separate and no governance layer. Every `br` command works bare, which
removes the whole "never run a bare mutating br command" discipline the
three-workspace layout requires. Fewer moving parts is the point.

DEKSPEC MODE -- three kinds, three stores (ADR-052):

    .beads/          cb-*    code beads      -- executor input, bare `br ready`
    .beads-issues/   iss-*   product issues  -- the repo's own tracking
    .beads-dekspec/  ds-*    DekSpec work    -- governance items

The root workspace holds *code* beads because `br` auto-discovers it, so bare
`br ready` returns the next ready coding bead with no flag and no remembered
discipline (ADR-052 s2). The other kinds are reached with `--db`.

Take dekspec mode when DekSpec is in play, or when a coding agent will run bare
`br ready` in this repo and must get coding tasks rather than issues.

The equivalent by hand, if you would rather not run a script -- this is the
whole thing, and each layout is nothing more than this convention:

    # independent mode (default)
    br init --prefix iss && br config set min_hash_length 5

    # dekspec mode
    br init --prefix cb && br config set min_hash_length 5
    mkdir -p .beads-issues  && (cd .beads-issues  && br init --prefix iss && br config set min_hash_length 5)
    mkdir -p .beads-dekspec && (cd .beads-dekspec && br init --prefix ds  && br config set min_hash_length 5)

CHOOSING, AND CHANGING YOUR MIND

Independent mode is not a subset of dekspec mode -- the two disagree about what
lives at the root. Independent puts *issues* there; dekspec puts *code* there
and expects bare `br ready` to be the coding queue. Switching later is a real
migration (export JSONL, re-init the root, import into the sibling), not a
second run of this script.

So conflict handling depends on whether you *asked* for a mode:

  * mode DEFAULTED, root already the other layout -> report what is there, exit
    0. Running bare `--bootstrap` in an established dekspec repo is a no-op,
    not an error.
  * mode EXPLICIT (--mode / --dekspec / --independent) and it conflicts ->
    refuse, and print the migration.

Rule of thumb: if a coding agent will ever run `br ready` in this repo, choose
dekspec mode now, even if DekSpec itself is never installed -- the `ds-`
workspace costs nothing to leave empty and the root stays free for code beads.

Why `min_hash_length 5`: at the default of 3, `br`'s random alphanumeric suffix
will occasionally mint IDs containing slurs -- observed while authoring
ADR-052. Bead IDs land in commit messages, branch names, and PR titles, so the
floor is raised.

Idempotent within a mode: an existing workspace is reported and left untouched.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

#: kind -> (directory relative to repo root, br ID prefix).
LAYOUTS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "dekspec": (
        ("code", ".", "cb"),
        ("issue", ".beads-issues", "iss"),
        ("dekspec", ".beads-dekspec", "ds"),
    ),
    "independent": (("issue", ".", "iss"),),
}

MODES = tuple(LAYOUTS)
DEFAULT_MODE = "independent"

MIN_HASH_LENGTH = 5


def _run(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _root_prefix(root: Path) -> str | None:
    """The ID prefix of the root workspace, or None if it is not initialised.

    Asks `br` rather than parsing config.yaml -- the prefix is written there as
    a comment, not a key, so the file is not a reliable source.
    """
    db = root / ".beads" / "beads.db"
    if not db.is_file():
        return None
    rc, out = _run(["br", "--db", str(db), "info"], cwd=root)
    if rc != 0:
        return None
    for line in out.splitlines():
        if line.lower().startswith("issue prefix:"):
            return line.split(":", 1)[1].strip()
    return None


def _refuse_mode_switch(root: Path, mode: str, found: str) -> None:
    """Explain a root-prefix conflict and print the migration, then stop."""
    want = LAYOUTS[mode][0][2]
    other = "independent" if mode == "dekspec" else "dekspec"
    print(
        f"\nRefusing: the root workspace already exists with prefix `{found}-`, "
        f"but --mode {mode} expects `{want}-` there.\n"
        f"\nThis repo looks like it was bootstrapped in {other} mode. The two "
        f"layouts disagree about\nwhat belongs at the root, so this is a "
        f"migration, not a re-run.\n"
        f"\nIf you do want to switch, the move is:\n"
        f"\n  1. br sync --flush-only                       # root -> .beads/issues.jsonl\n"
        f"  2. cp .beads/issues.jsonl <target>/.beads/    # target = the store that\n"
        f"                                                #   should now hold them\n"
        f"  3. br --db <target>/.beads/beads.db sync --import-only\n"
        f"  4. verify: counts, `br blocked`, comments\n"
        f"  5. rm -rf .beads && br init --prefix {want}\n"
        f"\nIDs are preserved by the import, so existing references keep resolving.\n"
        f"Back up .beads/ before step 5.",
        file=sys.stderr,
    )


def bootstrap(
    root: Path,
    *,
    mode: str = DEFAULT_MODE,
    explicit: bool = True,
    dry_run: bool = False,
) -> int:
    if shutil.which("br") is None:
        print(
            "Error: `br` (beads-rust) is not on PATH.\n"
            "  Install it first: https://github.com/steveyegge/beads",
            file=sys.stderr,
        )
        return 2

    layout = LAYOUTS[mode]

    found = _root_prefix(root)
    expected_root = layout[0][2]
    if found is not None and found != expected_root:
        if explicit:
            _refuse_mode_switch(root, mode, found)
            return 3
        # No mode was asked for, and the repo already answers the question.
        # Report the layout that exists rather than crying conflict.
        actual = next(
            (m for m, lay in LAYOUTS.items() if lay[0][2] == found), None
        )
        if actual is None:
            print(
                f"  Root workspace exists with prefix `{found}-`, which matches "
                f"neither layout.\n  Leaving it alone. Pass --mode explicitly if "
                f"you meant to change it.",
                file=sys.stderr,
            )
            return 0
        print(f"  Already bootstrapped in {actual} mode. Nothing to do.")
        mode, layout = actual, LAYOUTS[actual]

    failures = 0
    for kind, dirname, prefix in layout:
        target = (root / dirname).resolve()
        db = target / ".beads" / "beads.db"
        shown = ".beads" if dirname == "." else f"{dirname}/.beads"
        label = f"{kind:8s} {shown:22s} prefix={prefix}"

        if db.is_file():
            print(f"  exists   {label}")
            continue
        if dry_run:
            print(f"  would    {label}")
            continue

        target.mkdir(parents=True, exist_ok=True)
        rc, out = _run(["br", "init", "--prefix", prefix], cwd=target)
        if rc != 0:
            print(f"  FAILED   {label}\n           {out}", file=sys.stderr)
            failures += 1
            continue
        rc, out = _run(
            ["br", "config", "set", "min_hash_length", str(MIN_HASH_LENGTH)],
            cwd=target,
        )
        if rc != 0:
            print(
                f"  warn     {label} -- created, but min_hash_length not set\n"
                f"           {out}",
                file=sys.stderr,
            )
        print(f"  created  {label}")

    if failures:
        return 1

    if not dry_run:
        if mode == "dekspec":
            print(
                "\nDone. Three workspaces, three kinds:\n"
                "  bare `br ready`                              -> next ready CODE bead\n"
                "  br --db .beads-issues/.beads/beads.db ready   -> product issues\n"
                "  br --db .beads-dekspec/.beads/beads.db ready  -> DekSpec work\n"
                "\nNever run a bare mutating `br` command -- it writes the CODE store.\n"
                "Resolve the target first with beads_workspace.py and pass its --db.\n"
                "\nCommit all three .beads/issues.jsonl files -- they are the durable record."
            )
        else:
            print(
                "\nDone. One workspace, issues only:\n"
                "  bare `br ready` / `br create` / `br list`     -> your issues\n"
                "\nNo --db needed anywhere, and no DekSpec. If a coding agent ever runs\n"
                "`br ready` in this repo it will get issues, not coding tasks -- that is the\n"
                "trade this mode makes. See --help before switching.\n"
                "\nCommit .beads/issues.jsonl -- it is the durable record."
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the br bead workspaces for a repo (default: independent).",
        epilog="Needs only `br` on PATH. No DekSpec, no plugin, no prj-mgr.",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default=None,
        help=(
            "independent (default): one workspace at the root, issues only, no "
            "DekSpec and no --db discipline. dekspec: three workspaces -- code at "
            "the root, plus issue and DekSpec siblings."
        ),
    )
    parser.add_argument(
        "--dekspec",
        dest="mode",
        action="store_const",
        const="dekspec",
        help="shorthand for --mode dekspec",
    )
    parser.add_argument(
        "--independent",
        dest="mode",
        action="store_const",
        const="independent",
        help="shorthand for --mode independent (the default)",
    )
    parser.add_argument(
        "--at", type=Path, default=Path.cwd(), help="repo root (default: cwd)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would be created"
    )
    args = parser.parse_args(argv)
    root = args.at.resolve()
    explicit = args.mode is not None
    mode = args.mode or DEFAULT_MODE
    suffix = "" if explicit else ", default"
    print(f"Bootstrapping bead workspaces in {root}  (mode: {mode}{suffix})")
    return bootstrap(root, mode=mode, explicit=explicit, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
