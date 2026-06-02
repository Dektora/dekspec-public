"""Auto-CoW guard helpers — INT-082 phase 4.

When a pre-ACCEPTED Intent claims a canonical artifact's path, any
direct edit to that artifact is a guard bypass. The authoring skills
consult these helpers before any canonical write:

- `is_path_claimed(repo_root, target_path)` — answers "is this path
  claimed by any pre-ACCEPTED Intent?" Returns `(intent_id, glob,
  incubation_slug)` or None.
- `cow_stage(repo_root, canonical_path, incubation_slug)` — performs
  the copy-on-write atomic: copies the canonical artifact to
  `dekspec/provisional/<slug>/`, renames using the
  `<KIND>-provisional-<file-slug>` convention, stamps `replaces:
  <CANONICAL-ID>` in frontmatter, returns the new path.

The lookup is computed live from SpecGraph each call — no state file
to keep in sync. This is the simpler "consult-on-demand" pattern;
the cached `.dekspec/active-incubations.yaml` design from INT-082's
spec body is deferred (cost-of-cache > value for the current
single-engineer / small-team scale).
"""

from __future__ import annotations

import glob as _glob
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .constraint_compiler.graph import SpecGraph


_PRE_ACCEPTED_STATUSES = frozenset({"DRAFT", "PROPOSED"})


@dataclass(frozen=True)
class Claim:
    """A pre-ACCEPTED Intent's claim on a canonical artifact path."""
    intent_id: str
    glob_pattern: str
    incubation_slug: str | None  # None if Intent has no incubation folder yet


def _intent_incubation_slug(intent_id: str, repo_root: Path) -> str | None:
    """Find the dekspec/provisional/<slug>/ folder associated with an
    Intent (by filename or by intra-folder reference). Returns slug
    name or None."""
    prov = repo_root / "dekspec" / "provisional"
    if not prov.is_dir():
        return None
    for slug_dir in prov.iterdir():
        if not slug_dir.is_dir():
            continue
        # Match by Intent-id in any artifact filename or body.
        for md in slug_dir.rglob("*.md"):
            if intent_id in md.name:
                return slug_dir.name
            try:
                if intent_id in md.read_text(encoding="utf-8"):
                    return slug_dir.name
            except OSError:
                continue
    return None


def _intent_slug_from_filename(intent_path: Path) -> str:
    """Extract the slug portion of an Intent's filename, e.g.
    `INT-079-provisional-folder-scaffold.md` -> `provisional-folder-scaffold`."""
    m = re.match(r"^INT-\d+-(.+)\.md$", intent_path.name)
    return m.group(1) if m else intent_path.stem


def is_path_claimed(repo_root: Path, target_path: str | Path) -> Claim | None:
    """Return the first pre-ACCEPTED Intent (DRAFT or PROPOSED) whose
    Components-affected globs match `target_path`. None if unclaimed.

    `target_path` may be absolute or relative to repo_root.
    """
    repo_root = repo_root.resolve()
    target = Path(target_path)
    if not target.is_absolute():
        target = repo_root / target
    try:
        rel = str(target.resolve().relative_to(repo_root))
    except ValueError:
        return None

    graph = SpecGraph.load(repo_root)
    for ir in graph.intents():
        if (ir.get("status") or "") not in _PRE_ACCEPTED_STATUSES:
            continue
        intent_id = ir.get("id", "")
        for entry in (ir.get("components_affected") or []):
            pat = entry.get("glob") if isinstance(entry, dict) else str(entry)
            if not pat:
                continue
            for m in _glob.glob(str(repo_root / pat), recursive=True):
                try:
                    if Path(m).resolve().relative_to(repo_root) == Path(rel):
                        # Match. Find this Intent's incubation slug if
                        # any; if absent fall back to its filename slug.
                        slug = _intent_incubation_slug(intent_id, repo_root)
                        if slug is None:
                            # Resolve Intent file path to derive slug.
                            intents_dir = repo_root / "dekspec" / "intents"
                            for ip in intents_dir.glob(f"{intent_id}-*.md"):
                                slug = _intent_slug_from_filename(ip)
                                break
                        return Claim(
                            intent_id=intent_id,
                            glob_pattern=pat,
                            incubation_slug=slug,
                        )
                except ValueError:
                    continue
    return None


def _kind_from_canonical_path(canonical_path: Path) -> str | None:
    """Extract `<KIND>` from a canonical artifact filename:
    `dekspec/architecture-elements/AE-007-foo.md` -> `AE`."""
    m = re.match(r"^([A-Z]+)-\d+-", canonical_path.name)
    return m.group(1) if m else None


def _canonical_id_from_filename(canonical_path: Path) -> str | None:
    """Extract `<KIND>-NNN` from a canonical artifact filename."""
    m = re.match(r"^([A-Z]+-\d+)-", canonical_path.name)
    return m.group(1) if m else None


def _file_slug_from_canonical(canonical_path: Path) -> str:
    """`AE-007-foo-bar.md` -> `foo-bar`."""
    m = re.match(r"^[A-Z]+-\d+-(.+)\.md$", canonical_path.name)
    return m.group(1) if m else canonical_path.stem


def cow_stage(
    repo_root: Path, canonical_path: str | Path, incubation_slug: str
) -> Path:
    """Copy `canonical_path` to
    `dekspec/provisional/<incubation_slug>/<KIND>-provisional-<file-slug>.md`,
    stamp `replaces: <CANONICAL-ID>` in the YAML frontmatter (creating
    a frontmatter block if none exists), and return the new path.

    Raises FileNotFoundError if the canonical doesn't exist; raises
    ValueError if the canonical's filename doesn't match a recognised
    `<KIND>-<NNN>-<slug>.md` shape.
    """
    repo_root = repo_root.resolve()
    src = Path(canonical_path)
    if not src.is_absolute():
        src = repo_root / src
    src = src.resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Canonical artifact not found: {src}")

    kind = _kind_from_canonical_path(src)
    canonical_id = _canonical_id_from_filename(src)
    if not kind or not canonical_id:
        raise ValueError(
            f"Cannot derive <KIND>-<NNN> from canonical filename: {src.name}"
        )
    file_slug = _file_slug_from_canonical(src)
    target_dir = repo_root / "dekspec" / "provisional" / incubation_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{kind}-provisional-{file_slug}.md"

    if target.exists():
        # Idempotent — don't clobber an in-flight CoW copy.
        return target

    shutil.copy2(src, target)
    _stamp_replaces(target, canonical_id)
    return target


def _stamp_replaces(path: Path, canonical_id: str) -> None:
    """Insert `replaces: <canonical_id>` into the YAML frontmatter at
    `path`. Creates a frontmatter block if none exists. Idempotent —
    no-op when the line is already present."""
    content = path.read_text(encoding="utf-8")
    if re.search(rf"^replaces\s*:\s*{re.escape(canonical_id)}\s*$",
                 content, flags=re.MULTILINE):
        return
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if m:
        fm = m.group(1).rstrip("\n")
        new_fm = fm + f"\nreplaces: {canonical_id}\n"
        new_content = "---\n" + new_fm + "---\n" + content[m.end():]
    else:
        # No frontmatter; prepend one.
        new_content = (
            "---\nreplaces: " + canonical_id + "\n---\n\n" + content
        )
    path.write_text(new_content, encoding="utf-8")
