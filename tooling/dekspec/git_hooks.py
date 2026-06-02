"""Git-hooks installer + enforcement-plane glue under MSN-002 / INT-010.

Pure-Python helpers that copy `templates/git-hooks/*.template` into a
consumer repo's `.git/hooks/` directory and verify they are present.
The hooks themselves are POSIX shell scripts that call
`dekspec session status --machine-readable` (INT-009) and gate
`git commit` / `git push` on the result.

This module owns:
- `install_hooks(target_repo, *, force=False)` — write pre-commit + pre-push
  templates into `.git/hooks/`, chmod 0o755, refuse overwrite without force.
- `uninstall_hooks(target_repo)` — remove the DekSpec-managed hook files.
- `hooks_installed(target_repo)` — True when both hooks are present + carry
  the DekSpec signature line.

NOT installed against the library's own self-spec: per CLAUDE.md
§DekSpec Guardrails, library-side commits are session-rules-governed,
not hook-enforced. Consumers opt in via `dekspec session install-hooks`
(INT-009's CLI registration; this module is the dispatch target).
"""
from __future__ import annotations

import shutil
import stat
from pathlib import Path

# Hook files this module manages. The template filename strips `.template`.
_HOOK_NAMES: tuple[str, ...] = ("pre-commit", "pre-push", "post-merge")

# Signature line written near the top of every managed hook file. Used by
# `hooks_installed()` to distinguish DekSpec-managed hooks from any
# pre-existing consumer hook that happens to share the filename.
_HOOK_SIGNATURE = "# DekSpec"

# Hook file mode — owner rwx + group/other rx (mirrors git's `core.fileMode`
# default for shell hooks). Required so `git` will execute the hook.
_HOOK_MODE = 0o755


class GitHooksError(Exception):
    """Raised on installer-side failures (missing .git/, refused clobber, etc.)."""


def _templates_dir() -> Path:
    """Resolve `templates/git-hooks/` for source-checkout AND wheel/pipx installs.

    Delegates to `vendoring.library_root()`, the canonical resolver: it prefers
    the source-checkout `templates/` and falls back to the wheel-bundled
    `_vendored/templates/`. The pre-fix `__file__`-relative path only resolved
    the source-checkout layout, so `install-hooks` was broken for every
    non-editable install (closes the ds-0qp/MSN-002 check-3 finding).
    """
    from .vendoring import library_root

    return library_root() / "templates" / "git-hooks"


def _resolve_hooks_dir(target_repo: Path) -> Path:
    """Return `<target>/.git/hooks/`, raising if `<target>/.git` is missing.

    `git worktree` checkouts have `.git` as a regular file pointing at the
    main repo's `.git/worktrees/<name>` directory; in that case we still
    install into the per-worktree `hooks/` directory (git's worktree-aware
    hook resolution will find them there).
    """
    target = target_repo.resolve()
    git_dir = target / ".git"
    if not git_dir.exists():
        raise GitHooksError(
            f"not a git repository: {target} (missing .git/)"
        )

    if git_dir.is_file():
        # Worktree: parse the `gitdir: <path>` line.
        content = git_dir.read_text(encoding="utf-8").strip()
        if not content.startswith("gitdir:"):
            raise GitHooksError(
                f"unexpected .git file shape at {git_dir}: {content!r}"
            )
        git_dir = Path(content.split(":", 1)[1].strip())
        if not git_dir.is_absolute():
            git_dir = (target / git_dir).resolve()

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    return hooks_dir


def _template_path(hook_name: str) -> Path:
    path = _templates_dir() / f"{hook_name}.template"
    if not path.is_file():
        raise GitHooksError(
            f"hook template missing from library install: {path}"
        )
    return path


def _is_dekspec_managed(hook_path: Path) -> bool:
    """True iff `hook_path` exists and its first 2KB contains the DekSpec signature."""
    if not hook_path.exists():
        return False
    try:
        head = hook_path.read_text(encoding="utf-8", errors="replace")[:2048]
    except OSError:
        return False
    return _HOOK_SIGNATURE in head


def install_hooks(target_repo: Path, *, force: bool = False) -> list[Path]:
    """Install DekSpec pre-commit + pre-push hooks into `<target_repo>/.git/hooks/`.

    Returns the list of written hook paths. Raises `GitHooksError` if any
    target hook file exists and is not DekSpec-managed and `force=False`.
    DekSpec-managed hooks are always overwritten (they are template-driven).
    """
    hooks_dir = _resolve_hooks_dir(Path(target_repo))
    written: list[Path] = []

    # Two-phase: validate every target before mutating any file. Avoids the
    # "wrote pre-commit, refused pre-push, half-installed" partial-failure case.
    for hook_name in _HOOK_NAMES:
        target = hooks_dir / hook_name
        if target.exists() and not _is_dekspec_managed(target) and not force:
            raise GitHooksError(
                f"refusing to overwrite existing non-DekSpec hook: {target}\n"
                f"  pass force=True (or --force on the CLI) to clobber."
            )

    for hook_name in _HOOK_NAMES:
        src = _template_path(hook_name)
        dst = hooks_dir / hook_name
        shutil.copyfile(src, dst)
        # `shutil.copyfile` preserves neither mode nor mtime; chmod explicitly.
        current = dst.stat().st_mode
        dst.chmod(current | _HOOK_MODE | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(dst)

    return written


def uninstall_hooks(target_repo: Path) -> list[Path]:
    """Remove DekSpec-managed hooks. Returns the list of removed paths.

    Non-DekSpec-managed hooks (no signature) are left untouched. Missing
    hooks are skipped silently.
    """
    hooks_dir = _resolve_hooks_dir(Path(target_repo))
    removed: list[Path] = []
    for hook_name in _HOOK_NAMES:
        target = hooks_dir / hook_name
        if _is_dekspec_managed(target):
            target.unlink()
            removed.append(target)
    return removed


def hooks_installed(target_repo: Path) -> bool:
    """True iff every managed hook is present + carries the DekSpec signature."""
    try:
        hooks_dir = _resolve_hooks_dir(Path(target_repo))
    except GitHooksError:
        return False
    return all(_is_dekspec_managed(hooks_dir / name) for name in _HOOK_NAMES)


__all__ = [
    "GitHooksError",
    "install_hooks",
    "uninstall_hooks",
    "hooks_installed",
]
