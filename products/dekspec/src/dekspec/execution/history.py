"""Committed-history provenance for execution decisions (ADR-057).

Some decisions cannot be taken from the working tree alone, because the
working tree is exactly what a delivery can rewrite: whether an IB was ever
governed by the legacy policy (adoption), whether a COMPLETE status predates
the delivery (historical completion), and which execution records a delivery
touched at any point in its history (records deleted or relabelled after the
fact). These helpers read the committed history instead.
"""

from __future__ import annotations

import locale
import re
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


class _BatchUnavailable(RuntimeError):
    """The batch reader stopped or answered in an unexpected form (for example a
    Git older than 2.38, which lacks ``cat-file --batch -z``). Callers fall back
    to one Git call per lookup; a failed reader must never read as "no history"."""


class _BatchObjects:
    """One streaming cat-file process, shared across tree/blob lookups.

    Requests are flushed and consumed one at a time so neither pipe can fill
    while the other end is blocked. Content lengths are bytes, not characters.
    """

    def __init__(self, repo_root: Path, *, env=None):
        self.process = subprocess.Popen(
            ["git", "cat-file", "--batch", "-z"], cwd=str(repo_root),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
        )
        self.objects: dict[str, tuple[str, str, bytes] | None] = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.process.stdin.close()
        except BrokenPipeError:
            pass
        self.process.stdout.close()
        self.process.wait()

    def get(self, expression: str) -> tuple[str, str, bytes] | None:
        if "\0" in expression:
            raise ValueError("embedded null byte")
        if expression in self.objects:
            return self.objects[expression]
        try:
            self.process.stdin.write(expression.encode("utf-8") + b"\0")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise _BatchUnavailable("cat-file reader stopped") from error
        header = self.process.stdout.readline().rstrip(b"\n")
        if not header:
            raise _BatchUnavailable("cat-file reader returned no answer")
        missing = tuple(expression.encode("utf-8") + suffix for suffix in (b" missing", b" ambiguous"))
        # A missing expression may itself contain newlines (Git paths can).
        while (header and header not in missing
               and not re.fullmatch(rb"[0-9a-f]+ (?:(?:blob|tree|commit|tag) [0-9]+|submodule|missing)", header)):
            if not expression.encode("utf-8").startswith(header + b"\n"):
                raise _BatchUnavailable("unexpected cat-file answer")
            line = self.process.stdout.readline()
            if not line:
                raise _BatchUnavailable("cat-file reader stopped mid-answer")
            header += b"\n" + line.rstrip(b"\n")
        absent_entry = re.fullmatch(rb"([0-9a-f]{40}|[0-9a-f]{64}) (?:submodule|missing)", header)
        if absent_entry:
            return (absent_entry[1].decode("ascii"), "missing", b"")
        if header in missing:
            return None
        oid, kind, size = header.rsplit(b" ", 2)
        content = self.process.stdout.read(int(size))
        if len(content) != int(size) or self.process.stdout.read(1) != b"\n":  # trailing newline
            raise _BatchUnavailable("cat-file reader stopped mid-object")
        result = (oid.decode("ascii"), kind.decode("ascii"), content)
        self.objects[expression] = result
        return result

    def missing_path(self, commit: str, path: str):
        """A tree entry can name an unavailable object (notably a gitlink).

        rev-parse still returns its id, while cat-file blob yields no text.
        Preserve that distinction from a path which has no tree entry at all.
        """
        tree = self.get(f"{commit}^{{tree}}")
        for part in path.split("/"):
            if tree is None or tree[1] != "tree":
                return None
            oid, _, raw = tree
            width, offset, found = len(oid) // 2, 0, None
            while offset < len(raw):
                end = raw.index(b"\0", offset)
                _, name = raw[offset:end].split(b" ", 1)
                child = raw[end + 1:end + 1 + width].hex()
                offset = end + 1 + width
                if name == part.encode("utf-8"):
                    found = child
                    break
            if found is None:
                return None
            tree = self.get(found)
        return tree or (found, "missing", b"")

    def paths(self, expression: str, prefix: str):
        result = self.get(expression)
        if result is None or result[1] != "tree":
            return
        oid, _, raw = result
        oid_bytes = len(oid) // 2  # repositories using either SHA-1 or SHA-256
        offset = 0
        while offset < len(raw):
            end = raw.index(b"\0", offset)
            mode, name = raw[offset:end].split(b" ", 1)
            child = raw[end + 1:end + 1 + oid_bytes].hex()
            path = prefix + "/" + name.decode("utf-8", errors="surrogateescape")
            offset = end + 1 + oid_bytes
            if mode == b"40000":
                yield from self.paths(child, path)
            else:
                yield path


def record_ids_in_history(repo_root: Path, base: str, head: str = "HEAD") -> dict[str, str]:
    """Execution-record ids present at ``base`` or in the tree of any commit of
    ``base..head`` (on either side of a merge, including a record added and
    removed again inside the range), mapped to where each was first seen.
    Read through one batch reader; falls back to one Git call per commit."""
    try:
        return _record_ids_batched(repo_root, base, head)
    except _BatchUnavailable:
        seen = {rid: base for rid in records_at(repo_root, base)}
        for commit in delivery_commits(repo_root, base, head):
            for rid in records_at(repo_root, commit):
                seen.setdefault(rid, commit)
        return seen


def _record_ids_batched(repo_root: Path, base: str, head: str) -> dict[str, str]:
    seen: dict[str, str] = {}
    config = _git(repo_root, "config", "--get", "--bool", "core.quotePath")
    if config.returncode not in (0, 1):
        return seen
    quote_high = config.stdout.strip() != "false"
    with _BatchObjects(repo_root) as objects:
        for commit in [base, *delivery_commits(repo_root, base, head)]:
            ids = set()
            for path in objects.paths(f"{commit}:{EXECUTION_DIRNAME}", EXECUTION_DIRNAME):
                # ls-tree without -z C-quotes these paths; its closing quote
                # means records_at does not regard them as record.jsonl paths.
                raw = path.encode("utf-8", errors="surrogateescape")
                if any(b < 32 or b == 127 or b in (34, 92) or (quote_high and b >= 128) for b in raw):
                    continue
                parts = Path(raw.decode("utf-8")).parts
                if len(parts) >= 3 and parts[-1] == "record.jsonl":
                    ids.add(parts[-2])
            for rid in ids:
                seen.setdefault(rid, commit)
    return seen


def record_versions(repo_root: Path, rel: str, base: str, head: str = "HEAD") -> list[tuple[str, str]]:
    """Every distinct committed version of ``rel`` at ``base`` and in any commit
    of ``base..head``: ``(commit, text)``, deduplicated by blob. Read through one
    batch reader; falls back to one Git call per commit."""
    try:
        return _record_versions_batched(repo_root, rel, base, head)
    except _BatchUnavailable:
        out: list[tuple[str, str]] = []
        blobs: set[str] = set()
        for commit in [base, *delivery_commits(repo_root, base, head)]:
            blob = _git(repo_root, "rev-parse", "-q", "--verify", f"{commit}:{rel}").stdout.strip()
            if not blob or blob in blobs:
                continue
            blobs.add(blob)
            out.append((commit, _git(repo_root, "cat-file", "blob", blob).stdout))
        return out


def _record_versions_batched(repo_root: Path, rel: str, base: str, head: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    blobs: set[str] = set()
    with _BatchObjects(repo_root) as objects:
        for commit in [base, *delivery_commits(repo_root, base, head)]:
            result = objects.get(f"{commit}:{rel}")
            if result is None:
                result = objects.missing_path(commit, rel)
            if result is None or result[0] in blobs:
                continue
            blob, kind, raw = result
            blobs.add(blob)
            # cat-file blob historically returns empty stdout for a non-blob.
            text = raw.decode(locale.getpreferredencoding(False)).replace("\r\n", "\n").replace("\r", "\n") if kind == "blob" else ""
            out.append((commit, text))
    return out
