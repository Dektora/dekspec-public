"""Committed-history provenance for execution decisions (ADR-057).

Some decisions cannot be taken from the working tree alone, because the
working tree is exactly what a delivery can rewrite: whether an IB was ever
governed by the legacy policy (adoption), whether a COMPLETE status predates
the delivery (historical completion), and which execution records a delivery
touched at any point in its history (records deleted or relabelled after the
fact). These helpers read the committed history instead.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from dekspec.constraint_compiler.parser import IB_AUTHORITY_POLICIES, _extract_ib_metadata
from dekspec.execution.record import EXECUTION_DIRNAME

__all__ = [
    "authority_policy_of",
    "delivery_commits",
    "file_versions",
    "record_ids_in_history",
    "record_versions",
    "records_at",
    "status_at",
    "status_of",
]

LEGACY_TERMINAL_STATUSES = frozenset({"COMPLETED", "COMPLETE"})


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True)


def authority_policy_of(text: str) -> str:
    """The IB's declared authority policy, with the parser's rule: a missing or
    unknown declaration keeps the restrictive legacy meaning."""
    raw = (_extract_ib_metadata(text).get("Authority policy") or "").strip()
    token = raw.split()[0].strip("`*_").lower() if raw else ""
    return token if token in IB_AUTHORITY_POLICIES else "legacy"


def status_of(text: str) -> str:
    """The raw ``**Status:**`` token, retired values included (no parse gate)."""
    raw = (_extract_ib_metadata(text).get("Status") or "").strip()
    return raw.split()[0].strip("`*_").upper() if raw else ""


def file_versions(repo_root: Path, rel_path: str, *, rev: str = "HEAD") -> list[tuple[str, str, str]]:
    """Every committed version of ``rel_path`` reachable from ``rev``, newest
    first, following renames: ``(commit, path-at-commit, text)``."""
    proc = _git(repo_root, "log", "--follow", "--format=%x00%H", "--name-only", rev, "--", rel_path)
    if proc.returncode != 0:
        return []
    out: list[tuple[str, str, str]] = []
    for chunk in proc.stdout.split("\x00")[1:]:
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue  # a commit that deleted the file lists no content to read
        commit, path = lines[0].strip(), lines[-1].strip()
        show = _git(repo_root, "show", f"{commit}:{path}")
        if show.returncode == 0:
            out.append((commit, path, show.stdout))
    return out


def status_at(repo_root: Path, rev: str, rel_path: str) -> str | None:
    """The raw status of ``rel_path`` at ``rev`` (``None`` when absent)."""
    show = _git(repo_root, "show", f"{rev}:{rel_path}")
    return status_of(show.stdout) if show.returncode == 0 else None


def delivery_commits(repo_root: Path, base: str, head: str = "HEAD") -> list[str]:
    """Every commit reachable from ``head`` and not from ``base`` — both sides of
    every merge, with no path-history simplification (a path-limited `git log`
    prunes a merge side whose records the merge discarded)."""
    proc = _git(repo_root, "rev-list", f"{base}..{head}")
    return proc.stdout.split() if proc.returncode == 0 else []


def records_at(repo_root: Path, rev: str) -> set[str]:
    """Execution-record ids whose ``record.jsonl`` exists in ``rev``'s tree."""
    listed = _git(repo_root, "ls-tree", "-r", "--name-only", rev, "--", EXECUTION_DIRNAME)
    out = set()
    for path in listed.stdout.splitlines():
        parts = Path(path).parts
        if len(parts) >= 3 and parts[-1] == "record.jsonl":
            out.add(parts[-2])
    return out


def record_ids_in_history(repo_root: Path, base: str, head: str = "HEAD") -> dict[str, str]:
    """Execution-record ids present at ``base`` or in the tree of any commit of
    ``base..head`` (on either side of a merge, including a record added and
    removed again inside the range), mapped to where each was first seen."""
    seen = {rid: base for rid in records_at(repo_root, base)}
    for commit in delivery_commits(repo_root, base, head):
        for rid in records_at(repo_root, commit):
            seen.setdefault(rid, commit)
    return seen


def record_versions(repo_root: Path, rel: str, base: str, head: str = "HEAD") -> list[tuple[str, str]]:
    """Every distinct committed version of ``rel`` at ``base`` and in any commit
    of ``base..head``: ``(commit, text)``, deduplicated by blob."""
    out: list[tuple[str, str]] = []
    blobs: set[str] = set()
    for commit in [base, *delivery_commits(repo_root, base, head)]:
        blob = _git(repo_root, "rev-parse", "-q", "--verify", f"{commit}:{rel}").stdout.strip()
        if not blob or blob in blobs:
            continue
        blobs.add(blob)
        out.append((commit, _git(repo_root, "cat-file", "blob", blob).stdout))
    return out
