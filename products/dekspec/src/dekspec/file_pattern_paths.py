"""Resolve authored patterns against existing repository paths."""
import os
from pathlib import Path

from dekspec.diff_confinement import matches_any_glob


def repository_paths(repo_root: Path) -> list[str]:
    """Snapshot lexical paths, including dot files and linked directories.

    Keep aliases: an authored path may name a linked directory. Prune only
    links back to an ancestor, so a directory cycle cannot make resolution
    infinite. There is no second pattern interpretation in enumeration.
    """
    paths = []
    for directory, folders, files in os.walk(repo_root, followlinks=True):
        parent = Path(directory)
        paths.extend((parent / name).relative_to(repo_root).as_posix() for name in folders + files)
        ancestors = {p.resolve() for p in (parent, *parent.parents)}
        folders[:] = [name for name in folders if (parent / name).resolve() not in ancestors]
    return sorted(paths)


def resolve_pattern(repo_root: Path, pattern: str, *, paths: list[str] | None = None) -> list[str]:
    """Resolve with the shared dialect; callers may reuse their path snapshot."""
    if paths is None:
        paths = repository_paths(repo_root)
    return [str(repo_root / path) for path in paths if matches_any_glob(path, [pattern])]
