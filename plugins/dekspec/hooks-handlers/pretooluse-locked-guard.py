#!/usr/bin/env python3
"""DekSpec PreToolUse LOCKED-artifact write guard (ds-k24i).

Fires on PreToolUse for Edit|Write|MultiEdit. BLOCKS the tool call when the
target is a `LOCKED` DekSpec artifact under `<cwd>/dekspec/`. LOCKED immutability
is otherwise honor-system (a post-edit audit fires only AFTER the fact and never
blocks); this hook mechanically refuses the write at tool-call time.

Exemptions — the legitimate authoring paths stay unblocked:
  * Status transitions (`--lock` / `--unlock` / `--accept` / `approve` /
    editorial-amend) run via `artifact_ops.py` in a Bash subprocess — they do
    NOT use the Edit/Write TOOL, so this hook never fires on them. The canonical
    change flow is `--unlock` (LOCKED -> PROPOSED) -> edit while PROPOSED ->
    `--lock`; the edits land while the artifact is NOT LOCKED.
  * A skill that must edit a LOCKED artifact's body via the Edit tool (e.g.
    `/write-intent --sync` post-merge checklist cleanup) drops a marker file
    `dekspec/.dekspec-locked-write-allow` for the duration of its edits; this
    hook honors a FRESH marker and allows the write. The marker is staleness-
    guarded (see MARKER_TTL_SECONDS) so a leaked marker cannot permanently
    disable the guard.

Environment overrides:
    DEKSPEC_HOOK_DISABLE=1   Skip the guard entirely.

Block contract: exit code 2 + a stderr reason. A PreToolUse hook exiting 2
blocks the tool call and surfaces stderr to the agent.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

MARKER = "dekspec/.dekspec-locked-write-allow"
# A marker older than this is treated as stale (leaked by a crashed skill) and
# ignored, so the guard re-engages rather than staying silently disabled.
MARKER_TTL_SECONDS = 300

# Top-level dekspec/ files that are methodology docs, NOT LOCKable artifacts.
_NON_ARTIFACT_TOP_LEVEL = {
    "dekspec-operating-guide.md",
    "dekspec-quick-reference.md",
    "architecture-frameworks-reference.md",
    "architecture.md",
    "cli-reference.md",
    "EXAMPLES.md",
    "amendment-log-types.md",
    "migration-advisory.json",
}


def _status(path: Path) -> str | None:
    """Return the artifact's declared Status (first non-empty line under the
    ``## Status`` heading), or None if unreadable / no status section."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == "## status":
            for nxt in lines[i + 1 :]:
                stripped = nxt.strip()
                if stripped:
                    return stripped
            return None
    return None


def _fresh_marker(cwd: Path) -> bool:
    """True if the authoring-skill exemption marker exists and is fresh."""
    marker = cwd / MARKER
    try:
        age = time.time() - marker.stat().st_mtime
    except OSError:
        return False
    return age <= MARKER_TTL_SECONDS


def main() -> int:
    if os.environ.get("DEKSPEC_HOOK_DISABLE") == "1":
        return 0

    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        # Bad input — never block on a parse failure.
        return 0

    if payload.get("tool_name") not in {"Edit", "Write", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    path = Path(file_path)
    cwd = Path.cwd().resolve()
    try:
        rel = path.resolve().relative_to(cwd)
    except (ValueError, OSError):
        return 0

    rel_str = str(rel).replace("\\", "/")
    # Only artifacts under dekspec/, *.md, excluding templates + methodology docs.
    if not rel_str.startswith("dekspec/"):
        return 0
    if path.suffix.lower() != ".md":
        return 0
    parts = rel.parts
    if len(parts) >= 2 and parts[1] == "templates":
        return 0
    if len(parts) == 2 and parts[1] in _NON_ARTIFACT_TOP_LEVEL:
        return 0

    # Only block a write to an artifact that is CURRENTLY locked.
    if _status(path.resolve()) != "LOCKED":
        return 0

    # Authoring-skill exemption (fresh marker) — e.g. /write-intent --sync.
    if _fresh_marker(cwd):
        return 0

    print(
        f"[dekspec] BLOCKED: {rel_str} is LOCKED — a direct Edit/Write to a "
        f"LOCKED artifact is refused (immutability, ds-k24i).\n"
        f"  To change it: run the artifact's authoring skill with --unlock "
        f"(e.g. /write-intent --unlock <path>), edit it while PROPOSED, then "
        f"--lock. Post-merge tail edits go through --sync (which is exempt).\n"
        f"  Status transitions already bypass this guard (they run via "
        f"artifact_ops, not the Edit tool). Emergency override: "
        f"DEKSPEC_HOOK_DISABLE=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
