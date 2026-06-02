#!/usr/bin/env python3
"""DekSpec post-edit audit hook.

Fires on PostToolUse for Edit|Write|MultiEdit. When the edited file lives
under `<cwd>/dekspec/` (the artifact tree) or `<cwd>/.claude/skills/`
(vendored skills), runs `dekspec validate <path>` for fast per-artifact
feedback. Surfaces validation errors as a non-blocking advisory; never
blocks the tool call.

Disabled unless the consumer has `dekspec` on PATH. Silent on every
non-applicable tool call.

Environment overrides:
    DEKSPEC_HOOK_DISABLE=1   Skip the hook entirely.
    DEKSPEC_HOOK_TIMEOUT=N   Per-validate-call timeout in seconds (default: 5).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if os.environ.get("DEKSPEC_HOOK_DISABLE") == "1":
        return 0

    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        # Bad input — never block the tool.
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    path = Path(file_path)
    cwd = Path.cwd().resolve()

    # Only act on edits inside this project's dekspec/ artifact tree.
    # Vendored skill edits live under .claude/skills/ but skills don't
    # round-trip through `dekspec validate`, so scope to dekspec/ only.
    try:
        rel = path.resolve().relative_to(cwd)
    except (ValueError, OSError):
        return 0
    if not str(rel).startswith("dekspec/") and not str(rel).startswith("dekspec\\"):
        return 0
    if path.suffix.lower() != ".md":
        return 0
    # Templates and methodology docs are not artifacts.
    parts = rel.parts
    if len(parts) >= 2 and parts[1] in {"templates"}:
        return 0
    if len(parts) == 2 and parts[1] in {
        "dekspec-operating-guide.md",
        "dekspec-quick-reference.md",
        "architecture-frameworks-reference.md",
        "architecture.md",
        "cli-reference.md",
        "EXAMPLES.md",
        "amendment-log-types.md",
        "domain-glossary.md",
        "system-vision.md",
        "migration-advisory.json",
    } and parts[1] not in {"domain-glossary.md", "system-vision.md"}:
        # Methodology docs (not artifacts) — skip.
        return 0

    if shutil.which("dekspec") is None:
        # CLI not installed; nothing to validate against. Stay silent.
        return 0

    try:
        timeout = int(os.environ.get("DEKSPEC_HOOK_TIMEOUT", "5"))
    except ValueError:
        timeout = 5

    try:
        proc = subprocess.run(
            ["dekspec", "validate", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[dekspec] post-edit validate timed out after {timeout}s for {rel}",
            file=sys.stderr,
        )
        return 0
    except OSError as exc:
        print(f"[dekspec] post-edit validate failed: {exc}", file=sys.stderr)
        return 0

    if proc.returncode == 0:
        return 0

    # Validation failed — surface as a non-blocking advisory.
    print(
        f"[dekspec] ⚠ {rel} did not pass schema validation:\n"
        f"{proc.stderr.strip() or proc.stdout.strip()}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
