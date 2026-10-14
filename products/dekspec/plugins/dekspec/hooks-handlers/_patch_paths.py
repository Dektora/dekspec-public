"""Read Codex patch paths without interpreting or executing patch contents."""
from __future__ import annotations

from pathlib import Path


def patch_paths(payload: dict) -> list[Path]:
    """Return every touched path, including both move ends, relative to cwd.

    Unreadable payloads have no paths. Scan headers rather than patch hunks so
    a shell heredoc wrapper is harmless. Codex accepts padded file headers;
    strip leading whitespace before matching. An indented context line may
    also match, conservatively guarding that path. Preserve order and validate
    each unique path once.
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    command = tool_input.get("command")
    if not isinstance(command, str):
        return []
    cwd = payload.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        return []
    base = Path(cwd) if cwd else Path.cwd()
    prefixes = ("*** Add File:", "*** Update File:", "*** Delete File:", "*** Move to:")
    paths = []
    for line in command.splitlines():
        line = line.lstrip()
        for prefix in prefixes:
            if line.startswith(prefix):
                name = line[len(prefix):].strip()
                if name and "\x00" not in name:
                    path = base / name
                    if path not in paths:
                        paths.append(path)
                break
    return paths
