#!/usr/bin/env python3
"""DekTools a-la-carte selector (ADR-047 — the `setup-dektools` engine half).

ADR-047 makes DekTools a suite you opt into tool by tool: "a tool catalog + a
persisted per-installation enabled-set that gates which tools register/emit",
with **nothing on by default**, re-runnable add *and* remove, and removal that
"disables the tool surface, never deletes user data".

Core already owns the persistence and the emit:

    dekspec config get dektools.enabled --at <repo>      # comma-separated
    dekspec config set dektools.enabled "a,b,c" --at <repo>
    dekspec install --platform <host> --target <repo>    # emits exactly that
                                                         # subset, prunes the rest

This script is the operator-facing selector on top of them. It reads the
catalog, renders the current selection with each tool's `dependency_tier`,
computes the add/remove diff, persists through `dekspec config set`, and
re-runs `dekspec install` so the host tree matches the new selection. It
decides nothing the config does not already record, and it deletes nothing
itself — pruning is `dekspec install`'s scoped job.

**Persistence goes through the `dekspec` CLI, never an import.** The engine is
normally pipx-installed, so `import dekspec` from whatever interpreter runs a
skill script is not a path that exists in production; `dekspec` on PATH is
ADR-047's host-agnostic signal and is the same surface on all six harnesses.
Standard library only, for the same reason.

Exit codes: 0 ok · 1 failure (no config, no engine, failed write) · 2 usage
error (unknown flag, unknown tool name).

Usage:
    selector.py status  [--at PATH] [--full] [--json]
    selector.py enable  <tool>... [--at PATH] [--platform HOST] [--json]
    selector.py disable <tool>... [--at PATH] [--platform HOST] [--json]
    selector.py set     [<tool>...] [--at PATH] [--platform HOST] [--json]
    selector.py apply   --platform HOST [--at PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_KEY = "dektools.enabled"
CONFIG_RELPATH = Path(".dekspec") / "config.yaml"
REQUIRED = "dekspec-required"
ENHANCED = "dekspec-enhanced"

# The bead's UX note: after every step show what is still available, capped so
# a 16-tool catalog does not bury the result (AXI content-truncation).
REMAINING_CAP = 8

HOSTS = ("claude", "codex", "antigravity", "cursor", "copilot", "pi")


class SelectorError(Exception):
    """A failure the operator can act on. `code` is the process exit code."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# catalog
# --------------------------------------------------------------------------- #
def find_catalog(explicit: str | None = None, repo: Path | None = None) -> Path:
    """Locate `tool-catalog.json`.

    Checked in order: an explicit `--catalog`, `$DEKTOOLS_CATALOG`, the plugin
    root this script ships in, and `plugins/dektools/` above either this file
    or the target repo. The emitted per-host tree carries the skill without
    the plugin root, so more than one of these is load-bearing.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SelectorError(f"No DekTools catalog at {path}.", 2)
        return path

    env = os.environ.get("DEKTOOLS_CATALOG")
    if env and Path(env).is_file():
        return Path(env)

    here = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in here.parents:
        candidates.append(parent / "tool-catalog.json")
        candidates.append(parent / "plugins" / "dektools" / "tool-catalog.json")
    if repo is not None:
        base = Path(repo).resolve()
        for parent in (base, *base.parents):
            candidates.append(parent / "plugins" / "dektools" / "tool-catalog.json")

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise SelectorError(
        "Could not find the DekTools tool catalog (tool-catalog.json). "
        "Pass --catalog PATH or set DEKTOOLS_CATALOG.",
        1,
    )


def load_catalog(path: Path) -> list[dict[str, str]]:
    """Catalog entries as `{name, dependency_tier, summary}`, catalog order.

    Catalog order is the presentation order: it is curated, and re-sorting it
    would make the numbered "still remaining" list shuffle between runs.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise SelectorError(f"Could not read the DekTools catalog at {path}: {err}", 1)
    tools = []
    for entry in payload.get("tools", []):
        name = entry.get("name")
        if not name:
            continue
        tools.append(
            {
                "name": name,
                # ADR-047's declared default for an undeclared tool.
                "tier": entry.get("dependency_tier", REQUIRED),
                "summary": entry.get("summary", ""),
            }
        )
    if not tools:
        raise SelectorError(f"The DekTools catalog at {path} declares no tools.", 1)
    return tools


# --------------------------------------------------------------------------- #
# the dekspec CLI seam
# --------------------------------------------------------------------------- #
def _dekspec(*argv: str) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("dekspec")
    if exe is None:
        raise SelectorError(
            "The `dekspec` engine is not on PATH, so the selection cannot be "
            "persisted. setup-dektools is a dekspec-required tool (ADR-047) — "
            "run plugins/dektools/scripts/dependency_guard.py setup-dektools "
            "for install instructions.",
            1,
        )
    return subprocess.run([exe, *argv], capture_output=True, text=True, check=False)


def read_selection(repo: Path) -> list[str]:
    """The repo's enabled-set, or `[]`.

    ADR-047 forces nothing on, so an unset key and an empty list mean the same
    thing — `config get` exits non-zero on an unset key, and that is not an
    error here. A *missing config file* is, because there is nowhere to write.
    """
    if not (repo / CONFIG_RELPATH).is_file():
        raise SelectorError(
            f"No DekSpec config at {repo / CONFIG_RELPATH}. Run `dekspec init` "
            "(or /dekspec:setup-dekspec) first — the DekTools selection is "
            "persisted in the repo's DekSpec config so it travels with the "
            "project.",
            1,
        )
    proc = _dekspec("config", "get", CONFIG_KEY, "--at", str(repo))
    if proc.returncode != 0:
        return []
    return [part.strip() for part in proc.stdout.strip().split(",") if part.strip()]


def write_selection(repo: Path, tools: list[str]) -> None:
    proc = _dekspec("config", "set", CONFIG_KEY, ",".join(tools), "--at", str(repo))
    if proc.returncode != 0:
        raise SelectorError(
            f"`dekspec config set {CONFIG_KEY}` failed: {(proc.stderr or proc.stdout).strip()}",
            1,
        )


def run_install(repo: Path, platform: str) -> str:
    """Re-emit the host tree so it matches the persisted selection."""
    proc = _dekspec("install", "--platform", platform, "--target", str(repo))
    if proc.returncode != 0:
        raise SelectorError(
            f"`dekspec install --platform {platform}` failed: "
            f"{(proc.stderr or proc.stdout).strip()}",
            1,
        )
    first = proc.stdout.strip().splitlines()
    return first[0] if first else ""


# --------------------------------------------------------------------------- #
# selection algebra
# --------------------------------------------------------------------------- #
def resolve_names(names: list[str], catalog: list[dict[str, str]]) -> list[str]:
    """De-duplicate `names`, order-preserving; reject anything uncatalogued.

    The catalog is ADR-047's list of known tools, so a typo is a usage error
    and not a silently-ignored no-op — a selector that accepts `spke` and
    reports success has lied about what is enabled.
    """
    known = {tool["name"] for tool in catalog}
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SelectorError(
            f"{', '.join(repr(u) for u in unknown)} "
            f"{'is' if len(unknown) == 1 else 'are'} not a DekTools tool. "
            f"Valid tools: {', '.join(t['name'] for t in catalog)}",
            2,
        )
    return list(dict.fromkeys(names))


def apply_change(
    current: list[str], command: str, names: list[str], catalog: list[dict[str, str]]
) -> list[str]:
    """The enabled-set after `command`, in catalog order.

    Catalog order rather than click order, so the persisted value is a
    function of the selection alone — two operators who enable the same tools
    in a different sequence get the same config line, and re-running is a
    genuine no-op instead of a reordering diff.
    """
    if command == "enable":
        wanted = set(current) | set(names)
    elif command == "disable":
        wanted = set(current) - set(names)
    elif command == "set":
        wanted = set(names)
    else:  # pragma: no cover - argparse constrains the command set
        raise SelectorError(f"Unknown command {command!r}.", 2)
    ordered = [t["name"] for t in catalog if t["name"] in wanted]
    # A name in the config that has since left the catalog is carried through
    # rather than silently dropped by a routine `enable` of something else.
    ordered += [n for n in current if n in wanted and n not in ordered]
    return ordered


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _tier_of(name: str, catalog: list[dict[str, str]]) -> str:
    for tool in catalog:
        if tool["name"] == name:
            return tool["tier"]
    return REQUIRED


def _enhanced_note(catalog: list[dict[str, str]]) -> str | None:
    enhanced = [t["name"] for t in catalog if t["tier"] == ENHANCED]
    if not enhanced:
        return None
    return (
        f"note: {', '.join(enhanced)} "
        f"{'holds' if len(enhanced) == 1 else 'hold'} the {ENHANCED} tier — "
        "usable with no DekSpec engine installed, and the dependency guard "
        f"stays silent for {'it' if len(enhanced) == 1 else 'them'}. Every "
        f"other tool is {REQUIRED}."
    )


def render_status(
    repo: Path, enabled: list[str], catalog: list[dict[str, str]], full: bool
) -> list[str]:
    lines = [
        f"dektools  enabled={len(enabled)}/{len(catalog)}  repo={repo}",
        "",
    ]
    if enabled:
        lines.append(f"enabled[{len(enabled)}]{{tool,tier}}:")
        lines += [f"  {n},{_tier_of(n, catalog)}" for n in enabled]
    else:
        lines.append("enabled[0]: nothing enabled (ADR-047: nothing is on by default)")
    lines.append("")

    remaining = [t for t in catalog if t["name"] not in enabled]
    shown = remaining if full else remaining[:REMAINING_CAP]
    lines.append(f"still remaining[{len(shown)} of {len(remaining)}]{{n,tool,tier}}:")
    if not remaining:
        lines.append("  (none — every catalogued tool is enabled)")
    for i, tool in enumerate(shown, start=1):
        lines.append(f"  {i},{tool['name']},{tool['tier']}")
    if len(shown) < len(remaining):
        lines.append(f"  ({len(remaining) - len(shown)} more — pass --full for all)")

    note = _enhanced_note(catalog)
    if note:
        lines += ["", note]
    return lines


def render_change(
    repo: Path,
    before: list[str],
    after: list[str],
    catalog: list[dict[str, str]],
    installed: str | None,
    platform: str | None,
) -> list[str]:
    added = [n for n in after if n not in before]
    removed = [n for n in before if n not in after]
    lines = [
        f"enabled[{len(after)}]: {','.join(after) if after else '(none)'}",
        f"added[{len(added)}]: {','.join(added) if added else '(none)'}",
        f"removed[{len(removed)}]: {','.join(removed) if removed else '(none)'}",
    ]
    if removed:
        lines.append(
            "removal is non-destructive: it disables the tool surface on the "
            "next emit and deletes no user data."
        )
    lines.append("")
    if installed is not None:
        lines.append(installed)
    lines += render_status(repo, after, catalog, full=False)
    lines.append("")
    lines.append("help[]:")
    if installed is None:
        lines.append(
            f"  apply:   dekspec install --platform <host> --target {repo}   "
            "# re-emit so the host tree matches the selection"
        )
    lines.append(f"  add:     selector.py enable <tool>... --at {repo}")
    lines.append(f"  remove:  selector.py disable <tool>... --at {repo}")
    if platform is None:
        lines.append(f"  hosts:   {', '.join(HOSTS)}")
    return lines


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="selector.py",
        description=(
            "DekTools a-la-carte selector (ADR-047): show, add to, or remove "
            "from the per-repo enabled-set, then re-emit the host tree."
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--at", default=".", help="Repo root (default: cwd).")
        p.add_argument("--catalog", default=None, help="tool-catalog.json override.")
        p.add_argument("--json", action="store_true", help="Machine-readable output.")

    p_status = sub.add_parser("status", help="Show the catalog and what is enabled.")
    common(p_status)
    p_status.add_argument(
        "--full", action="store_true", help="List every remaining tool, uncapped."
    )

    for name, helptext in (
        ("enable", "Add tools to the enabled-set."),
        ("disable", "Remove tools from the enabled-set."),
        ("set", "Replace the enabled-set (no names clears it)."),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("tools", nargs="*", metavar="<tool>")
        common(p)
        p.add_argument(
            "--platform",
            choices=HOSTS,
            default=None,
            help="Re-run `dekspec install` for this host after persisting.",
        )

    p_apply = sub.add_parser("apply", help="Re-emit a host tree from the persisted selection.")
    common(p_apply)
    p_apply.add_argument("--platform", choices=HOSTS, required=True)
    return parser


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "status"
    repo = Path(args.at).resolve()

    catalog = load_catalog(find_catalog(args.catalog, repo))
    before = read_selection(repo)

    if command == "status":
        if args.json:
            print(
                json.dumps(
                    {
                        "repo": str(repo),
                        "enabled": before,
                        "tools": catalog,
                    },
                    indent=2,
                )
            )
        else:
            print("\n".join(render_status(repo, before, catalog, args.full)))
        return 0

    if command == "apply":
        installed = run_install(repo, args.platform)
        if args.json:
            print(json.dumps({"repo": str(repo), "enabled": before}, indent=2))
        else:
            print(installed)
            print("\n".join(render_status(repo, before, catalog, full=False)))
        return 0

    names = resolve_names(args.tools, catalog)
    after = apply_change(before, command, names, catalog)

    if after != before:
        write_selection(repo, after)
    installed = run_install(repo, args.platform) if args.platform else None

    if args.json:
        print(
            json.dumps(
                {
                    "repo": str(repo),
                    "enabled": after,
                    "added": [n for n in after if n not in before],
                    "removed": [n for n in before if n not in after],
                    "installed": installed,
                },
                indent=2,
            )
        )
    else:
        print("\n".join(render_change(repo, before, after, catalog, installed, args.platform)))
    return 0


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except SelectorError as err:
        print(f"Error: {err}", file=sys.stderr)
        return err.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
