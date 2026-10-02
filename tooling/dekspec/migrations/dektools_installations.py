"""Migrate host trees DekTools setup emitted at v0.126.0 (ADR-064 (d), IB-149).

Up to v0.126.0 the optional helper tools shipped as a second plugin, and its
setup wrote them into a repository's host root (``.claude/``, ``.codex/``, …)
together with an ownership record, ``<host root>/.dektools-install.json``::

    {"version": 1, "enabled": [...], "files": {<path relative to the host root>: <sha256>}}

Since the tools ship inside the dekspec plugin, nothing writes or reads that
record any more — except this module, which uses it one last time to decide
which files are safe to touch, and then removes it. Everything that knows
about the retired distribution (the record's name and format, the v0.126.0
tool and support-file names, how a host root is classified, how a copy's
references are resolved) lives here; the CLI only calls it and prints the
result, and the per-host emitter only receives the paths it must leave alone.

Two kinds of host root (ADR-064 (d)):

* **tools-only** — a ``.claude/`` root holding the emitted tools and no core
  tree. ``dekspec migrate --from 0.126.0 --apply`` (and ``dekspec sync``,
  through its migrate step) removes the owned, unmodified copies and the
  owned, unmodified support files no remaining copy references. It never
  writes a core file.
* **full-core-tree** — every other record-holding root. Only
  ``dekspec install --platform <host>`` migrates it: the emission re-writes the
  tools from the core layout (adopting the owned, unmodified copies), and this
  module removes the ``setup-dektools`` copy, the adopted files the emission did
  not re-write and the unreferenced support files. ``migrate`` only reports.

In both kinds a modified copy (the unit of disposition is the whole copy) and
every file the record does not own are kept byte-for-byte and reported as
review-only. The record is rewritten to list what is still pending, and
removed once nothing is. A record that escapes its host root is refused before
anything changes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "RECORD_NAME",
    "STAGE",
    "Outcome",
    "RepositoryRun",
    "RootPlan",
    "apply_install",
    "apply_tools_only",
    "find_records",
    "migrate_repository",
    "plan_install",
    "plan_repository",
]

#: The ownership record v0.126.0's DekTools setup wrote into each host root.
RECORD_NAME = ".dektools-install.json"
_RECORD_VERSION = 1

#: The twelve tools v0.126.0 could emit (ADR-064 (c)).
TOOLS = frozenset({
    "audit-codebase", "debug", "deepen", "diagnose-session", "handoff", "ingest-docs",
    "interview-me", "project-board", "prototype", "recover-specs", "security-review", "spike",
})
#: The retired selector skill a full emission always carried.
SETUP = "setup-dektools"
_COPY_NAMES = TOOLS | {SETUP}
#: The shared support files, relative to the host root.
SUPPORT_FILES = ("scripts/dependency_guard.py", "scripts/evidence_common.py", "tool-catalog.json")

TOOLS_ONLY = "tools-only"
FULL_CORE_TREE = "full-core-tree"

#: Core-tree markers for a ``.claude/`` root besides any core skill directory.
_CORE_MARKERS = ("skills/_lib", "skills/using-dekspec")
_MAX_SCAN_BYTES = 1_000_000


class RecordRefused(Exception):
    """A record that cannot be trusted; nothing may change."""


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Outcome:
    """One reported outcome about one file.

    ``action`` is ``remove``, ``adopt`` or ``keep``; ``path`` is relative to the
    repository. Every item about a modified or unowned file is ``review_only``:
    nothing acts on it unattended, and no item suggests deleting it.
    """

    action: str
    path: str
    subject: str
    description: str
    next_step: str
    review_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "path": self.path,
            "subject": self.subject,
            "description": self.description,
            "next_step": self.next_step,
            "review_only": self.review_only,
        }


@dataclass
class RootPlan:
    """Everything decided about one host root before its first write."""

    host: str
    repo: Path
    root: Path
    kind: str
    refused: str | None = None
    #: Root-relative files to remove (owned, unmodified, no longer needed).
    remove: list[str] = field(default_factory=list)
    #: Root-relative files of adopted copies (full-core-tree only); the
    #: emission re-writes those it ships, the rest are removed after it.
    adopt: list[str] = field(default_factory=list)
    #: Root-relative tool directories core emission must leave alone.
    preserve: list[str] = field(default_factory=list)
    #: The pending record: kept owned entries, and unowned files kept at a tool path.
    pending_files: dict[str, str] = field(default_factory=dict)
    pending_unowned: list[str] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)
    #: Root-relative paths the emission would write into the tool directories.
    emission: set[str] = field(default_factory=set)

    @property
    def rel_root(self) -> str:
        return self.root.relative_to(self.repo).as_posix()

    @property
    def completed_by(self) -> str:
        return f"dekspec install --platform {self.host}"

    @property
    def record_after(self) -> str:
        return "rewritten" if (self.pending_files or self.pending_unowned) else "removed"

    @property
    def record_rel(self) -> str:
        return f"{self.rel_root}/{RECORD_NAME}"

    def summary(self, *, applied: bool, by_install: bool) -> list[str]:
        """The heading and closing notes a report prints around the outcomes."""
        head = f"Migration of the v0.126.0 DekTools tree in {self.rel_root} ({self.kind} root)"
        if self.refused:
            return [head, f"  refused: {self.refused}. No host-root file was changed."]
        state = self.record_after if applied else f"would be {self.record_after}"
        notes = [f"  record {self.record_rel}: {state}"
                 + (" to list only what is pending" if self.record_after == "rewritten" else "")]
        if self.kind == FULL_CORE_TREE and not by_install:
            notes.append(f"  This command changes nothing in {self.rel_root}; "
                         f"`{self.completed_by}` completes the migration.")
        elif not applied and not by_install:
            notes.append("  No host-root file was changed; `dekspec migrate --from 0.126.0 --apply` "
                         "applies this.")
        return [head, *notes]

    def to_dict(self, *, applied: bool) -> dict[str, Any]:
        out: dict[str, Any] = {
            "host": self.host,
            "root": self.rel_root,
            "kind": self.kind,
            "applied": applied,
        }
        if self.refused:
            out["refused"] = self.refused
            return out
        out["record"] = self.record_after
        out["completed_by"] = self.completed_by
        out["items"] = [o.to_dict() for o in self.outcomes]
        return out


@dataclass
class RepositoryRun:
    """The migrate-pipeline stage over every record-holding host root."""

    plans: list[RootPlan]
    applied: list[bool]

    @property
    def refused(self) -> bool:
        return any(p.refused for p in self.plans)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": STAGE,
            "exit_code": 1 if self.refused else 0,
            "roots": [p.to_dict(applied=a) for p, a in zip(self.plans, self.applied)],
        }


#: The migrate-pipeline stage name.
STAGE = "dektools-installations"


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #
def _host_roots() -> dict[str, str]:
    from dekspec.platform_install import _HOST_ROOTS

    return dict(_HOST_ROOTS)


def find_records(repo: Path) -> list[tuple[str, Path]]:
    """``(host, host root)`` for every host root under ``repo`` holding a record.

    A record that is a symlink counts as present, so it is refused rather than
    silently ignored.
    """
    repo = Path(os.path.abspath(repo))
    found = []
    for host, rel in _host_roots().items():
        root = repo / rel
        if os.path.lexists(root / RECORD_NAME):
            found.append((host, root))
    return found


# --------------------------------------------------------------------------- #
# planning
# --------------------------------------------------------------------------- #
def plan_repository(repo: Path, source_dir: Path | None) -> list[RootPlan]:
    """Plan every record-holding host root of ``repo`` (``migrate`` / ``sync``)."""
    return [
        _plan(repo, host, root, source_dir, install=False)
        for host, root in find_records(repo)
    ]


def plan_install(repo: Path, host: str, source_dir: Path | None) -> RootPlan | None:
    """Plan ``host``'s root under ``repo`` for ``install --platform``; None without a record."""
    rel = _host_roots().get(host)
    if rel is None:
        return None
    root = Path(os.path.abspath(repo)) / rel
    if not os.path.lexists(root / RECORD_NAME):
        return None
    return _plan(repo, host, root, source_dir, install=True)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_link(path: Path) -> bool:
    return path.is_symlink()


def _check_contained(root: Path, rel: str) -> None:
    """Refuse an absolute path, a ``..`` segment, or a path through a symlink."""
    if not isinstance(rel, str) or not rel or "\\" in rel or "\x00" in rel:
        raise RecordRefused(f"the record lists an unusable path {rel!r}")
    if rel.startswith("/") or os.path.isabs(rel) or re.match(r"^[A-Za-z]:", rel):
        raise RecordRefused(f"the record lists an absolute path {rel!r}")
    parts = rel.split("/")
    if any(p in ("..", ".", "") for p in parts):
        raise RecordRefused(f"the record lists a path with a '..' or empty segment {rel!r}")
    cur = root
    for part in parts:
        cur = cur / part
        if _is_link(cur):
            raise RecordRefused(f"the record lists a path through a symlink {rel!r}")


def _load_record(root: Path) -> tuple[dict[str, str], list[str], bool]:
    """``(files, kept_unowned, rewritten)`` from the host root's record.

    ``rewritten`` is true for a record this module already rewrote to list what
    is pending: only such a record carries ``kept_unowned`` (v0.126.0's setup
    wrote ``version``, ``enabled`` and ``files``).
    """
    record = root / RECORD_NAME
    if _is_link(record):
        raise RecordRefused(f"{RECORD_NAME} is a symlink")
    if _is_link(root):
        raise RecordRefused("the host root is a symlink")
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecordRefused(f"{RECORD_NAME} is unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != _RECORD_VERSION:
        raise RecordRefused(f"{RECORD_NAME} is not a version-{_RECORD_VERSION} ownership record")
    files = data.get("files")
    rewritten = "kept_unowned" in data
    unowned = data.get("kept_unowned", [])
    if not isinstance(files, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in files.items()
    ):
        raise RecordRefused(f"{RECORD_NAME} has no valid `files` map")
    if not isinstance(unowned, list) or not all(isinstance(p, str) for p in unowned):
        raise RecordRefused(f"{RECORD_NAME} has an invalid `kept_unowned` list")
    for rel in [*files, *unowned]:
        _check_contained(root, rel)
    for name in ("skills", "scripts", *(f"skills/{c}" for c in sorted(_COPY_NAMES))):
        if _is_link(root / name):
            raise RecordRefused(f"{name} under the host root is a symlink")
    return dict(files), list(unowned), rewritten


def _copy_of(rel: str) -> str | None:
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == "skills" and parts[1] in _COPY_NAMES:
        return parts[1]
    return None


def _walk_files(base: Path) -> list[Path]:
    """Every file or symlink under ``base`` (links not followed; ``__pycache__`` skipped)."""
    out: list[Path] = []
    if not base.is_dir() or _is_link(base):
        return out
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        here = Path(dirpath)
        out += [here / n for n in filenames]
        out += [here / d for d in dirnames if _is_link(here / d)]
    return sorted(out)


def _emission(source_dir: Path | None) -> dict[str, Path]:
    """Root-relative path -> source, for every file emission writes into a tool directory."""
    out: dict[str, Path] = {}
    if source_dir is None:
        return out
    skills = Path(source_dir) / "skills"
    for tool in sorted(TOOLS):
        src_dir = skills / tool
        if not src_dir.is_dir():
            continue
        for src in sorted(src_dir.rglob("*")):
            if src.is_file():
                out[f"skills/{tool}/{src.relative_to(src_dir).as_posix()}"] = src
    return out


def _is_tools_only(root: Path, source_dir: Path | None, files: dict[str, str]) -> bool:
    """A ``.claude/`` root with no core tree. In doubt, a root is full-core-tree."""
    if root.name != ".claude":
        return False
    if any((root / m).exists() for m in _CORE_MARKERS):
        return False
    if (root / "skills" / SETUP).exists() or any(_copy_of(r) == SETUP for r in files):
        return False
    if source_dir is not None and (Path(source_dir) / "skills").is_dir():
        core = {p.name for p in (Path(source_dir) / "skills").iterdir() if p.is_dir()}
        core -= TOOLS
        if any((root / "skills" / name).exists() for name in core):
            return False
    return True


def _plan(repo: Path, host: str, root: Path, source_dir: Path | None, *, install: bool) -> RootPlan:
    repo = Path(os.path.abspath(repo))
    root = Path(os.path.abspath(root))
    try:
        files, listed_unowned, rewritten = _load_record(root)
    except RecordRefused as exc:
        kind = FULL_CORE_TREE if install or root.name != ".claude" else TOOLS_ONLY
        return RootPlan(host=host, repo=repo, root=root, kind=kind, refused=str(exc))
    kind = FULL_CORE_TREE if install or not _is_tools_only(root, source_dir, files) else TOOLS_ONLY
    plan = RootPlan(host=host, repo=repo, root=root, kind=kind)
    full = kind == FULL_CORE_TREE
    emission = _emission(source_dir) if full else {}
    plan.emission = set(emission)

    # --- classify every recorded file -----------------------------------
    state: dict[str, str] = {}  # rel -> unmodified | modified | missing
    for rel, digest in files.items():
        path = root / rel
        if not path.is_file() or _is_link(path):
            state[rel] = "missing" if not os.path.lexists(path) else "modified"
        else:
            state[rel] = "unmodified" if _sha(path) == digest.lower() else "modified"

    copies: dict[str, list[str]] = {}
    support: list[str] = []
    other: list[str] = []
    for rel in sorted(files):
        copy = _copy_of(rel)
        if copy is not None:
            copies.setdefault(copy, []).append(rel)
        elif rel in SUPPORT_FILES:
            support.append(rel)
        else:
            other.append(rel)
    absent = {c for c, rels in copies.items() if all(state[r] == "missing" for r in rels)}
    modified = {c for c, rels in copies.items()
                if c not in absent and any(state[r] != "unmodified" for r in rels)}

    # --- files the record does not own ----------------------------------
    def emitted_as_is(rel: str) -> bool:
        """The file at ``rel`` is already exactly what the emission writes there."""
        path = root / rel
        return (rel in emission and path.is_file() and not _is_link(path)
                and path.read_bytes() == emission[rel].read_bytes())

    unowned: set[str] = set()
    # Only the directories of copies the record still owns are walked. A
    # directory reached only through ``kept_unowned`` may hold files an earlier
    # run's emission wrote there (an adopted copy), so just the listed paths
    # are re-checked; walking it would report the engine's own files as unowned.
    for rel in listed_unowned:
        if os.path.lexists(root / rel) and rel not in files and not emitted_as_is(rel):
            unowned.add(rel)
    for d in sorted(f"skills/{c}" for c in copies):
        for path in _walk_files(root / d):
            rel = path.relative_to(root).as_posix()
            if rel not in files:
                unowned.add(rel)
    for rel in SUPPORT_FILES:
        if rel not in files and os.path.lexists(root / rel):
            unowned.add(rel)
    # Unowned files at a path core emission would write (full-core-tree only).
    # A v0.126.0 record is checked against every emission path: nothing has
    # been emitted into the tool directories yet, so whatever is there is the
    # operator's. A rewritten record is checked against the paths it lists and
    # against every emission path inside a copy it still owns: such a copy was
    # preserved, so the emission never wrote into its directory and an
    # unrecorded file there is the operator's. A directory an earlier run
    # adopted is checked only at its listed paths, so a file that run's
    # emission wrote is never promoted to a protected unowned file once a
    # later engine ships different bytes.
    candidates = [r for r in emission
                  if not rewritten or r in listed_unowned or _copy_of(r) in copies]
    clashing: set[str] = set()
    for rel in candidates:
        path = root / rel
        if rel in files or not os.path.lexists(path) or emitted_as_is(rel):
            continue  # owned, absent, or already what the emission writes
        unowned.add(rel)
        clashing.add(rel)
    # An unowned file elsewhere in a tool directory is kept, never scanned
    # as anything but a kept file; it does not make the copy modified.

    # --- disposition of each copy ---------------------------------------
    preserve: set[str] = set()
    if full:
        preserve |= {f"skills/{c}" for c in modified if c != SETUP}
        preserve |= {"/".join(rel.split("/")[:2]) for rel in clashing}
    kept_copies: dict[str, list[str]] = {}
    removed_copies: list[str] = []
    adopted_copies: list[str] = []
    for copy, rels in sorted(copies.items()):
        # Entirely absent copies have no owned bytes left to protect. Keep
        # their directories in the unowned/conflict scan above: restoration
        # still obeys preserve, and surviving user files keep their references.
        if copy in absent:
            continue
        if copy in modified:
            kept_copies[copy] = rels
        elif not full or copy == SETUP:
            removed_copies.append(copy)
        elif f"skills/{copy}" in preserve or not any(
            r.startswith(f"skills/{copy}/") for r in emission
        ):
            kept_copies[copy] = rels  # cannot adopt: the emission leaves this directory alone
        else:
            adopted_copies.append(copy)
    plan.preserve = sorted(preserve)

    # --- references the files left in the root make ---------------------
    left: list[tuple[Path, bytes]] = []
    for copy, rels in kept_copies.items():
        for rel in rels:
            if state[rel] != "missing":
                left.append((root / rel, (root / rel).read_bytes()))
    for rel in sorted(unowned):
        path = root / rel
        if path.is_file() and not _is_link(path) and _copy_of(rel) is not None:
            left.append((path, path.read_bytes()))
    if full:
        for rel, src in emission.items():
            if not any(rel.startswith(p + "/") for p in preserve):
                left.append((root / rel, src.read_bytes()))
    referrers, oversized = _references(root, left)

    # --- outcomes, in a stable order ------------------------------------
    rr = plan.rel_root

    def shown(rel: str) -> str:
        return f"{rr}/{rel}"

    for copy in removed_copies:
        for rel in copies[copy]:
            plan.remove.append(rel)
            plan.outcomes.append(Outcome(
                "remove", shown(rel), "setup-copy" if copy == SETUP else "tool-copy",
                "owned and unmodified; "
                + ("the tool selector is retired" if copy == SETUP
                   else f"the dekspec plugin delivers it as /dekspec:{copy}"),
                "none", False))
    for copy in adopted_copies:
        for rel in copies[copy]:
            plan.adopt.append(rel)
            plan.outcomes.append(Outcome(
                "adopt", shown(rel), "tool-copy",
                "owned and unmodified; re-emitted from the core layout"
                + ("" if rel in emission else " (no longer shipped, so removed)"),
                "none", False))
    for copy, rels in kept_copies.items():
        if copy in modified:
            why = "modified locally since the v0.126.0 install"
            step = ("review-only: reconcile it by hand with "
                    + ("the core skills (the tool selector is retired)" if copy == SETUP
                       else f"/dekspec:{copy}"))
            subject = "modified-copy"
        else:
            why = "owned and unmodified, but core emission leaves its directory alone"
            step = "review-only: resolve the unowned file there, then re-run the migration"
            subject = "kept-copy"
        for rel in rels:
            note = why if state[rel] != "missing" else why + " (this file is missing)"
            plan.outcomes.append(Outcome("keep", shown(rel), subject, note, step, True))
            plan.pending_files[rel] = files[rel]
    for rel in support:
        if state[rel] == "missing":
            continue
        refs = referrers.get(rel, [])
        if state[rel] == "modified":
            plan.outcomes.append(Outcome(
                "keep", shown(rel), "support", "modified locally since the v0.126.0 install",
                "review-only: reconcile it by hand", True))
            plan.pending_files[rel] = files[rel]
        elif oversized:
            plan.outcomes.append(Outcome(
                "keep", shown(rel), "support",
                f"reference scanning is incomplete: retained files exceed the {_MAX_SCAN_BYTES:,}"
                "-byte size limit: " + ", ".join(shown(p) for p in oversized),
                "review-only: inspect retained tool references and reconcile support dependencies"
                " by hand before re-running migration", True))
            plan.pending_files[rel] = files[rel]
        elif refs:
            plan.outcomes.append(Outcome(
                "keep", shown(rel), "support",
                "referenced by the kept copy " + ", ".join(shown(c) for c in refs),
                "review-only: kept while that copy references it", True))
            plan.pending_files[rel] = files[rel]
        else:
            plan.remove.append(rel)
            plan.outcomes.append(Outcome(
                "remove", shown(rel), "support", "owned, unmodified and referenced by no tool left",
                "none", False))
    for rel in other:
        if state[rel] == "missing":
            continue
        plan.outcomes.append(Outcome(
            "keep", shown(rel), "unrecognised", "listed in the record but not a v0.126.0 tool file",
            "review-only: left in place", True))
        plan.pending_files[rel] = files[rel]
    for rel in sorted(unowned):
        at = " at a path core emission writes; the emission leaves its directory alone" \
            if rel in clashing else ""
        plan.outcomes.append(Outcome(
            "keep", shown(rel), "unowned", "not installed by DekTools" + at,
            "review-only: left in place", True))
        if rel in clashing or _copy_of(rel) is not None:
            plan.pending_unowned.append(rel)
    return plan


# --------------------------------------------------------------------------- #
# references by path
# --------------------------------------------------------------------------- #
_RELATIVE = re.compile(r"(?<![\w./-])((?:\.\./)+[\w./-]*[\w-])")
_PARENTS = re.compile(r"parents\[(\d+)\]((?:\s*/\s*[\"'][^\"']+[\"'])+)")
_LITERAL = re.compile(r"[\"']([\w./-]+)[\"']")
_PARENTS_WALK = re.compile(r"in\s+Path\(__file__\)\.resolve\(\)\.parents\b(?!\[)")
_IMPORT = re.compile(r"^[ \t]*(?:from[ \t]+([\w.]+)[ \t]+import|import[ \t]+([\w., \t]+))", re.M)


def _references(
    root: Path, left: Iterable[tuple[Path, bytes]],
) -> tuple[dict[str, list[str]], list[str]]:
    """Return support referrers and root-relative files too large to scan.

    Referrers map each support file to the copy directories that reference it.
    Oversized files make non-use uncertain for every support file in this root,
    even when other files have known references. Their bytes are never decoded.

    A reference counts only when it resolves, by path, to that root's support
    file: ``../../scripts/x.py`` against the referring file's own directory, a
    ``parents[N] / "dir"`` insertion followed by an import of a module in that
    directory, or a walk up the file's parents for a named file.
    """
    targets = {os.path.normpath(root / rel): rel for rel in SUPPORT_FILES}
    found: dict[str, set[str]] = {}
    oversized: set[str] = set()

    def hit(path: Path | str, origin: Path) -> None:
        rel = targets.get(os.path.normpath(path))
        if rel is None:
            return
        parts = origin.relative_to(root).parts
        found.setdefault(rel, set()).add("/".join(parts[:2]))

    for path, data in left:
        if len(data) > _MAX_SCAN_BYTES:
            oversized.add(path.relative_to(root).as_posix())
            continue
        text = data.decode("utf-8", errors="ignore")
        for ref in _RELATIVE.findall(text):
            hit(path.parent / ref, path)
        if path.suffix != ".py":
            continue
        modules: set[str] = set()
        for frm, imp in _IMPORT.findall(text):
            names = [frm] if frm else [n.strip().split(" ")[0] for n in imp.split(",")]
            modules |= {n.split(".")[0] for n in names if n}
        for depth, tail in _PARENTS.findall(text):
            parents = path.parents
            if int(depth) >= len(parents):
                continue
            base = parents[int(depth)].joinpath(*re.findall(r"[\"']([^\"']+)[\"']", tail))
            hit(base, path)
            for mod in modules:
                hit(base / f"{mod}.py", path)
        if _PARENTS_WALK.search(text):
            literals = _LITERAL.findall(text)
            for ancestor in path.parents:
                for lit in literals:
                    hit(ancestor / lit, path)
                if ancestor == root:
                    break
    return {rel: sorted(copies) for rel, copies in found.items()}, sorted(oversized)


# --------------------------------------------------------------------------- #
# applying
# --------------------------------------------------------------------------- #
def _remove(root: Path, rels: Iterable[str]) -> None:
    emptied: set[Path] = set()
    for rel in rels:
        path = root / rel
        if path.is_file() and not _is_link(path):
            path.unlink()
            emptied.add(path.parent)
    for d in sorted(emptied, key=lambda p: len(p.parts), reverse=True):
        _prune(d, root)


def _prune(d: Path, root: Path) -> None:
    """Remove ``d`` and its parents (below ``root``) while this run left them empty."""
    while d != root and root in d.parents:
        if not d.is_dir() or _is_link(d):
            return
        cache = d / "__pycache__"
        entries = list(d.iterdir())
        if entries == [cache] and cache.is_dir() and not _is_link(cache) and all(
            p.is_file() and p.suffix == ".pyc" for p in cache.iterdir()
        ):
            for p in cache.iterdir():
                p.unlink()
            cache.rmdir()
            entries = []
        if entries:
            return
        d.rmdir()
        d = d.parent


def _write_record(plan: RootPlan) -> None:
    record = plan.root / RECORD_NAME
    if not (plan.pending_files or plan.pending_unowned):
        record.unlink()
        return
    data = {
        "version": _RECORD_VERSION,
        "files": dict(sorted(plan.pending_files.items())),
        "kept_unowned": sorted(plan.pending_unowned),
    }
    text = json.dumps(data, indent=2) + "\n"
    if record.read_text(encoding="utf-8") != text:
        record.write_text(text, encoding="utf-8")


def migrate_repository(repo: Path, source_dir: Path | None, *, apply: bool) -> RepositoryRun:
    """The ``migrate`` stage: plan every root, then (``apply``) migrate the tools-only ones.

    Every root is planned before any is changed; one refused record refuses
    the whole stage, so nothing changes anywhere.
    """
    plans = plan_repository(repo, source_dir)
    refused = any(p.refused for p in plans)
    applied = []
    for plan in plans:
        doing = apply and not refused and plan.kind == TOOLS_ONLY
        if doing:
            apply_tools_only(plan)
        applied.append(doing)
    return RepositoryRun(plans=plans, applied=applied)


def apply_tools_only(plan: RootPlan) -> None:
    """``migrate --apply`` on a tools-only root: remove, then settle the record."""
    if plan.refused or plan.kind != TOOLS_ONLY:
        return
    _remove(plan.root, plan.remove)
    _write_record(plan)


def apply_install(plan: RootPlan, written: Iterable[Path]) -> None:
    """After ``install --platform``'s emission: remove what the plan retires, settle the record."""
    if plan.refused:
        return
    rewritten = {os.path.abspath(p) for p in written}
    leftovers = [rel for rel in plan.adopt if os.path.abspath(plan.root / rel) not in rewritten]
    _remove(plan.root, [*plan.remove, *leftovers])
    _write_record(plan)
