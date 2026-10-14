#!/usr/bin/env python3
"""Initialize independently usable issue stores without requiring DekSpec.

Independent mode retains a single root issue store. DekSpec mode creates only
.beads-issues and .beads-dekspec: ADR-056 retired code
beads, and existing root history is left untouched. Prefixes come from local
project configuration or tracked store pins and are always pinned in config.
Changing an existing identity requires the explicit, previewable migration;
this bootstrap never deletes or repurposes a store.
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
        ("issue", ".beads-issues", "iss"),
        ("dekspec", ".beads-dekspec", "ds"),
    ),
    "independent": (("issue", ".", "iss"),),
}

MODES = tuple(LAYOUTS)
DEFAULT_MODE = "independent"

MIN_HASH_LENGTH = 5


def _pin_prefix(directory: Path, prefix: str) -> None:
    import re
    config = directory / ".beads/config.yaml"
    text = config.read_text() if config.exists() else ""
    text = re.sub(r"(?m)^issue_prefix\s*:.*\n?", "", text)
    config.write_text(text.rstrip("\n") + f"\nissue_prefix: {prefix}\n")


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
    print(
        f"Refusing to change existing root prefix {found!r} to {want!r}. "
        "Preserve the root store. Use a reviewed migration to move issues; "
        "dekspec beads reprefix previews identity changes in the two kind stores.",
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

    found = _root_prefix(root) if mode == "independent" else None
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

    from beads_workspace import _identity
    try:
        layout = tuple((kind, dirname, _identity(root, (root / dirname).resolve(), kind, prefix))
                       for kind, dirname, prefix in layout)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    failures = 0
    for kind, dirname, prefix in layout:
        target = (root / dirname).resolve()
        db = target / ".beads" / "beads.db"
        shown = ".beads" if dirname == "." else f"{dirname}/.beads"
        label = f"{kind:8s} {shown:22s} prefix={prefix}"

        if db.is_file() or (target / ".beads/issues.jsonl").is_file():
            if not dry_run:
                _pin_prefix(target, prefix)
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
        _pin_prefix(target, prefix)
        print(f"  created  {label}")

    if failures:
        return 1

    if not dry_run:
        if mode == "dekspec":
            print(
                "\nDone. Two issue/governance workspaces; existing root history preserved.\n"
                "  br --db .beads-issues/.beads/beads.db ready   -> product issues\n"
                "  br --db .beads-dekspec/.beads/beads.db ready  -> DekSpec work\n"
                "Commit both issues.jsonl exports and config.yaml prefix pins."
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
