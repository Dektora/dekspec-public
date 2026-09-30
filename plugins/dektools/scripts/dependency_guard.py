#!/usr/bin/env python3
"""DekTools → DekSpec dependency guard (ADR-047 §Dependency architecture).

Refuses to run a `dekspec-required` tool when the DekSpec engine is absent,
with a remediation message — never the silent missing-`_lib` error an
uninstalled core otherwise produces.

The guard is **per-tool, keyed on the declared tier**, because ADR-047 grants
`project-board` a `dekspec-enhanced` tier with zero coupling:

    dekspec-required  → refuse when the engine is absent   (exit 1)
    dekspec-enhanced  → always allowed, silently           (exit 0)

An uncatalogued tool is treated as `dekspec-required`: that is ADR-047's
declared default, and guarding an unknown tool is the safe direction to be
wrong in.

**The probe is `dekspec` on PATH.** ADR-047 settles this as the portable
signal across all six harnesses, since plugin-dependency semantics vary by
host and most hosts have no such declaration at all. A present engine is then
asked, through read-only `--help` probes, for the capability the tool needs:
the core callers (`debug`, `deepen`) need `dekspec implement` with the caller
contract's verbs and a `dekspec deepen-record` whose `--help` lists `begin`
(IB-140 O-6), so a too-old core is named precisely rather than failing later.
The probes read `--help` as plain text: colour is turned off for the engine,
and any escape sequences it still emits are stripped (ds-kjwop). The guard
never writes to the repository it runs in.

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
import os
import re
import shutil
import subprocess
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
ENGINE_UPGRADE_LINE = f'pipx install --force "git+{MIRROR_GIT_URL}@main"'
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

  (`project-board` holds the {ENHANCED} tier and runs with none of this.)"""


#: Tools that hand governed work to core `/implement` (ADR-059's caller
#: contract; ADR-060 rule 4). They need the contract's verbs and IB-139's
#: pass record, whose `begin` action is the marker of a new-enough core.
CORE_CALLERS = frozenset({"debug", "deepen"})
CALLER_VERBS = ("resolve", "ready", "next", "ack", "status")
PASS_RECORD_MARKER = "begin"

#: Single-probe capabilities of the other `dekspec-required` tools: the
#: engine subcommand whose `--help` must succeed.
CAPABILITY_PROBES = {
    "setup-dektools": ["config", "get", "--help"],
    "ingest-docs": ["ingest", "--help"],
    "recover-specs": ["archeology", "scan", "--help"],
    "handoff": ["handoff", "--help"],
}

_CHOICES = re.compile(r"\{([\w,-]+)\}")

#: ANSI escape (CSI) sequences. Python 3.13+ argparse wraps command names in
#: them under FORCE_COLOR or on a terminal, and `\x1b[1;32mresolve` would
#: otherwise read as `mresolve` (ds-kjwop).
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

#: Variables that force colour on, whatever the output is connected to.
_FORCE_COLOUR = ("FORCE_COLOR", "CLICOLOR_FORCE")


def _upgrade(tool: str, missing: str, why: str) -> str:
    return f"""\
⛔ DekTools `{tool}` needs a newer DekSpec core — the installed engine lacks {missing}.

  {why}

  Upgrade the engine and the core plugin to the release that matches this toolkit:
    {ENGINE_UPGRADE_LINE}
    {PLUGIN_INSTALL_LINE}"""


def _probe(engine: str, args: list[str]) -> subprocess.CompletedProcess:
    """Run one read-only `--help` probe and return its output as plain text.
    It writes nothing: the target repository is never modified by the guard
    (IB-140 O-6). Colour is turned off for the engine, and escapes it still
    emits are stripped, so command names parse whatever the user's colour
    settings (ds-kjwop)."""
    env = {k: v for k, v in os.environ.items() if k not in _FORCE_COLOUR}
    env.update(NO_COLOR="1", PYTHON_COLORS="0")
    proc = subprocess.run([engine, *args], capture_output=True, text=True, env=env,
                          timeout=30, check=False, stdin=subprocess.DEVNULL)
    proc.stdout = _ANSI.sub("", proc.stdout or "")
    return proc


def _help_choices(text: str) -> set[str]:
    """The choices argparse renders as `{a,b,c}` in a `--help` page."""
    return {word for group in _CHOICES.findall(text) for word in group.split(",")}


def _core_caller_problem(tool: str, engine: str) -> str | None:
    """IB-140 O-6: a core caller needs `dekspec implement` with the caller
    contract's verbs, and a `deepen-record` whose `--help` lists `begin`."""
    implement = _probe(engine, ["implement", "--help"])
    listed = set(re.findall(r"[a-z][\w-]*", implement.stdout))
    absent = [verb for verb in CALLER_VERBS if verb not in listed]
    if implement.returncode or absent:
        missing = ("`dekspec implement`" if implement.returncode
                   else f"`dekspec implement` {', '.join(absent)}")
        return _upgrade(tool, missing,
                        f"`{tool}` hands governed work to core's caller contract "
                        f"(`implement {'|'.join(CALLER_VERBS)}`, ADR-059); it never "
                        "substitutes its own implementation driver (ADR-060 rule 4).")
    record = _probe(engine, ["deepen-record", "--help"])
    if record.returncode or PASS_RECORD_MARKER not in _help_choices(record.stdout):
        return _upgrade(tool, f"the `{PASS_RECORD_MARKER}` action of `dekspec deepen-record`",
                        f"`dekspec deepen-record --help` does not list `{PASS_RECORD_MARKER}`, "
                        "the pass record that binds a pass to core's result; the engine "
                        "predates the caller contract this toolkit follows.")
    return None


def check(tool: str) -> str | None:
    """Return the message the guard should print, or None to allow through."""
    if tier_for(tool) == ENHANCED:
        return None
    engine = shutil.which("dekspec")
    if engine is None:
        return remediation(tool)
    try:
        if tool in CORE_CALLERS:
            return _core_caller_problem(tool, engine)
        command = CAPABILITY_PROBES.get(tool)
        if command and _probe(engine, command).returncode:
            return (f"DekTools {tool}: installed engine lacks {' '.join(command[:-1])}; "
                    "upgrade to the matching toolkit/engine release.")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"DekTools {tool}: capability probe failed: {exc}; repair or reinstall the engine."
    return None


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
