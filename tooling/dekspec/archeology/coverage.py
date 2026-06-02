"""Spec-gap detection helper for the archeology substrate.

`run(at)` walks a consumer repo, collects the §Components-affected glob set
from every **LOCKED** Intent under `dekspec/intents/`, and reports the files
NOT matched by any glob — the spec-orphaned surfaces a brownfield-recovery
workflow should backfill.

Honors a per-repo exclude file at `.dekspec/archeology-exclude` (newline-
delimited glob patterns; blank lines and `#`-prefixed comments ignored). The
file *extends* a built-in default exclude set — it does not replace it.

`run` returns structured data only — a list of `CoverageGap` dataclasses.
No formatting lives here; the CLI layer formats the result. Per INT-030 /
IB-118.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "CoverageError",
    "CoverageGap",
    "DEFAULT_EXCLUDES",
    "EXCLUDE_FILE",
    "load_excludes",
    "run",
]

# The per-repo exclude file, a sibling of the consumer's other `.dekspec/`
# configuration (resolved at IB-118 authoring time — OI-2).
EXCLUDE_FILE = ".dekspec/archeology-exclude"

# Built-in default exclude set — applied even when EXCLUDE_FILE is absent.
# The consumer's own entries are unioned with these; the file extends, it
# does not replace.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    "**/__pycache__/",
    "**/.venv/",
    "**/node_modules/",
    "**/build/",
    "**/dist/",
    "**/_vendored/",
    "**/.claude/worktrees/**",
    ".beads/",
    "dekspec/_vendored/",
)

# Glob bullet inside an Intent's §Components affected section, mirroring the
# constraint_compiler parser's `_INT_GLOB_BULLET`.
_GLOB_BULLET = re.compile(r"^[-*]\s*`([^`]+)`(?:[ \t]+.*)?$", re.MULTILINE)


class CoverageError(Exception):
    """Raised on an unreadable repo path or a malformed exclude file."""


@dataclass
class CoverageGap:
    """One file not claimed by any LOCKED Intent's §Components-affected glob.

    `path` is the repo-relative path. `last_modified` is the file's mtime as
    an ISO-8601 UTC string. `claimed_by_intent` is the id of the matching
    Intent, or `None` for a genuine orphan — for a gap row it is always
    `None`, but the field is carried per OI-5's `{path, last_modified,
    claimed_by_intent}` shape so a future caller can reuse the dataclass for
    a full coverage map.
    """

    path: str
    last_modified: str
    claimed_by_intent: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "last_modified": self.last_modified,
            "claimed_by_intent": self.claimed_by_intent,
        }


def _split_sections(text: str) -> dict[str, str]:
    """Split a markdown doc into `## Heading` -> body chunks."""
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf)
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf)
    return sections


def _intent_status(sections: dict[str, str]) -> str | None:
    """Extract the Intent status token from its §Status section."""
    body = sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        return s.split()[0].strip("`*_").upper()
    return None


def _intent_id(sections: dict[str, str], filename: str) -> str:
    """Best-effort Intent id — from the filename stem (`INT-NNN-...`)."""
    m = re.match(r"(INT-\d{3,})", filename)
    return m.group(1) if m else filename


def _intent_globs(sections: dict[str, str]) -> list[str]:
    """Glob patterns from an Intent's §Components affected section."""
    body = sections.get("Components affected", "")
    out: list[str] = []
    for m in _GLOB_BULLET.finditer(body):
        glob = m.group(1).strip()
        if glob and not glob.startswith("path/"):
            out.append(glob)
    return out


def _collect_locked_intent_globs(repo_root: Path) -> dict[str, list[str]]:
    """Map every LOCKED Intent id -> its §Components-affected glob list."""
    intents_dir = repo_root / "dekspec" / "intents"
    if not intents_dir.is_dir():
        return {}
    out: dict[str, list[str]] = {}
    for intent_file in sorted(intents_dir.glob("INT-*.md")):
        try:
            text = intent_file.read_text(encoding="utf-8")
        except OSError:
            continue  # unreadable Intent — skip, best-effort
        sections = _split_sections(text)
        if _intent_status(sections) != "LOCKED":
            continue
        intent_id = _intent_id(sections, intent_file.name)
        out[intent_id] = _intent_globs(sections)
    return out


def load_excludes(repo_root: Path) -> list[str]:
    """Resolve the effective exclude-glob set for a repo.

    The built-in `DEFAULT_EXCLUDES` unioned with the consumer's entries from
    `.dekspec/archeology-exclude` (if the file exists). Blank lines and
    `#`-prefixed comment lines in the file are ignored.

    Raises `CoverageError` if the exclude file exists but cannot be read.
    """
    excludes: list[str] = list(DEFAULT_EXCLUDES)
    exclude_path = repo_root / EXCLUDE_FILE
    if not exclude_path.is_file():
        return excludes
    try:
        raw = exclude_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoverageError(f"cannot read exclude file {exclude_path}: {exc}") from exc
    for line in raw.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry not in excludes:
            excludes.append(entry)
    return excludes


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
            if bare and bare in parts:
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


def _claimed_by(rel_path: str, intent_globs: dict[str, list[str]]) -> str | None:
    """First LOCKED Intent id whose glob set claims `rel_path`, else `None`."""
    posix = rel_path.replace("\\", "/")
    for intent_id, globs in intent_globs.items():
        for glob in globs:
            g = glob.replace("\\", "/")
            if fnmatch.fnmatch(posix, g):
                return intent_id
            # `dir/**/*.py`-shaped globs match nested files; also accept a
            # plain `**` segment standing in for any depth.
            if "**" in g and fnmatch.fnmatch(posix, g.replace("**/", "")):
                return intent_id
    return None


def run(at: str | Path = ".") -> list[CoverageGap]:
    """Detect spec-orphaned files in the repo rooted at `at`.

    Walks every file under `at`, skips the exclude set (defaults plus the
    `.dekspec/archeology-exclude` file), and returns one `CoverageGap` per
    file NOT matched by any LOCKED Intent's §Components-affected glob.

    The returned list is sorted by path for determinism. `run` is read-only
    against the target repo — it never writes.

    Raises `CoverageError` on an unreadable repo path or a malformed
    exclude file.
    """
    repo_root = Path(at).resolve()
    if not repo_root.is_dir():
        raise CoverageError(f"repo path is not a directory: {at}")

    excludes = load_excludes(repo_root)
    intent_globs = _collect_locked_intent_globs(repo_root)

    gaps: list[CoverageGap] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        # Always skip the git tree even if no exclude names it. In a normal
        # checkout `.git/` is a directory; in a worktree `.git` is a file
        # (a gitdir pointer) — neither is a spec-bearing surface.
        if rel_posix == ".git" or rel_posix.startswith(".git/"):
            continue
        if _is_excluded(rel_posix, excludes):
            continue
        if _claimed_by(rel_posix, intent_globs) is not None:
            continue
        try:
            mtime = path.stat().st_mtime
            last_modified = (
                datetime.fromtimestamp(mtime, tz=timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ")
            )
        except OSError:
            last_modified = ""
        gaps.append(
            CoverageGap(
                path=rel_posix,
                last_modified=last_modified,
                claimed_by_intent=None,
            )
        )
    return gaps
