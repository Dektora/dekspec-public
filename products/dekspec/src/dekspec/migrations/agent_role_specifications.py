"""Source-markdown migration: retired Context Specifications (ADR-061).

Library span 0.125.0 → 0.126.0. DekSpec now supplies the six Agent Role
Specifications itself (``dekspec.roles``); it no longer reads
``<dekspec-root>/context-specs/*.md``. A project holding such a file gets one
advisory per file from ``dekspec migrate``:

* **An unmodified library copy** — its content is byte-identical to a version
  of ``dekspec/context-specs/role-*.md`` the library once carried — is reported
  as safe to delete (``git rm``).
* **Anything else** is custom content. It is preserved exactly as it is,
  reported for review, and never adopted as library policy: a rule it holds
  that DekSpec should follow belongs upstream in the library's role definition.

The migration changes no file (``MarkdownMigration.apply`` is pure; deleting
is the operator's reviewed step), so running it again over the same span
reports the same advisories and changes nothing. The span only decides when
``dekspec migrate`` reports them: ``LINK-LEGACY-CONTEXT-SPEC`` gives the same
disposition on every audit, whatever version the project is marked at. The retired vendored template
``dekspec/templates/context-spec-template.md`` is not handled here: the
vendoring prune removes it on ``dekspec sync`` only when it is an
unmodified shipped copy (see ``vendoring.RETIRED_VENDORED_CONTENT``).
"""

from __future__ import annotations

from pathlib import Path

from dekspec.roles.legacy import KNOWN_LIBRARY_COPIES, classify_legacy

from .markdown import AdvisoryItem, MarkdownMigration, MarkdownMigrationResult, markdown_default_registry

__all__ = ["KNOWN_LIBRARY_COPIES", "LIBRARY_FROM", "LIBRARY_TO", "disposition"]

LIBRARY_FROM = "0.125.0"
LIBRARY_TO = "0.126.0"


def disposition(path: Path, data: bytes) -> tuple[str, str, str]:
    """(change_type, description, suggested action) for one legacy file — the same
    wording `LINK-LEGACY-CONTEXT-SPEC` reports, whatever the migration span."""
    f = classify_legacy(path, data)
    where = path.as_posix()
    if f.kind == "unmodified":
        return ("retired_artifact_unmodified",
                f"Retired Context Specification, an unmodified copy of the library's {f.library_copy}. DekSpec no "
                f"longer reads it; the library supplies {f.successor_text} itself (ADR-061). Safe to delete.",
                f"git rm {where}")
    if f.kind == "custom":
        return ("retired_artifact_custom",
                f"Retired Context Specification with custom content. It is preserved as it is, but DekSpec no longer "
                f"reads it and will not adopt it as policy: roles are library-supplied ({f.successor_text}; ADR-061). "
                "Review it and propose any rule you still need as a change to the DekSpec library's role definition. "
                "Delete it only after that review — never automatically.",
                f"review, then git rm {where}")
    return ("retired_artifact_custom",
            "A file in the retired Context Specification directory (ADR-061). DekSpec reads nothing here and does not "
            "adopt it as policy. Move it if it is still useful; delete it only after review.",
            f"review {where}")


def _apply(path: Path, text: str) -> MarkdownMigrationResult:
    change, description, hint = disposition(path, text.encode("utf-8"))
    review_only = change != "retired_artifact_unmodified"
    return MarkdownMigrationResult(
        advisory=AdvisoryItem(
            artifact_path="", artifact_type="context_spec",
            library_from_version=LIBRARY_FROM, library_to_version=LIBRARY_TO,
            change_type=change, description=description, suggested_transform=hint,
            # A custom file is never acted on by an unattended walk (`--auto-approve`).
            context={"review_only": review_only},
        ),
        notes=[f"retired Context Specification ({change.rsplit('_', 1)[-1]})"],
    )


markdown_default_registry.register(MarkdownMigration(
    artifact_type="context_spec",
    library_from_version=LIBRARY_FROM,
    library_to_version=LIBRARY_TO,
    apply=_apply,
    description="Agent Role Specifications: report retired Context Specifications (never deleted, never adopted)",
))
