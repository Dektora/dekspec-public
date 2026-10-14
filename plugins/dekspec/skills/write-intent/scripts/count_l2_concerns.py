#!/usr/bin/env python3
"""Count the distinct L2 concerns an Intent's Behavior placement table names (IB-215, O-13).

Surface skeleton written with IB-215's acceptance tests (ADR-062): the
contracted command line with no behavior. It accepts the contracted arguments
and exits 0 without output; the implementation replaces the body of ``main``.

Runnable: python count_l2_concerns.py <intent-path> [--json]
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="count_l2_concerns.py",
        description="Count the distinct L2 concerns in an Intent's Behavior placement table.",
    )
    parser.add_argument("intent_path", help="path to the Intent file")
    parser.add_argument("--json", action="store_true", help="print a JSON object")
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
