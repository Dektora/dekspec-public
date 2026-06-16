#!/usr/bin/env python3
"""DekSpec session-start bootstrap hook.

Fires on SessionStart. Surfaces the engine-install path when the `dekspec`
CLI is ABSENT (or best-effort flags a stale CLI), so an operator who has the
Claude Code plugin but not the Python engine learns how to close the gap
without having to know a version number.

Behavior:
  - CLI absent  → print a short guidance block with the pip-from-git install
                  line (no version pin → latest) plus the marketplace one-liner.
  - CLI present + current → stay silent.
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
            "content with `dekspec library sync`; refresh the plugin with "
            "`claude plugin update dekspec@dekspec`. (The install script runs "
            "all three: scripts/install.sh.)",
            file=sys.stderr,
        )

    # CLI present and current → stay silent.
    return 0


def _import_handoff_engine(cwd: Path):
    """Best-effort load of the native rotation-handoff engine.

    The handler runs from the plugin tree, not the installed package. Prefer the
    in-repo source at `<repo>/tooling/dekspec/rotation_handoff.py` (loaded
    directly from its file, so it works even when a different `dekspec` package
    is already on sys.path), then fall back to a plain import. Returns the
    module or None.
    """
    src = cwd / "tooling" / "dekspec" / "rotation_handoff.py"
    if src.is_file():
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "dekspec_rotation_handoff_engine", src
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
        except Exception:
            pass
    try:
        from dekspec import rotation_handoff  # type: ignore

        return rotation_handoff
    except Exception:
        return None


def _resume_from_handoff(cwd: Path) -> None:
    """Read the latest handoff and print a short resume block. Best-effort.

    Silent outside a dekspec repo, when no handoff exists, or on any error so
    the parent SessionStart event is never disturbed.
    """
    if not (cwd / ".dekspec-version").exists() and not (cwd / "dekspec").is_dir():
        return
    engine = _import_handoff_engine(cwd)
    if engine is None:
        return
    try:
        record = engine.read_latest_handoff(cwd)
    except Exception:
        return
    if not isinstance(record, dict):
        return
    objective = str(record.get("objective") or "").strip()
    next_action = str(record.get("next_safest_action") or "").strip()
    if not objective and not next_action:
        return
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
