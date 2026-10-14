"""Frozen readings from the IB-176 base; independent of the live callers.

The function bodies below are verbatim base copies. Keep these historical
semantics when the live matchers are removed in IB-177.
"""

from __future__ import annotations

from functools import lru_cache

import fnmatch
import re
from collections.abc import Iterable

from dekspec.glob_braces import expand_braces

LEGACY_READINGS = ("brief", "components", "archeology-exclude")


def validate_reading(reading: str) -> None:
    if reading not in LEGACY_READINGS:
        raise ValueError(f"Unknown reading {reading!r}; accepted readings: {', '.join(LEGACY_READINGS)}")


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


@lru_cache(maxsize=2048)
def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a path glob to an anchored regex.

    ``**/`` matches zero or more leading path segments; ``**`` matches any
    run of characters including ``/``; ``*`` matches within a single
    segment (no ``/``); ``?`` matches one non-``/`` char. Everything else is
    literal. Exact-match discipline per MSN-009 — no fuzzy tolerance.
    """
    out: list[str] = []
    i, n = 0, len(glob)
    while i < n:
        if glob[i] == "*":
            if glob[i : i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
            elif glob[i : i + 2] == "**":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")

def _path_matches_glob(path: str, glob: str) -> bool:
    """True iff ``path`` matches ``glob`` exactly (literal or glob match)."""
    path = path.strip()
    glob = glob.strip()
    if not path or not glob:
        return False
    if path == glob:
        return True
    return _glob_to_regex(glob).match(path) is not None


def _is_excluded(rel_path: str, excludes: list[str]) -> bool:
    """True if `rel_path` (a POSIX repo-relative path) matches an exclude glob.

    A directory-shaped glob (one ending in `/`) excludes everything under
    that directory. A `**`-bearing glob is matched with `fnmatch`, which
    treats `**` like `*` — adequate for the coarse exclude surfaces here.
    """
    posix = rel_path.replace("\\", "/")
    parts = posix.split("/")
    for raw in excludes:
        glob = raw.replace("\\", "/")
        if glob.endswith("/"):
            # Directory prefix: exclude any path with that dir as a segment.
            dir_glob = glob.rstrip("/")
            # Strip a leading **/ so "foo" matches at any depth.
            bare = dir_glob[3:] if dir_glob.startswith("**/") else dir_glob
            # Match a path segment either exactly or by glob (e.g. `*.egg-info`).
            if bare and (
                bare in parts or any(fnmatch.fnmatch(seg, bare) for seg in parts)
            ):
                return True
            if posix == dir_glob or posix.startswith(dir_glob + "/"):
                return True
            continue
        if fnmatch.fnmatch(posix, glob):
            return True
        # A leading **/ should also match files at depth zero.
        if glob.startswith("**/") and fnmatch.fnmatch(posix, glob[3:]):
            return True
    return False


def legacy_matches(reading: str, path: str, pattern: str) -> bool:
    """Evaluate a frozen reading, including its original normalization quirks."""
    validate_reading(reading)
    if reading == "brief":
        return matches_any_glob(path, [pattern])
    if reading == "components":
        return _path_matches_glob(path, pattern)
    return _is_excluded(path, [pattern])


def resolve_legacy(root, pattern, *, braces=False):
    """Old resolve-only reader, exclusively for migration reports."""
    import glob
    patterns = expand_braces(pattern) if braces else [pattern]
    return any(glob.glob(str(root / p), recursive=True) for p in patterns)
