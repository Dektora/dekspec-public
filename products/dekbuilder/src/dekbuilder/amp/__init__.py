"""DekBuilder's Amp install: `dekbuilder install --platform amp` (IB-235 O-15 to O-18).

Surface skeleton written with IB-235's acceptance tests (ADR-062): the
contracted `install` command exists and accepts its arguments, with no
behavior yet. The implementation replaces this module's body within IB-235's
Scope (`products/dekbuilder/src/dekbuilder/amp/**`).
"""
from __future__ import annotations

import argparse
from typing import Any

__all__ = ["register", "run"]


def register(sub: Any) -> None:
    """Add the `install` subcommand to DekBuilder's parser."""
    parser = sub.add_parser("install", help="install DekBuilder's skills into a host project")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--source", default=None)
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    """Skeleton: does nothing yet."""
    return 0
