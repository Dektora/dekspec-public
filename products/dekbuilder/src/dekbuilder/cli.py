"""Deck Builder's independently installed command entry point."""
from __future__ import annotations

import argparse
import sys
from typing import Any

from dekbuilder import __version__
from dekbuilder.flow import register as register_wave
from dekbuilder.implement.cli import register
from dekbuilder.amp import register as register_install


def _run_pr_branch(args: argparse.Namespace) -> int:
    # Load the provider-dependent handler only for this command. Other
    # commands must retain their own missing-provider response.
    from dekbuilder.pr_branch import _run

    return _run(args)


def register_pr_branch(sub: Any) -> None:
    """Add the `pr-branch` subcommand to DekBuilder's parser."""
    parser = sub.add_parser("pr-branch", help="build a clean <branch>-pr branch without spec-only commits")
    parser.add_argument("target", nargs="?", default="main", help="target revision (default: main)")
    parser.add_argument("--at", default=None, help="repository (default: git top level of the working directory)")
    parser.add_argument("--json", action="store_true", help="print one JSON report")
    parser.set_defaults(func=_run_pr_branch)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dekbuilder", description="Governed in-host construction using installed Spec S0.")
    parser.add_argument("--version", "-V", "-v", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    register(sub)
    register_wave(sub)
    register_pr_branch(sub)
    register_install(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
