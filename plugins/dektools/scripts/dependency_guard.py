#!/usr/bin/env python3
"""DekTools → DekSpec dependency guard (ADR-047 §Dependency architecture).

Refuses to run a `dekspec-required` tool when the DekSpec engine is absent,
with a remediation message — never the silent missing-`_lib` error an
uninstalled core otherwise produces.

The guard is **per-tool, keyed on the declared tier**, because ADR-047 grants
`prj-mgr` a `dekspec-enhanced` tier with zero coupling:

    dekspec-required  → refuse when the engine is absent   (exit 1)
    dekspec-enhanced  → always allowed, silently           (exit 0)

An uncatalogued tool is treated as `dekspec-required`: that is ADR-047's
declared default, and guarding an unknown tool is the safe direction to be
wrong in.

**The probe is `dekspec` on PATH.** ADR-047 settles this as the portable
signal across all six harnesses, since plugin-dependency semantics vary by
host and most hosts have no such declaration at all.

Standard library only, and it imports nothing DekSpec owns — this code runs
precisely when the engine is missing, so an engine import would fail with the
very error the guard exists to replace. `tests/test_dektools_dependency_guard.py`
enforces both properties.

Exit codes: 0 allowed · 1 guard fired · 2 usage error.

Usage:
    python dependency_guard.py <tool-name>
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "tool-catalog.json"

REQUIRED = "dekspec-required"
ENHANCED = "dekspec-enhanced"

# The curated public mirror (ADR-034), repeated literally: the branch that
# needs it fires only when the engine is absent, so no package constant is
# importable. Kept in step with plugins/dekspec/hooks-handlers/session-start-bootstrap.py.
MIRROR_GIT_URL = "https://github.com/Dektora/dekspec-public.git"
ENGINE_INSTALL_LINE = f'pipx install "git+{MIRROR_GIT_URL}@main"'
PLUGIN_INSTALL_LINE = "claude plugin install dekspec@dekspec"


def engine_present() -> bool:
    """ADR-047's host-agnostic probe: the `dekspec` engine on PATH."""
    return shutil.which("dekspec") is not None


def load_tiers(catalog_path: Path = CATALOG_PATH) -> dict[str, str]:
    """Map tool name → declared dependency tier.

    A missing or unreadable catalog yields an empty map, which lands every
    tool on the `dekspec-required` default rather than silently disarming
    the guard.
    """
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        tool["name"]: tool.get("dependency_tier", REQUIRED)
        for tool in payload.get("tools", [])
        if "name" in tool
    }


def tier_for(tool: str, tiers: dict[str, str] | None = None) -> str:
    """The tool's tier, defaulting to `dekspec-required` (ADR-047)."""
    return (load_tiers() if tiers is None else tiers).get(tool, REQUIRED)


def remediation(tool: str) -> str:
    return f"""\
⛔ DekTools requires DekSpec — the `dekspec` engine is not on PATH.

  `{tool}` is a {REQUIRED} tool (ADR-047): it reads the DekSpec IR or resolves
  shared `_lib` from the core plugin, so it cannot run without them.

  Install the engine, then the core plugin:
    {ENGINE_INSTALL_LINE}
    {PLUGIN_INSTALL_LINE}

  (`prj-mgr` holds the {ENHANCED} tier and runs with none of this.)"""


def check(tool: str) -> str | None:
    """Return the message the guard should print, or None to allow through."""
    if tier_for(tool) == ENHANCED:
        return None
    if engine_present():
        return None
    return remediation(tool)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0].startswith("-"):
        print(f"usage: {Path(__file__).name} <tool-name>", file=sys.stderr)
        return 2

    message = check(argv[0])
    if message is None:
        return 0
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
