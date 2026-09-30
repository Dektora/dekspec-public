#!/usr/bin/env python3
"""Select optional toolkit skills through the installed engine (stdlib only)."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HOSTS = {"claude": ".claude", "codex": ".codex", "antigravity": ".antigravity",
         "cursor": ".cursor", "copilot": ".github", "pi": ".pi"}


class SelectorError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SelectorError(message, 2)


def find_catalog(explicit=None, repo=None):
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SelectorError(f"No catalog: {path}", 2)
        return path
    for parent in Path(__file__).resolve().parents:
        path = parent / "tool-catalog.json"
        if path.is_file():
            return path
    raise SelectorError("Toolkit catalog missing; reinstall the DekTools distribution.")


def load_catalog(path):
    try:
        data = json.loads(path.read_text())
        return [{"name": t["name"], "tier": t["dependency_tier"], "summary": t["summary"]}
                for t in data["tools"] if t["name"] != "setup-dektools"]
    except (OSError, ValueError, KeyError) as exc:
        raise SelectorError(f"Invalid catalog: {exc}") from exc


def _dekspec(*args):
    exe = shutil.which("dekspec")
    if exe is None:
        raise SelectorError("DekSpec engine unavailable; install the matching engine release and retry.")
    return subprocess.run([exe, *args], capture_output=True, text=True, check=False)


def read_selection(repo):
    result = _dekspec("config", "get", "dektools.enabled", "--at", str(repo))
    if result.returncode:
        raise SelectorError(f"Cannot read selection: {(result.stderr or result.stdout).strip()}")
    return [n.strip() for n in result.stdout.strip().split(",") if n.strip()]


def write_selection(repo, names):
    result = _dekspec("config", "set", "dektools.enabled", ",".join(names), "--at", str(repo))
    if result.returncode:
        raise SelectorError(f"Cannot save selection: {(result.stderr or result.stdout).strip()}")


def resolve_names(names, catalog):
    unknown = set(names) - {t["name"] for t in catalog}
    if unknown:
        raise SelectorError(f"Unknown tools: {', '.join(sorted(unknown))}", 2)
    return list(dict.fromkeys(names))


def apply_change(current, command, names, catalog):
    wanted = (set(current) | set(names) if command == "enable" else
              set(current) - set(names) if command == "disable" else set(names))
    return sorted(wanted)


def installed_state(repo):
    result = {}
    for host, directory in HOSTS.items():
        path = repo / directory / ".dektools-install.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                # A manifest alone is insufficient if files were modified/deleted.
                import hashlib
                intact = all(not Path(rel).is_absolute() and ".." not in Path(rel).parts
                             and (repo / directory / rel).resolve().is_relative_to(repo)
                             and (repo / directory / rel).is_file() and
                             hashlib.sha256((repo / directory / rel).read_bytes()).hexdigest() == digest
                             for rel, digest in data["files"].items())
                result[host] = {"enabled": data["enabled"], "intact": intact}
            except (OSError, ValueError, KeyError):
                result[host] = {"enabled": None, "intact": False}
    return result


def plugin_delivers_core(repo, platform):
    """Claude's marketplace already delivers core and setup; running from there
    (outside the repo) means emitting them again would shadow the plugins."""
    return platform == "claude" and not Path(__file__).resolve().is_relative_to(repo.resolve())


def run_install(repo, platform, catalog=None):
    args = ["install", "--platform", platform, "--target", str(repo)]
    if catalog and (catalog.parent / "tools").is_dir():
        args += ["--dektools-source", str(catalog.parent)]
    if plugin_delivers_core(repo, platform):
        args.append("--dektools-only")
    result = _dekspec(*args)
    if result.returncode:
        raise SelectorError(f"Desired selection saved; install failed: {(result.stderr or result.stdout).strip()}. "
                            f"Repair with selector.py apply --platform {platform} --at {repo}")
    return result.stdout.strip()


def build_parser():
    parser = Parser(description="Show/select optional DekTools skills; setup is always available.")
    parser.add_argument("command", choices=("status", "enable", "disable", "set", "apply"), nargs="?", default="status")
    parser.add_argument("tools", nargs="*")
    parser.add_argument("--at", default=".", help="Target repository (default cwd).")
    parser.add_argument("--catalog", help="Distribution catalog path.")
    parser.add_argument("--platform", choices=HOSTS, help="Host to install into.")
    parser.add_argument("--json", action="store_true", help="Full structured output.")
    parser.add_argument("--full", action="store_true", help="Include descriptions.")
    return parser


def run(argv):
    args = build_parser().parse_args(argv)
    repo = Path(args.at).resolve()
    # Commands invoked from a nested working directory still target its repo.
    for parent in (repo, *repo.parents):
        if (parent / ".git").exists() or (parent / ".dekspec/config.yaml").is_file():
            repo = parent
            break
    path = find_catalog(args.catalog, repo)
    catalog = load_catalog(path)
    before = read_selection(repo)
    after = before
    if args.command in ("enable", "disable", "set"):
        after = apply_change(before, args.command, resolve_names(args.tools, catalog), catalog)
        if after != before:
            write_selection(repo, after)
    elif args.tools:
        raise SelectorError("status/apply do not accept tool names", 2)
    if args.command == "apply" and not args.platform:
        raise SelectorError("apply requires --platform", 2)
    if args.command != "status" and args.platform:
        run_install(repo, args.platform, path)
    installed = installed_state(repo)
    data = {"repo": str(repo), "desired": after, "installed": installed, "tools": catalog}
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"repo: {json.dumps(str(repo))}\ndesired[{len(after)}]: {','.join(after)}")
        print(f"hosts[{len(installed)}]{{host,status}}:")
        for host, state in installed.items():
            active = state["intact"] and set(state["enabled"] or []) == set(after)
            print(f"  {host},{'applied' if active else 'needs-repair'}")
        fields = "name,selected,tier,description" if args.full else "name,selected,tier"
        print(f"tools[{len(catalog)}]{{{fields}}}:")
        for tool in catalog:
            description = "," + json.dumps(tool["summary"]) if args.full else ""
            print(f"  {tool['name']},{str(tool['name'] in after).lower()},{tool['tier']}{description}")
        print('help[2]: "Enable/disable by name; apply with --platform HOST", "Reload the host after changes; setup always remains available"')
    return 0


def main(argv=None):
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except (SelectorError, OSError) as exc:
        print(f"error: {json.dumps(str(exc))}")
        return getattr(exc, "code", 1)


if __name__ == "__main__":
    sys.exit(main())
