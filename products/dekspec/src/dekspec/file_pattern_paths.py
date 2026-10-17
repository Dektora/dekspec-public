"""Resolve authored patterns without exposing repository traversal policy.

repository_paths(root) returns sorted relative POSIX paths selected by Git,
including directory aliases and submodule contents, without walking ignored
contents. Outside a work tree it lists the whole folder. resolve_pattern returns
lexical matches, optionally reusing a supplied snapshot. Selection, traversal
and cycle handling need no caller setup; empty results are normal. Git failures
raise RuntimeError naming the command and root, never masquerading as no matches.
"""
import os
import shlex
import subprocess
from pathlib import Path

from dekspec.diff_confinement import matches_any_glob


def _git(root: Path, *args: str, discover: bool = False) -> str | None:
    """Read Git output; only a definite non-work-tree permits the old walk."""
    command = ["git", "-C", str(root), *args]
    try:
        result = subprocess.run(command, capture_output=True, env={**os.environ, "LC_ALL": "C"})
    except OSError as error:
        raise RuntimeError(f"{shlex.join(command)} failed for root {root}: {error}") from error
    if result.returncode:
        detail = os.fsdecode(result.stderr).strip()
        if discover:
            if "not a git repository" in detail or "must be run in a work tree" in detail:
                return None
        raise RuntimeError(f"{shlex.join(command)} failed for root {root}: {detail}")
    return os.fsdecode(result.stdout)


def _git_children(root: Path) -> dict[Path, set[str]]:
    """Index selected children, including each populated submodule's own view."""
    output = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    children: dict[Path, set[str]] = {root: set()}
    for name in set(output.split("\0")):
        if not name:
            continue
        path = root / name
        parent = path
        while parent != root:
            children.setdefault(parent.parent, set()).add(parent.name)
            parent = parent.parent
        # Git lists gitlinks and embedded repositories as single directories.
        # Ordinary directories were derived above, never scanned on disk.
        if not path.is_symlink() and path.is_dir():
            nested = _git(path, "rev-parse", "--show-toplevel")
            if Path(nested.rstrip("\n")) == path:
                children.update(_git_children(path))
    return children


def _walk_paths(repo_root: Path) -> list[str]:
    """Keep the original traversal for roots outside a Git work tree."""
    paths = []
    for directory, folders, files in os.walk(repo_root, followlinks=True):
        parent = Path(directory)
        paths.extend((parent / name).relative_to(repo_root).as_posix() for name in folders + files)
        ancestors = {p.resolve() for p in (parent, *parent.parents)}
        folders[:] = [name for name in folders if (parent / name).resolve() not in ancestors]
    return sorted(paths)


def repository_paths(repo_root: Path) -> list[str]:
    """Snapshot Git-selected paths (or all paths outside Git), retaining aliases.

    Tracked paths remain listed even when absent on disk. Directory links retain
    their lexical names, but links back to ancestors are not expanded. Git errors
    raise RuntimeError; matching semantics are independent of enumeration.
    """
    root = repo_root.resolve()
    top = _git(root, "rev-parse", "--show-toplevel", discover=True)
    if top is None:
        return _walk_paths(repo_root)
    worktree = Path(top.rstrip("\n"))
    try:
        children = _git_children(worktree)
    except RuntimeError as error:
        raise RuntimeError(f"{error} (requested root {repo_root})") from error
    paths = []
    pending = [(root, Path(), frozenset((root, *root.parents)))]
    while pending:
        directory, prefix, ancestors = pending.pop()
        if directory.is_relative_to(worktree):
            names = children.get(directory, ())
        else:
            # Only an explicitly selected external alias permits a disk walk.
            try:
                with os.scandir(directory) as entries:
                    names = [entry.name for entry in entries]
            except OSError:
                continue
        for name in names:
            relative = prefix / name
            paths.append(relative.as_posix())
            path = directory / name
            if path in children or path.is_dir():
                target = path.resolve()
                if target not in ancestors:
                    pending.append((target, relative, ancestors | {target}))
    return sorted(paths)


def resolve_pattern(repo_root: Path, pattern: str, *, paths: list[str] | None = None) -> list[str]:
    """Resolve with the shared dialect; callers may reuse their path snapshot."""
    if paths is None:
        paths = repository_paths(repo_root)
    return [str(repo_root / path) for path in paths if matches_any_glob(path, [pattern])]
