"""Diff-confinement evaluation for ``/write-intent --testpass``.

Given a list of ``Components affected:`` globs and a list of files changed
on an Intent branch, decide which (if any) files fall outside the declared
behavioral scope and should TESTFAIL the diff-confinement check.

Beyond the engineer-declared globs, three path prefixes are *always*
admitted because they are mutated as necessary side-effects of running the
Intent lifecycle itself — never as behavioral scope:

  * ``dekspec/**``   — spec graph (Intent file, IBs, indexes, AE backlinks).
  * ``.beads/**``    — bead-tracker housekeeping (``br claim`` / ``br close``
    emits jsonl writes).
  * ``.dekspec/**``  — consumer-side cache + lifecycle DB.

Expanding every Intent's ``Components affected:`` to declare those prefixes
would blow the size cap and add ceremony, not safety. The admit-set is the
canonical way to keep diff confinement honest without forcing every Intent
to repeat the lifecycle paths.

See ``plugins/dekspec/skills/write-intent/modes/testpass.md`` Step 2 for
the prose contract these helpers implement. Both surfaces must stay in
sync — when one changes, the other must too. (Fix lands as ds-p4tt.)
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable

__all__ = [
    "IMPLICIT_LIFECYCLE_GLOBS",
    "check_diff_confinement",
    "matches_any_glob",
]


# The three path prefixes that are mutated as lifecycle side-effects and
# therefore always admitted by diff confinement, regardless of what the
# Intent declares in ``Components affected:``. Keep in lockstep with the
# admit-set documented in modes/testpass.md.
IMPLICIT_LIFECYCLE_GLOBS: tuple[str, ...] = (
    "dekspec/**",
    ".beads/**",
    ".dekspec/**",
)


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
    """True if ``path`` matches any glob in ``globs``."""

    for glob in globs:
        if _glob_matches(path, glob):
            return True
    return False


def check_diff_confinement(
    components_affected: list[str],
    changed_files: list[str],
) -> tuple[bool, list[str]]:
    """Evaluate diff confinement for an ``/write-intent --testpass`` run.

    Parameters
    ----------
    components_affected:
        The engineer-declared glob list from the Intent's
        ``Components affected:`` field. Already resolved — any named
        components have been swapped out for their glob expansions.
    changed_files:
        Repo-relative POSIX paths from
        ``git diff --name-only $(git merge-base HEAD main) HEAD``.

    Returns
    -------
    tuple[bool, list[str]]
        ``(passed, out_of_scope)`` where:

        * ``passed`` is True iff every file matches either a glob in
          ``components_affected`` OR a glob in
          :data:`IMPLICIT_LIFECYCLE_GLOBS`.
        * ``out_of_scope`` is the list of paths that did not match either
          set, in input order. Empty when ``passed`` is True.
    """

    out_of_scope: list[str] = []
    for path in changed_files:
        if matches_any_glob(path, components_affected):
            continue
        if matches_any_glob(path, IMPLICIT_LIFECYCLE_GLOBS):
            continue
        out_of_scope.append(path)

    return (not out_of_scope, out_of_scope)
