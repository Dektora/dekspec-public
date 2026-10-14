"""Implementation fingerprint — what content a piece of evidence was about.

Evidence and review verdicts are bound to the *content* they examined, not to
a branch name or an artifact status. A commit SHA alone is the wrong key:
recording evidence would itself create a new commit, a squash merge produces
a new SHA over identical content, and an uncommitted change can make "the
same SHA" mean different files.

The fingerprint is derived from a **content manifest** — one entry per path
of the repository's working content (tracked plus untracked-but-not-ignored
files). Each entry hashes the entry's kind (file or symlink), its executable
bit, and its content (a symlink's content is its target), so re-pointing a
link or flipping a mode is a change. The manifest is stored with each verdict
(:func:`dekspec.execution.snapshots`), which is what lets a later check name
exactly which paths changed since a review — independent of git history,
spaces or encodings in paths, or uncommitted work.

Exactly five normalisations, each because the change carries no behavior and
would otherwise make completion impossible to record:

* Execution record files and their snapshots are excluded — recording
  evidence must not invalidate the evidence it records. Stray files count.
* Tracker record files are excluded by :func:`is_tracker_record`, shared
  with the scope lifecycle check. Other files in tracker folders count.
* Untracked interpreter/tool caches (``__pycache__/``, ``.pytest_cache/`` …)
  are excluded — running the checks creates them. Tracked files are never
  excluded, and acceptance runs point bytecode caches outside the repository.
* Generated spec indexes (``<spec_root>/*-index.md``) are excluded — they are
  regenerated from the artifacts, which are themselves fingerprinted.
* In governed markdown under the spec root, lifecycle bookkeeping
  (``## Status`` / ``**Status:**``, ``## Modified``, ``## Amendment Log``) is
  dropped, so flipping an IB to COMPLETE does not stale its own evidence.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

from dekspec.diff_confinement import matches_any_glob
from dekspec.execution.record import EXECUTION_DIRNAME

__all__ = [
    "FingerprintError",
    "content_manifest",
    "current_commit",
    "fingerprint_of",
    "implementation_fingerprint",
    "is_tracker_record",
    "manifest_changes",
    "named_entries",
    "normalize_governed_markdown",
    "worktree_dirty",
]

_VOLATILE_SECTIONS = {"status", "modified", "amendment log"}
_H2 = re.compile(r"^##\s+(.+?)\s*$")
_STATUS_META = re.compile(r"^\*\*Status:\*\*.*$")
_CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_TRACKER_SUFFIXES = {"jsonl", "json", "yaml", "yml", "toml", "md", "db", "gitignore", "lock"}


def is_tracker_record(path: str) -> bool:
    """Whether a repository-relative path is a lifecycle `br` tracker record."""
    return (path.split("/", 1)[0] in (".beads", ".beads-issues", ".beads-dekspec")
            and path.rsplit(".", 1)[-1] in _TRACKER_SUFFIXES)


class FingerprintError(RuntimeError):
    """The repository could not be read (not a git work tree, git missing)."""


def _git(repo_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args], cwd=str(repo_root),
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as exc:  # pragma: no cover - git absent
        raise FingerprintError("git is not installed") from exc
    if proc.returncode != 0:
        raise FingerprintError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def normalize_governed_markdown(text: str) -> str:
    """Drop lifecycle bookkeeping from a governed artifact (see module doc)."""
    out: list[str] = []
    skipping = False
    for line in text.splitlines():
        heading = _H2.match(line)
        if heading:
            skipping = heading.group(1).strip().lower() in _VOLATILE_SECTIONS
            if skipping:
                continue
        if skipping:
            continue
        if _STATUS_META.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def _is_cache(path: str) -> bool:
    return any(part in _CACHE_DIRS for part in path.split("/"))


def _is_index(path: str, spec_root: str) -> bool:
    return path.startswith(spec_root + "/") and "/" not in path[len(spec_root) + 1 :] and path.endswith(
        "-index.md"
    )


def _entry(repo_root: Path, rel: str, spec_root: str) -> str | None:
    path = repo_root / rel
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None  # tracked but deleted in the work tree
    if stat.S_ISLNK(st.st_mode):
        kind, content = b"l", os.readlink(path).encode("utf-8", "surrogateescape")
    elif stat.S_ISREG(st.st_mode):
        kind, content = b"f", path.read_bytes()
        if rel.startswith(spec_root + "/") and rel.endswith(".md"):
            content = normalize_governed_markdown(content.decode("utf-8", errors="replace")).encode("utf-8")
    else:
        return None
    executable = b"x" if st.st_mode & stat.S_IXUSR else b"-"
    return hashlib.sha256(kind + executable + b"\0" + content).hexdigest()


def content_manifest(
    repo_root: Path,
    *,
    spec_root: str = "dekspec",
    extra_excludes: tuple[str, ...] = (),
) -> dict[str, str]:
    """``{repo-relative path: entry hash}`` over the fingerprinted content."""
    repo_root = Path(repo_root)
    tracked = {p for p in _git(repo_root, "ls-files", "-z", "--cached").split("\0") if p}
    untracked = {p for p in _git(repo_root, "ls-files", "-z", "--others", "--exclude-standard").split("\0") if p}
    from dekspec.execution.record import is_record_file

    excludes = tuple(extra_excludes)
    manifest: dict[str, str] = {}
    for rel in sorted(tracked | untracked):
        # Only the records themselves are excluded: anything else placed under the
        # execution directory is content, bound by evidence like any other file.
        if (is_record_file(rel) or is_tracker_record(rel)
                or matches_any_glob(rel, excludes) or _is_index(rel, spec_root)):
            continue
        if rel not in tracked and _is_cache(rel):
            continue
        entry = _entry(repo_root, rel, spec_root)
        if entry is not None:
            manifest[rel] = entry
    return manifest


def fingerprint_of(manifest: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(manifest):
        digest.update(rel.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(manifest[rel]))
    return digest.hexdigest()


def implementation_fingerprint(
    repo_root: Path,
    *,
    spec_root: str = "dekspec",
    extra_excludes: tuple[str, ...] = (),
) -> str:
    return fingerprint_of(content_manifest(repo_root, spec_root=spec_root, extra_excludes=extra_excludes))


def manifest_changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Paths added, removed or changed between two manifests."""
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


def current_commit(repo_root: Path) -> str | None:
    try:
        return _git(Path(repo_root), "rev-parse", "HEAD").strip() or None
    except FingerprintError:
        return None


def worktree_dirty(repo_root: Path) -> bool:
    """True when anything outside the execution records is uncommitted."""
    status = _git(Path(repo_root), "status", "--porcelain", "-z", "--untracked-files=normal")
    for entry in (e for e in status.split("\0") if e):
        path = entry[3:]
        if not path.startswith(EXECUTION_DIRNAME + "/"):
            return True
    return False


def named_entries(repo_root, paths, *, spec_root="dekspec", head=None):
    """Entry hashes for named repository paths, omitting absent files.

    Read working files by default, or immutable git objects at ``head``.
    File kind, executable mode and governed markdown use the manifest rule.
    An unreadable revision or content raises FingerprintError; no files change.
    """
    root = Path(repo_root)
    wanted = set(paths)
    try:
        if head is None:
            return {rel: entry for rel in sorted(wanted)
                    if (entry := _entry(root, rel, spec_root)) is not None}
        commit = _git(root, "rev-parse", "--verify", "--end-of-options", f"{head}^{{commit}}").strip()
        entries = {}
        for row in _git(root, "ls-tree", "-r", "-z", commit).split("\0"):
            if not row:
                continue
            metadata, rel = row.split("\t", 1)
            mode, kind, oid = metadata.split()
            if rel not in wanted or kind != "blob":
                continue
            proc = subprocess.run(["git", "cat-file", "blob", oid], cwd=root, capture_output=True)
            if proc.returncode:
                raise FingerprintError(f"cannot read {rel} at {commit}: {proc.stderr.decode(errors='replace')}")
            content = proc.stdout
            link = mode == "120000"
            if not link and rel.startswith(spec_root + "/") and rel.endswith(".md"):
                content = normalize_governed_markdown(content.decode("utf-8", errors="replace")).encode("utf-8")
            executable = b"x" if link or int(mode, 8) & stat.S_IXUSR else b"-"
            entries[rel] = hashlib.sha256((b"l" if link else b"f") + executable + b"\0" + content).hexdigest()
        return dict(sorted(entries.items()))
    except OSError as exc:
        raise FingerprintError(f"cannot read named entries: {exc}") from exc
