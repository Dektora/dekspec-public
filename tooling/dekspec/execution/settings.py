"""Execution policy settings (ADR-057 §Bounded, truthful execution).

Read from the optional ``execution:`` block of ``.dekspec/config.yaml``.
These are adaptable execution *policy* — model- and repo-dependent numbers —
not governing obligations; every value has a conservative default so a repo
with no block still gets bounded, evidence-gated execution.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ExecutionSettings", "load_settings", "load_settings_at", "resolve_python"]


@dataclass(frozen=True)
class ExecutionSettings:
    #: Attempts per IB run before the run blocks (counted across restarts).
    max_attempts: int = 3
    #: An attempt with no heartbeat for this long is closed as stalled.
    stall_minutes: int = 60
    #: Consecutive finished attempts with no new satisfied condition and no
    #: content change before the run blocks as no-progress.
    no_progress_attempts: int = 2
    #: Repository-wide integration check run by `dekspec delivery verify`.
    integration_command: str | None = None
    #: Per-command timeout for acceptance commands and test runs (seconds).
    command_timeout: int = 1800
    #: Interpreter that runs acceptance test nodes. ``None`` resolves to the
    #: project's own interpreter (see :func:`resolve_python`) — never simply
    #: dekspec's, which in a pipx install has neither pytest nor the project.
    python: str | None = None
    #: Extra globs excluded from the implementation fingerprint.
    fingerprint_exclude: tuple[str, ...] = ()
    #: Governed spec root, relative to the repo.
    spec_root: str = "dekspec"


def load_settings_at(repo_root: Path, commit: str, *, spec_root: str = "dekspec") -> ExecutionSettings:
    """Settings as they are on ``commit`` (CI reads the *base* branch's policy,
    so a delivery cannot relax its own limits, interpreter or exclusions)."""
    import subprocess

    proc = subprocess.run(["git", "show", f"{commit}:.dekspec/config.yaml"], cwd=str(repo_root),
                          capture_output=True, text=True)
    return _from_text(proc.stdout if proc.returncode == 0 else "", spec_root)


def load_settings(repo_root: Path, *, spec_root: str = "dekspec") -> ExecutionSettings:
    """Settings from `.dekspec/config.yaml` (absent file or block → defaults).

    Read leniently here — schema validation of the config is `dekspec config`'s
    job; an execution gate must not become unusable because an unrelated key
    in the same file is malformed.
    """
    cfg = Path(repo_root) / ".dekspec" / "config.yaml"
    return _from_text(cfg.read_text(encoding="utf-8") if cfg.is_file() else "", spec_root)


def _from_text(text: str, spec_root: str) -> ExecutionSettings:
    import yaml

    raw: dict = {}
    try:
        loaded = yaml.safe_load(text) or {}
        raw = (loaded.get("execution") or {}) if isinstance(loaded, dict) else {}
    except yaml.YAMLError:
        raw = {}
    defaults = ExecutionSettings(spec_root=spec_root)

    def _int(key: str, default: int) -> int:
        value = raw.get(key, default)
        return value if isinstance(value, int) and value > 0 else default

    return ExecutionSettings(
        max_attempts=_int("max_attempts", defaults.max_attempts),
        stall_minutes=_int("stall_minutes", defaults.stall_minutes),
        no_progress_attempts=_int("no_progress_attempts", defaults.no_progress_attempts),
        integration_command=raw.get("integration_command") or None,
        command_timeout=_int("command_timeout", defaults.command_timeout),
        python=raw.get("python") or None,
        fingerprint_exclude=tuple(raw.get("fingerprint_exclude") or ()),
        spec_root=spec_root,
    )


def _has_pytest(python: str, cwd: Path) -> bool:
    # Writes no bytecode: the candidate may be the repository's own `.venv`,
    # and resolving the interpreter is part of an acceptance run (IB-145 O-4).
    try:
        return subprocess.run([python, "-c", "import pytest"], cwd=str(cwd), capture_output=True,
                              timeout=60, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@functools.lru_cache(maxsize=32)
def _auto_python(repo_root: str) -> str:
    root = Path(repo_root)
    venv = (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    candidates = [venv] if (root / venv).exists() else []
    candidates += [c for c in (shutil.which("python3"), shutil.which("python")) if c]
    candidates.append(sys.executable)
    for candidate in dict.fromkeys(candidates):
        if _has_pytest(candidate, root):
            return candidate
    return candidates[0]


def resolve_python(repo_root: Path, configured: str | None) -> str:
    """The interpreter that runs pytest acceptance nodes.

    ``execution.python`` wins when set. Otherwise the first of the repo's
    ``.venv``, ``python3``/``python`` on PATH, and dekspec's own interpreter
    that can import pytest — the project's test environment, which is rarely
    the one dekspec itself is installed in.
    """
    return configured or _auto_python(str(Path(repo_root).resolve()))
