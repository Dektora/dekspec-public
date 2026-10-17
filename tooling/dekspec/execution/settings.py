"""Hides optional configuration; ExecutionSettings gains lean: bool=False;
load_settings(root) and load_settings_at(root, commit) keep existing signatures.
Absent, false and non-boolean switch values mean off; callers never parse YAML
or choose a fallback, and base reads never inherit the working tree switch.
Alternatives: a separate feature-flag service; caller YAML; existing settings.
Existing settings wins because all execution policy already travels as one value.
The settings loader supplies the value; only contract_problems combines it with
the brief policy. Exposing the raw setting does not make callers policy judges.
IB-294 surface extension (designed before tests): ExecutionSettings.vitest_install
is an optional checkout installation command; None/empty means lockfile defaults.
The existing loaders hide YAML and base-revision selection; callers never parse
settings or choose a package manager. Preparation faults stay distinct from tests.
Alternatives: caller install steps or a new settings service; the existing settings
value wins because policy already travels with it. The loaders supply the command; the runner prepares the checkout.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from dekspec.execution import git_reads

__all__ = ["ExecutionSettings", "load_settings", "load_settings_at", "resolve_python"]


@dataclass(frozen=True)
class ExecutionSettings:
    lean: bool = False
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
    #: The configuration file vitest's tests run under, repository-relative.
    #: ``None`` means vitest's default lookup from the project root.
    vitest_config: str | None = None
    #: Extra globs excluded from the implementation fingerprint.
    fingerprint_exclude: tuple[str, ...] = ()
    #: Governed spec root, relative to the repo.
    spec_root: str = "dekspec"
    #: Optional command for a clean vitest checkout.
    #: None/empty selects the commit's lockfile; no install behavior here.
    vitest_install: str | None = None


def load_settings_at(repo_root: Path, commit: str, *, spec_root: str = "dekspec") -> ExecutionSettings:
    """Settings as they are on ``commit`` (CI reads the *base* branch's policy,
    so a delivery cannot relax its own limits, interpreter or exclusions)."""
    return _from_text(_config_text_at(repo_root, commit), spec_root)


def _config_text_at(repo_root: Path, commit: str) -> str:
    """Read immutable project configuration; absent configuration means defaults."""
    proc = git_reads.run(str(repo_root), "show", f"{commit}:.dekspec/config.yaml", capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""


def _worktree_setup_at(repo_root: Path, commit: str) -> str | None:
    """The base-owned checkout setup, without adding to the execution facade."""
    import yaml

    try:
        config = yaml.safe_load(_config_text_at(repo_root, commit))
    except yaml.YAMLError:
        return None
    integration = config.get("integration") if isinstance(config, dict) else None
    command = integration.get("worktree_setup") if isinstance(integration, dict) else None
    return command if isinstance(command, str) and command.strip() else None


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
        lean=raw.get("lean") is True,
        max_attempts=_int("max_attempts", defaults.max_attempts),
        stall_minutes=_int("stall_minutes", defaults.stall_minutes),
        no_progress_attempts=_int("no_progress_attempts", defaults.no_progress_attempts),
        integration_command=raw.get("integration_command") or None,
        command_timeout=_int("command_timeout", defaults.command_timeout),
        python=raw.get("python") or None,
        vitest_config=raw.get("vitest_config") if isinstance(raw.get("vitest_config"), str)
        and raw["vitest_config"].strip() else None,
        vitest_install=raw.get("vitest_install") if isinstance(raw.get("vitest_install"), str)
        and raw["vitest_install"].strip() else None,
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
    candidates = [str(root / venv)] if (root / venv).exists() else []
    candidates += [c for c in (shutil.which("python3"), shutil.which("python")) if c]
    candidates.append(sys.executable)
    for candidate in dict.fromkeys(candidates):
        if _has_pytest(candidate, root):
            return candidate
    return candidates[0]


def resolve_python(repo_root: Path, configured: str | None) -> str:
    """The interpreter that runs pytest acceptance nodes.

    Configured absolute paths stay unchanged; relative paths use the resolved
    repository root without following executable links. Bare names search PATH
    with the repository's venv first; an absent name yields an unusable absolute
    repository path so the acceptance gate can name it. Historical record values
    use this same rule when compared.

    ``execution.python`` wins when set. Otherwise the first of the repo's
    ``.venv``, ``python3``/``python`` on PATH, and dekspec's own interpreter
    that can import pytest — the project's test environment, which is rarely
    the one dekspec itself is installed in.
    """
    root = Path(repo_root).resolve()
    configured = configured or _auto_python(str(root))
    candidate = Path(configured).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    if os.sep in configured or (os.altsep and os.altsep in configured):
        return str((root / candidate).absolute())
    bin_dir = root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    search_path = str(bin_dir) + os.pathsep + os.environ.get("PATH", os.defpath)
    found = shutil.which(str(candidate), path=search_path)
    return str(Path(found).absolute() if found else root / candidate)
