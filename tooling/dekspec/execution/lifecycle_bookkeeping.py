"""The narrow ADR-073 exception to protection, shared by all diff judges.

This deliberately does not use fingerprint normalization: that also discards
Modified dates and existing amendment rows, which protection must preserve.
"""

from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from dekspec.constraint_compiler.parser import (
    _extract_ib_intent, _extract_ib_metadata, _extract_ib_parent,
)
from dekspec.execution.artifact_edit import _H2_STATUS, _META_STATUS, append_amendment_row
from dekspec.execution.record import is_record_file
from dekspec.execution.references import AmbiguousReference, artifact_path

if TYPE_CHECKING:
    from dekspec.execution.contract import IBContract
    from dekspec.execution.scope import Change


_TRANSITIONS = {("DRAFT", "PROPOSED"), ("PROPOSED", "ACCEPTED"),
                ("ACCEPTED", "COMPLETE"), ("COMPLETE", "ACCEPTED")}


def _git_bytes(repo_root: Path, *args: str) -> bytes | None:
    """Unavailable comparison data grants no bookkeeping exemption."""
    try:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True)
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _text(repo_root: Path, path: str, revision: str | None) -> str | None:
    try:
        if revision is not None:
            data = _git_bytes(repo_root, "show", f"{revision}:{path}")
        else:
            current = repo_root / path
            data = None if current.is_symlink() else current.read_bytes()
        return None if data is None else data.decode("utf-8")
    except (OSError, UnicodeError):
        return None


def bookkeeping_paths(repo_root: Path, contracts: Iterable[IBContract], base: str, *,
                      spec_root: str = "dekspec", staged: bool = False, end: str | None = None) -> set[str]:
    """Exact brief paths and unambiguous, unchanged parent-Intent bindings.

    A changed parent declaration cannot expand the exemption. Compare the
    same sides as protection: delivery base/worktree or HEAD/index.
    """
    paths = set()
    for contract in contracts:
        paths.add(contract.rel_path)
        if not contract.parent or not contract.parent.startswith("INT-"):
            continue
        before = _text(repo_root, contract.rel_path, base)
        after = _text(repo_root, contract.rel_path, "" if staged else end)
        if before is None or after is None:
            continue
        old, new = _extract_ib_metadata(before), _extract_ib_metadata(after)
        parent_ref = _extract_ib_parent(old) or _extract_ib_intent(old) or {}
        if (parent_ref.get("id") != contract.parent
                or any(old.get(key) != new.get(key) for key in ("Parent", "Intent", "Spec"))):
            continue
        try:
            parent = artifact_path(repo_root, contract.parent, spec_root=spec_root)
        except AmbiguousReference:
            continue
        if parent is not None:
            paths.add(parent.relative_to(repo_root).as_posix())
    return paths


def _same_mode(repo_root: Path, path: str, base: str, staged: bool, end: str | None = None) -> bool:
    before = _git_bytes(repo_root, "ls-tree", "--format=%(objectmode)", base, "--", f":(literal){path}")
    if before is None or before.strip() not in {b"100644", b"100755"}:
        return False
    if end == "":
        staged = True
    elif end is not None:
        return before == _git_bytes(repo_root, "ls-tree", "--format=%(objectmode)", end, "--", f":(literal){path}")
    if staged:
        entries = _git_bytes(repo_root, "ls-files", "--stage", "-z", "--", f":(literal){path}")
        if entries is None:
            return False
        rows = entries.rstrip(b"\0").split(b"\0")
        if len(rows) != 1:
            return False
        fields = rows[0].split(b"\t", 1)[0].split()
        return len(fields) == 3 and fields[2] == b"0" and fields[0] == before.strip()
    try:
        mode = (repo_root / path).lstat().st_mode
    except OSError:
        return False
    current = b"100755" if mode & stat.S_IXUSR else b"100644"
    return stat.S_ISREG(mode) and current == before.strip()


def _amendment_rows(text: str) -> list[str]:
    lines = text.rstrip("\n").split("\n")
    start = next((i for i, line in enumerate(lines)
                  if re.match(r"^## Amendment Log\s*$", line)), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return [line for line in lines[start:end] if line.startswith("|")]


def is_protection_bookkeeping(repo_root: Path, change: Change, covered: set[str],
                              base: str, *, staged: bool = False, end: str | None = None) -> bool:
    """Whether this entire change may bypass protected-surface matching.

    Read base/worktree, or HEAD/index for a commit guard. Reconstruct the new
    markdown with the writer itself: this preserves every other byte and
    handles absent tables/sections exactly as the engine does. No author or
    lifecycle authority is inferred from the permitted content.
    """
    if change.old_path is not None or change.status not in {"A", "M"}:
        return False
    if is_record_file(change.path):
        return True
    if change.status != "M" or change.path not in covered:
        return False
    if not _same_mode(repo_root, change.path, base, staged, end):
        return False
    old = _text(repo_root, change.path, base)
    new = _text(repo_root, change.path, "" if staged else end)
    if old is None or new is None:
        return False

    old_status = _META_STATUS.search(old) or _H2_STATUS.search(old)
    new_status = _META_STATUS.search(new) or _H2_STATUS.search(new)
    if old_status is not None and new_status is not None:
        previous, following = old_status.group(2), new_status.group(2)
        if previous != following:
            if (previous.strip("`*_").upper(), following) not in _TRANSITIONS:
                return False
            old = old[:old_status.start(2)] + following + old[old_status.end(2):]

    previous_rows, following_rows = _amendment_rows(old), _amendment_rows(new)
    if following_rows[:len(previous_rows)] != previous_rows:
        return False
    added = following_rows[len(previous_rows):]
    if not previous_rows and added:
        # The writer supplies the header and separator when it creates a table.
        added = added[2:]
    for row in added:
        old = append_amendment_row(old, row)
    return old == new
