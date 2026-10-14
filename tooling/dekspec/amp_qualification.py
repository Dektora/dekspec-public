"""Live Amp qualification: ``python -m dekspec.amp_qualification check`` (IB-197).

Surface skeleton written with IB-197's acceptance tests (ADR-062): the module
entry point exists, accepts the contracted command line
(``check --target <repo> [--out <dir>] [--amp <executable>]``) and does
nothing yet. It runs no ``amp`` command, writes nothing and exits 0. The
implementation replaces this body within IB-197's Scope.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Run the qualifier; the skeleton has no behavior and returns 0."""
    return 0


if __name__ == "__main__":
    sys.exit(main())
