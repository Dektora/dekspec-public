#!/usr/bin/env python3
"""DekSpec session-start bootstrap hook.

Fires on SessionStart. Surfaces the engine-install path when the `dekspec`
CLI is ABSENT (or best-effort flags a stale CLI), so an operator who has the
Claude Code plugin but not the Python engine learns how to close the gap
without having to know a version number.

Behavior:
  - CLI absent  → print a short guidance block with the pip-from-git install
                  line (no version pin → latest) plus the marketplace one-liner.
  - CLI present → disclose unrecorded project rules in DekSpec projects.
  - CLI present + stale (best-effort version compare against the plugin's
    own plugin.json) → print a brief upgrade hint. Never errors on failure.

The engine is acquired from the curated public MIRROR repo via pip-from-git
(ADR-034). The mirror repo slug is repeated literally here because the whole
point of this hook is to run WITHOUT the engine importable — we cannot import
any constant from a package that may not be installed.

Never blocks; never nonzero-exits on detection. Honors DEKSPEC_HOOK_DISABLE=1.

Environment overrides:
    DEKSPEC_HOOK_DISABLE=1    Skip the hook entirely.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Curated public mirror repo (ADR-034). Repeated literally because the engine
# is (by definition) not importable when the CLI-absent branch fires, so we
# cannot import any package constant.
MIRROR_REPO = "Dektora/dekspec-public"
MIRROR_GIT_URL = f"https://github.com/{MIRROR_REPO}.git"

WHEEL_INSTALL_LINE = f'pipx install "git+{MIRROR_GIT_URL}@main"'


def main() -> int:
    if os.environ.get("DEKSPEC_HOOK_DISABLE") == "1":
        return 0

    # Rotation-handoff resume (INT-176 / κ): surface the most recent
    # DekSpec-authored handoff so a rotated/compacted session resumes from a
    # native record — independent of whether the engine CLI is on PATH.
    _resume_from_handoff(Path.cwd().resolve())

    if shutil.which("dekspec") is None:
        _print_absent_guidance()
        return 0

    # CLI present — only speak if best-effort detection says it's stale.
    cli_version = _cli_version()
    plugin_version = _plugin_version()
    if cli_version and plugin_version and _is_stale(cli_version, plugin_version):
        print(
            "[dekspec] engine CLI may be stale: "
            f"CLI={cli_version} plugin={plugin_version}. "
            f"Re-acquire the engine ({WHEEL_INSTALL_LINE}) then reconcile "
            "content with `dekspec sync`; refresh the plugin with "
            "`claude plugin update dekspec@dekspec`. (The install script runs "
            "all three: scripts/install.sh.)",
            file=sys.stderr,
        )

    _project_rules_notice(Path.cwd())
    return 0


def _valid_role_state(data: object, *, record: bool = False) -> bool:
    """Validate the read-only CLI listing or its persisted disclosure snapshot."""
    keys = {"release", "roles", "platforms"} if record else {"release", "roles"}
    if not isinstance(data, dict) or set(data) != keys:
        return False
    if not isinstance(data["release"], str) or not data["release"]:
        return False
    if not isinstance(data["roles"], dict) or any(
        not isinstance(role, str) or not role or type(rev) is not int or rev < 1
        for role, rev in data["roles"].items()
    ):
        return False
    if record:
        hosts = data["platforms"]
        if (not isinstance(hosts, list)
                or any(not isinstance(host, str) or not host for host in hosts)
                or hosts != sorted(set(hosts))):
            return False
    return True


def _project_rules_notice(cwd: Path) -> None:
    """Ask the installed engine for disclosure text and revisions; never write."""
    if not (cwd / ".dekspec-version").is_file() and not (cwd / "dekspec").is_dir():
        return
    try:
        outputs = []
        for args in (("lib", "role-project-rules"), ("role", "--list", "--json")):
            proc = subprocess.run(
                ["dekspec", "resource", *args], cwd=cwd,
                capture_output=True, text=True, timeout=8,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if proc.returncode != 0:
                return
            outputs.append(proc.stdout)
        notice, raw_listing = outputs
        listing = json.loads(raw_listing)
        if not _valid_role_state(listing):
            return
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return
    try:
        record = json.loads((cwd / ".dekspec-role-disclosure.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        record = None
    if (_valid_role_state(record, record=True)
            and record["release"] == listing["release"]
            and record["roles"] == listing["roles"]):
        return
    print(notice, end="", file=sys.stderr)
    if not notice.endswith("\n"):
        print(file=sys.stderr)
    print("[dekspec] Run `dekspec sync` to record this disclosure.", file=sys.stderr)


def _resume_from_handoff(cwd: Path) -> None:
    """Read the latest handoff and print a short resume block. Best-effort.

    Silent outside a dekspec repo, when no handoff exists, or on any error so
    the parent SessionStart event is never disturbed.
    """
    if not (cwd / ".dekspec-version").exists() and not (cwd / "dekspec").is_dir():
        return
    executable = shutil.which("dektools")
    if executable is None:
        return
    try:
        proc = subprocess.run(
            [executable, "handoff", "read", "--at", str(cwd)],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode != 0:
            return
        payload = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return
    if not isinstance(payload, dict):
        return
    record = payload.get("record")
    stale = payload.get("stale")
    if not isinstance(stale, list) or any(not isinstance(reason, str) for reason in stale):
        return
    if not isinstance(record, dict):
        return
    objective = str(record.get("objective") or "").strip()
    next_action = str(record.get("next_safest_action") or "").strip()
    if not objective and not next_action:
        return
    if stale:
        print("[dekspec] prior handoff needs revalidation: " + "; ".join(stale), file=sys.stderr)
    print("[dekspec] resuming from prior session handoff:", file=sys.stderr)
    if objective:
        print(f"  objective: {objective}", file=sys.stderr)
    if next_action:
        print(f"  next safest action: {next_action}", file=sys.stderr)


def _print_absent_guidance() -> None:
    print("[dekspec] engine CLI not found on PATH.", file=sys.stderr)
    print(
        "  The Claude Code plugin needs the dekspec Python engine. Install it with:",
        file=sys.stderr,
    )
    print(f"    {WHEEL_INSTALL_LINE}", file=sys.stderr)
    print(
        "  (@main → latest; pin a release with @vX.Y.Z). Then register the "
        f"plugin marketplace: claude plugin marketplace add {MIRROR_REPO}",
        file=sys.stderr,
    )


def _cli_version() -> str | None:
    """Best-effort `dekspec --version`. None on any failure."""
    try:
        proc = subprocess.run(
            ["dekspec", "--version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = (proc.stdout or proc.stderr).strip()
    return _extract_version(out)


def _plugin_version() -> str | None:
    """Read the plugin's declared version from plugin.json. None on failure."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    manifest = Path(root) / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ver = data.get("version") if isinstance(data, dict) else None
    return _extract_version(str(ver)) if ver else None


def _extract_version(text: str) -> str | None:
    """Pull a dotted X.Y.Z token out of arbitrary version output."""
    import re

    m = re.search(r"\d+\.\d+\.\d+", text or "")
    return m.group(0) if m else None


def _is_stale(cli_version: str, plugin_version: str) -> bool:
    """True iff the CLI semver is strictly older than the plugin semver."""
    try:
        cli = tuple(int(p) for p in cli_version.split("."))
        plug = tuple(int(p) for p in plugin_version.split("."))
    except (ValueError, AttributeError):
        return False
    return cli < plug


if __name__ == "__main__":
    sys.exit(main())
