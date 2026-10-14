"""Standalone craft CLI; governed work uses an optional external receipt."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv in (["--version"], ["-v"], ["-V"]):
        print(__version__)
        return 0
    from .host_install import register_install
    from .toolkit_cli import register_helpers

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    register_helpers(sub)
    register_install(sub)
    args = parser.parse_args(argv)
    if not args.command:
        from .rotation_handoff import read_latest_handoff, target_root
        from pathlib import Path

        root = target_root(Path.cwd())
        print(f"repo: {root}")
        print(f"handoffs: {int(read_latest_handoff(root) is not None)}")
        print("help[2]: dektools handoff read,dektools deepen-record status")
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
