"""Path-glob matching shared by the scope checks.

Originally the Intent-level diff-confinement evaluator for
``/write-intent --testpass`` (with an implicit admit-set of ``dekspec/**``,
``.beads/**`` and ``.dekspec/**``). ADR-056/057 retired that path: scope is now
the IB's, evaluated with protected-surface precedence and explicit lifecycle
exemptions by :mod:`dekspec.execution.scope`. What remains here is the glob
matcher that evaluation (and the plan, guard and audit code) shares, so every
surface agrees on what a glob admits — including brace groups (ds-059n).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable

from dekspec.glob_braces import expand_braces

__all__ = ["matches_any_glob"]


def _glob_matches(path: str, glob: str) -> bool:
    """Return True if ``path`` matches ``glob`` under the project's globstar
    semantics.

    Mirrors the convention already in use across the codebase (see
    ``tooling/dekspec/archeology/coverage.py``): we drive ``fnmatch.fnmatch``
    directly, then add two fallbacks to extend its limited ``**`` handling:

      1. A ``prefix/**`` glob admits any path under ``prefix/`` (the practical
         "everything below this directory" semantics the bead body asks for).
      2. A leading ``**/`` is stripped so the bare suffix matches files at
         depth zero too.

    POSIX path separators only — callers are expected to pass repo-relative
    paths with forward slashes.
    """

    posix_path = path.replace("\\", "/")
    posix_glob = glob.replace("\\", "/")

    # 1. Plain fnmatch first. Handles e.g. ``services/**/*.py`` reasonably
    #    well because fnmatch treats ``**`` as ``*`` (matches anything that
    #    does not span a slash boundary in glob spec — but fnmatch does
    #    permit slashes, so this is the loosest possible match).
    if fnmatch.fnmatchcase(posix_path, posix_glob):
        return True

    # 2. Directory-prefix glob: ``foo/**`` admits anything under ``foo/``.
    if posix_glob.endswith("/**"):
        prefix = posix_glob[: -len("/**")]
        if prefix and (posix_path == prefix or posix_path.startswith(prefix + "/")):
            return True

    # 3. Leading ``**/`` should also match at depth zero.
    if posix_glob.startswith("**/") and fnmatch.fnmatchcase(posix_path, posix_glob[3:]):
        return True

    # 4. A ``**`` in the middle of the glob should permit any depth.
    if "**" in posix_glob:
        collapsed = posix_glob.replace("**/", "")
        if collapsed != posix_glob and fnmatch.fnmatchcase(posix_path, collapsed):
            return True

    return False


def matches_any_glob(path: str, globs: Iterable[str]) -> bool:
    """True if ``path`` matches any glob in ``globs``.

    Shell-style brace groups ``{a,b}`` are expanded before matching so this
    gate agrees with the L7b component-resolve audit, which also expands
    them (ds-059n) — both go through :func:`dekspec.glob_braces.expand_braces`.
    """

    for glob in globs:
        for expanded in expand_braces(glob):
            if _glob_matches(path, expanded):
                return True
    return False
