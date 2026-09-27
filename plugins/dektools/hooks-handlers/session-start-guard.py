#!/usr/bin/env python3
"""DekTools session-start dependency preflight (ADR-047).

ADR-047 settles the guard mechanism as "a `plugin.json` dependency declaration
where the host supports it, otherwise a first-run / session-start preflight".
No harness DekSpec targets carries plugin-level dependency semantics today, so
this preflight is the mechanism everywhere — it surfaces the remediation once,
at session start, before the operator reaches a tool that would fail.

**Loud, but never fatal.** It prints and exits 0. A nonzero SessionStart hook
breaks the whole session, which is the wrong trade for an operator who may
have installed DekTools only to read a project board — `prj-mgr` works fine
without DekSpec, and the per-tool guard still refuses the tools that do not.

Honors DEKTOOLS_HOOK_DISABLE=1.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import dependency_guard as guard  # noqa: E402


def main() -> int:
    if os.environ.get("DEKTOOLS_HOOK_DISABLE") == "1":
        return 0
    if guard.engine_present():
        return 0

    tiers = guard.load_tiers()
    blocked = sorted(n for n, t in tiers.items() if t != guard.ENHANCED)
    available = sorted(n for n, t in tiers.items() if t == guard.ENHANCED)

    print("⛔ DekTools: the `dekspec` engine is not on PATH.")
    print()
    print(f"  {len(blocked)} DekTools skills need it and will refuse to run:")
    print(f"    {', '.join(blocked)}")
    if available:
        print(f"  Still fully usable without it: {', '.join(available)}")
    print()
    print("  Install the engine, then the core plugin:")
    print(f"    {guard.ENGINE_INSTALL_LINE}")
    print(f"    {guard.PLUGIN_INSTALL_LINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
