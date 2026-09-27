"""Source-markdown migration: `guidance-and-corrections.md` -> `terminology-corrections.md` (INT-191).

INT-191 split `write-ggc` into `write-glossary` and `write-corrections` and
retired the word "Guidance" from the artifact set.  The investigation behind
that Intent established that nothing ever implemented guidance: the file was a
ten-line placeholder, the skill had no guidance mode, and `ggc_ops.py` exposed
no guidance-shaped function.  What the file actually holds is a log of
terminology corrections, so it is now named for that:

    dekspec/guidance-and-corrections.md  ->  dekspec/terminology-corrections.md

Consumers vendor the skill and hold a real, populated file at the old path.  A
rename with no migration path silently orphans it, which is what this module
exists to prevent.

## What this migration does, and what it deliberately does not

`MarkdownMigration.apply` is contractually **pure** — the orchestrator
(`migrate_markdown_artifacts`) decides whether to write, so a step may not
touch the filesystem.  A file *rename* is filesystem work.  So the migration
splits along the framework's existing seam:

- **Mechanical, applied automatically** — the in-file text: the `# Guidance and
  Corrections` H1 becomes `# Terminology Corrections`, the `dekspec init`
  scaffold comment is restamped, and references to the retired `/write-ggc`
  skill are repointed at `/write-corrections`.
- **Advisory, surfaced for the operator** — the rename itself, emitted as an
  `AdvisoryItem` with `change_type="terminology_rename"` (one of the change
  types the advisory contract already enumerates).  `dekspec migrate-artifacts`
  writes it into the advisory report and `/dekspec:migrate --walker-only` walks
  it.  The advisory carries the exact `git mv` to run.

The file is reached at all because `markdown.detect_artifact_type` and
`markdown.iter_markdown_artifacts` recognise **both** spellings of the
singleton under one artifact_type, `terminology_corrections`.  A walker that
only knew the new name could never see the file it is supposed to rename.

## Invariants

- **Idempotent.** A second run is a no-op: the mechanical rewrites are all
  anchored on the legacy spellings, and the advisory fires only while the file
  still sits at the legacy path.
- **Pure.** No I/O; the rename is advised, never performed here.
- **Content-preserving.** Only the H1, the `dekspec init` scaffold comment, and
  `/write-ggc` references change.  Correction entries, recurrence logs and
  promotion statuses are untouched — INT-191 is explicit that artifact content
  is not rewritten, only the filename.
"""
from __future__ import annotations

import re
from pathlib import Path

from .markdown import (
    AdvisoryItem,
    MarkdownMigration,
    MarkdownMigrationResult,
    markdown_default_registry,
)
from .markdown import (
    LEGACY_GUIDANCE_CORRECTIONS_FILENAME as _LEGACY_NAME,
)
from .markdown import (
    TERMINOLOGY_CORRECTIONS_FILENAME as _CANONICAL_NAME,
)

# The library release that ships the rename.  `dekspec migrate-artifacts`
# selects a step when its span sits inside the requested [from, to] span, so a
# consumer upgrading from <= 0.123.0 to >= 0.124.0 picks this up exactly once.
_FROM_VERSION = "0.123.0"
_TO_VERSION = "0.124.0"

# `# Guidance and Corrections` as an H1 anywhere in the file.
_LEGACY_H1_RE = re.compile(
    r"^#[ \t]+Guidance and Corrections[ \t]*$", re.MULTILINE,
)

# The `dekspec init` scaffold comment's opening line.
_SCAFFOLD_LABEL_RE = re.compile(
    r"^([ \t]*)Guidance and Corrections(?=[ \t]+—[ \t]+placeholder)",
    re.MULTILINE,
)

# The scaffold's body sentence, which named the retired skill and the retired
# concept in one breath.
_SCAFFOLD_SENTENCE_RE = re.compile(
    r"Append corrections \+ standing guidance with `/write-ggc`\.",
)

# Any surviving reference to the retired skill, namespaced or bare.  Ordered
# longest-first so the namespaced form matches before the bare one.
_WRITE_GGC_RE = re.compile(r"/(?:dekspec:)?write-ggc\b")


def _apply(path: Path, text: str) -> MarkdownMigrationResult:
    """Restamp the corrections singleton's prose and advise the rename.

    Returns a result with `new_text` set when any legacy spelling was found,
    and an `advisory` when the file is still at the pre-INT-191 path.
    """
    new_text = _LEGACY_H1_RE.sub("# Terminology Corrections", text)
    new_text = _SCAFFOLD_LABEL_RE.sub(r"\1Terminology Corrections", new_text)
    new_text = _SCAFFOLD_SENTENCE_RE.sub(
        "Append corrections with `/write-corrections --log`.", new_text,
    )
    new_text = _WRITE_GGC_RE.sub("/write-corrections", new_text)

    notes: list[str] = []
    if new_text != text:
        notes.append(
            f"restamped {path.name} for the INT-191 Guidance -> Terminology "
            f"Corrections rename"
        )

    advisory: AdvisoryItem | None = None
    if path.name == _LEGACY_NAME:
        target = path.with_name(_CANONICAL_NAME)
        advisory = AdvisoryItem(
            artifact_path="",  # orchestrator fills this in from `path`
            artifact_type="terminology_corrections",
            library_from_version=_FROM_VERSION,
            library_to_version=_TO_VERSION,
            change_type="terminology_rename",
            description=(
                f"INT-191 renamed the corrections singleton from "
                f"`{_LEGACY_NAME}` to `{_CANONICAL_NAME}`. The word "
                f"\"Guidance\" named nothing that was ever implemented, and "
                f"the file is a log of terminology corrections. The file's "
                f"contents have been restamped in place; the rename itself "
                f"needs a filesystem move, which a migration step may not "
                f"perform. Rename it, then check any repo-local references "
                f"(AGENTS.md, CLAUDE.md, session-load pointers) to the old "
                f"path. The retired `/write-ggc` skill is replaced by "
                f"`/write-corrections` (log, recurrences, review) and "
                f"`/write-glossary` (terms, extraction)."
            ),
            suggested_transform=(
                f"git mv {_LEGACY_NAME} {_CANONICAL_NAME}   "
                f"# run from {target.parent}"
            ),
            context={
                "old_filename": _LEGACY_NAME,
                "new_filename": _CANONICAL_NAME,
                "intent": "INT-191",
                "retired_skill": "write-ggc",
                "successor_skills": "write-corrections, write-glossary",
            },
        )

    return MarkdownMigrationResult(
        new_text=new_text if new_text != text else None,
        advisory=advisory,
        notes=notes,
    )


markdown_default_registry.register(MarkdownMigration(
    artifact_type="terminology_corrections",
    library_from_version=_FROM_VERSION,
    library_to_version=_TO_VERSION,
    apply=_apply,
    description=(
        "INT-191: rename the corrections singleton "
        "`guidance-and-corrections.md` -> `terminology-corrections.md` and "
        "repoint retired `/write-ggc` references at `/write-corrections`. "
        "Text is restamped mechanically; the filesystem rename is emitted as "
        "a `terminology_rename` advisory. Idempotent."
    ),
))


__all__ = ["_apply"]
