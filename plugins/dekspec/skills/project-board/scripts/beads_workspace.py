#!/usr/bin/env python3
"""Resolve issue/governance workspaces using only the standard library.

Current stores are .beads-issues/.beads and .beads-dekspec/.beads. Prefix
precedence is project identity, actual tracked pin, then legacy iss/ds default.
Contradictory or malformed identities are errors, never empty-board success.
Root code beads are retired (ADR-056); code resolution and shared-root fallback
remain solely for reading existing history. No resolver creates a store.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# kind -> (directory CONTAINING the `.beads/` dir, ID prefix).
# The code workspace is the repo root itself, so `br` auto-discovers it and
# bare `br ready` needs no flag (ADR-052 §2).
CONVENTION: dict[str, tuple[str, str]] = {
    "code": (".", "cb"),
    "issue": (".beads-issues", "iss"),
    "dekspec": (".beads-dekspec", "ds"),
}

KINDS = tuple(CONVENTION)

#: Kinds the project manager may touch. Code beads are DELIBERATELY excluded:
#: they are the coding agent's queue, not project-managed work. `prj-mgr` must
#: never read, render, or sync them -- see `pm_workspaces()`.
PM_KINDS: tuple[str, ...] = ("issue", "dekspec")

#: The one kind `prj-mgr` must never operate on.
FORBIDDEN_FOR_PM = "code"


@dataclass(frozen=True)
class Workspace:
    """A resolved `br` workspace."""

    kind: str
    prefix: str
    directory: Path
    #: How this workspace was found -- "convention", "declaration", "verb",
    #: or "fallback" (pre-migration single-workspace repo).
    source: str

    @property
    def db(self) -> Path:
        """Path to the workspace's `br` database."""
        return self.directory / ".beads" / "beads.db"

    @property
    def jsonl(self) -> Path:
        """Path to the workspace's durable JSONL export."""
        return self.directory / ".beads" / "issues.jsonl"

    @property
    def exists(self) -> bool:
        """True when the workspace is present in ANY usable form.

        The `.db` is a local cache that `br` rebuilds and that `br`'s own
        gitignore excludes, so a fresh clone has only `issues.jsonl` -- the
        durable, committed record. Keying existence on the database alone
        makes every freshly-cloned repo look tracker-less.
        """
        return self.db.is_file() or self.jsonl.is_file()

    def br_args(self) -> list[str]:
        """`br` arguments selecting this workspace.

        Empty for the repo-default workspace so that bare `br ready` keeps
        working untouched -- the property ADR-052 §2 exists to protect.
        """
        if (self.directory / ".beads").is_dir() and self.kind == "code":
            return []
        return ["--db", str(self.db)]


def _present(directory: Path) -> bool:
    """Is a `br` workspace present at `directory`?

    Accepts either the database OR the JSONL. `br`'s gitignore excludes the
    `.db`, so on a fresh clone the JSONL is the only evidence a workspace
    exists -- and it is the durable record either way.
    """
    beads = directory / ".beads"
    return (beads / "beads.db").is_file() or (beads / "issues.jsonl").is_file()


def repo_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (or CWD) to the git repo root.

    Falls back to the starting directory when there is no `.git`, so the
    tool still functions outside a repository.
    """
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            return candidate
    return cur


def _from_declaration(root: Path, kind: str) -> Path | None:
    """Layer 2 -- an explicit location in `.dekspec/config.yaml`.

    Parsed with a deliberately small hand-rolled reader rather than PyYAML:
    this module must stay standard-library-only, and the shape we need is a
    flat `issue_tracker:` mapping. A repo doing something more elaborate can
    use the resolution verb instead.
    """
    config = root / ".dekspec" / "config.yaml"
    if not config.is_file():
        return None
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None

    in_tracker = False
    want = f"{kind}_workspace"
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[:1].isspace():
            in_tracker = raw.split(":", 1)[0].strip() == "issue_tracker"
            continue
        if not in_tracker:
            continue
        key, _, value = raw.strip().partition(":")
        if key.strip() == want and value.strip():
            return root / value.strip().strip("\"'")
    return None


def _from_verb(root: Path, kind: str) -> Path | None:
    """Layer 3 -- ask the DekSpec engine, when it happens to be installed.

    Never required. Any failure -- engine absent, verb not yet shipped,
    malformed output -- falls through to the layers above.
    """
    if shutil.which("dekspec") is None:
        return None
    try:
        proc = subprocess.run(
            ["dekspec", "beads", "workspaces", "--json"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    entry = (payload or {}).get(kind) if isinstance(payload, dict) else None
    if isinstance(entry, dict) and entry.get("directory"):
        return root / str(entry["directory"])
    return None


def _scalar(text: str, key: str, *, nested: bool = False) -> str | None:
    """Read the documented scalar YAML subset without an engine dependency.

    Refuse duplicate/complex declarations instead of silently falling back.
    """
    matches = re.findall(r"(?m)^" + (r"[ \t]+" if nested else "") + re.escape(key) + r"\s*:\s*(.*?)\s*$", text)
    if len(matches) > 1:
        raise ValueError(f"Duplicate prefix setting {key}")
    if not matches:
        return None
    value = re.sub(r"\s+#.*$", "", matches[0]).strip()
    if value[:1] in {"'", '\"'}:
        if len(value) < 2 or value[-1] != value[0]:
            raise ValueError(f"Malformed prefix setting {key}")
        value = value[1:-1]
    elif value.lower() in {"null", "~", "true", "false", "yes", "no", "on", "off"} or value[:1] in {"[", "{", "&", "*", "!", "|", ">"} or re.fullmatch(r"[-+]?(?:[0-9][0-9_.eE+-]*|0x[0-9a-fA-F]+)", value):
        raise ValueError(f"Malformed prefix setting {key}: expected a string")
    return value


def _project(root: Path) -> str | None:
    path = root / ".dekspec/config.yaml"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"(?ms)^beads[ \t]*:[ \t]*([^\n]*)\n((?:[ \t]+[^\n]*\n?|\n)*)", text + "\n")
    if not blocks:
        return None
    if len(blocks) != 1:
        raise ValueError("Duplicate beads project prefix config")
    inline, block = blocks[0]
    if inline.strip() and not inline.lstrip().startswith("#"):
        match = re.fullmatch(r"\{\s*project_prefix\s*:\s*['\"]?([a-z0-9]{2,6})['\"]?\s*\}\s*(?:#.*)?", inline)
        value = match[1] if match else None
    else:
        value = _scalar(block, "project_prefix", nested=True)
    if value is None or re.fullmatch(r"[a-z0-9]{2,6}", value) is None:
        raise ValueError("Malformed beads.project_prefix; expected 2–6 lowercase letters or digits")
    return value


def _identity(root: Path, directory: Path, kind: str, default: str) -> str:
    project = _project(root) if kind != "code" else None
    config = directory / ".beads/config.yaml"
    pin = _scalar(config.read_text(encoding="utf-8"), "issue_prefix") if config.exists() else None
    if pin is not None and (not pin or len(pin) > 64 or pin.lower() != pin or not pin.isprintable()):
        raise ValueError(f"Invalid issue_prefix in {config}")
    expected = f"{project}-{default}" if project else pin or default
    if project and pin and pin != expected:
        raise ValueError(f"prefix mismatch: {config} pins {pin}; expected {expected}; run dekspec beads reprefix")
    export = directory / ".beads/issues.jsonl"
    # Root fallback can historically mix kinds. Dedicated stores cannot: an
    # identity mismatch must never produce an apparently successful empty board.
    if export.exists() and directory.resolve() != root.resolve():
        for line in export.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row.get("id"), str) or not row["id"].startswith(expected + "-"):
                raise ValueError(f"prefix mismatch in {export}: {row.get('id')}; expected {expected}-")
    return expected


def resolve(kind: str, root: Path | None = None) -> Workspace:
    """Resolve one workspace by kind. Never raises for a missing workspace.

    Returns a `Workspace` whose `.exists` is False when nothing is present;
    callers decide whether that is an error or an empty board.
    """
    if kind not in CONVENTION:
        raise ValueError(f"unknown bead kind {kind!r}; expected one of {KINDS}")
    root = root or repo_root()
    conv_dir, prefix = CONVENTION[kind]

    declared = _from_declaration(root, kind)
    if declared is not None and _present(declared):
        return Workspace(kind, _identity(root, declared, kind, prefix), declared, "declaration")

    resolved = _from_verb(root, kind)
    if resolved is not None and _present(resolved):
        return Workspace(kind, _identity(root, resolved, kind, prefix), resolved, "verb")

    conventional = (root / conv_dir).resolve()
    if _present(conventional):
        return Workspace(kind, _identity(root, conventional, kind, prefix), conventional, "convention")

    # Pre-migration: the split has not happened, so every kind still lives in
    # the single root workspace. Report it rather than claiming no tracker.
    if kind != "code" and _present(root):
        return Workspace(kind, prefix, root, "fallback")

    return Workspace(kind, _identity(root, conventional, kind, prefix), conventional, "convention")


def resolve_all(root: Path | None = None) -> dict[str, Workspace]:
    """Resolve all three kinds at once."""
    root = root or repo_root()
    return {kind: resolve(kind, root) for kind in KINDS}


def pm_workspaces(root: Path | None = None) -> list[Workspace]:
    """Workspaces the project manager operates on: issue + dekspec, never code.

    `prj-mgr` manages BOTH generic product issues and DekSpec governance work
    -- they are different backlogs but both are project-managed. Code beads are
    excluded by construction: they are executor input, pulled by the coding
    agent via bare `br ready`, and are not project-managed work at all.

    Returns only workspaces that exist, so a repo with just one of the two
    still renders boards.
    """
    root = root or repo_root()
    out = [resolve(kind, root) for kind in PM_KINDS]
    return [ws for ws in out if ws.exists]


def assert_not_code(ws: Workspace) -> None:
    """Guard: refuse a code workspace anywhere in the project-manager path."""
    if ws.kind == FORBIDDEN_FOR_PM:
        raise ValueError(
            "prj-mgr must never operate on the code-bead workspace: code beads "
            "are the coding agent's queue (bare `br ready`), not project-managed "
            "work. Use the issue or dekspec workspace."
        )


def main(argv: list[str] | None = None) -> int:
    """Print the resolved workspaces as JSON -- the discoverability surface.

    Any tool or agent can run this to learn what trackers exist, where they
    live, and how they were found, without importing anything.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve the br bead workspaces (ADR-052)."
    )
    parser.add_argument("--kind", choices=KINDS, help="resolve a single kind")
    parser.add_argument("--at", type=Path, default=None, help="repo root")
    args = parser.parse_args(argv)

    root = repo_root(args.at)
    kinds = [args.kind] if args.kind else list(KINDS)
    payload = {}
    for kind in kinds:
        ws = resolve(kind, root)
        payload[kind] = {
            "prefix": ws.prefix,
            "directory": str(ws.directory.relative_to(root))
            if ws.directory.is_relative_to(root)
            else str(ws.directory),
            "db": str(ws.db),
            "exists": ws.exists,
            "source": ws.source,
            "br_args": ws.br_args(),
        }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
