"""Source-markdown artifact migrations.

The library ships per-release migrations that transform consumer-side
markdown artifacts (`dekspec/architecture-elements/*.md`, `dekspec/adrs/*.md`,
etc.) to match the schema of the new release.

Two kinds of changes are recognised:

- **Mechanical** — deterministic transforms (rename a frontmatter key, add
  a default field, reshape a heading). Apply automatically.
- **Semantic** — transforms that require human / LLM judgement (split a
  section, infer a new field from prose, restructure relationships).
  These emit an `AdvisoryItem` instead of editing the file; the
  `/dekspec:migrate --walker-only` orchestrator skill walks the advisory queue.

Public API:

    MarkdownMigration             — one (artifact_type, lib_from, lib_to) step.
    MarkdownMigrationResult       — what a single migration call returned.
    AdvisoryItem                  — the contract for "needs human review".
    MarkdownMigrationReport       — per-run summary.
    MarkdownRegistry              — composes migrations across a version range.
    markdown_default_registry     — module-level singleton.
    migrate_markdown_artifacts    — orchestrator: walk repo, apply, emit report.
    write_advisory_report         — persist advisory items to JSON on disk.
    read_advisory_report          — load advisory items from JSON on disk.

Today the registry is empty — the framework ships ahead of any concrete
migration so the first real schema change is a small additive PR.
"""
from __future__ import annotations

import json
import re as _re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator


_SEMVER_RE = _re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def _semver_tuple(version: str) -> tuple[int, int, int]:
    m = _SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"Not a semver-shaped version: {version!r}")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


# --------------------------------------------------------------------------- #
# Advisory item — the "needs human review" contract (Task #3 deliverable).
# --------------------------------------------------------------------------- #


@dataclass
class AdvisoryItem:
    """One semantic change that cannot be auto-applied.

    The orchestrator skill consumes these via the JSON advisory file
    (see `write_advisory_report` / `read_advisory_report`).

    Fields:
      artifact_path: absolute or repo-relative path to the markdown file.
      artifact_type: dekspec artifact type (`adr`, `architecture_element`,
        `working_spec`, `interface_contract`, `implementation_brief`,
        `intent`, `mission`, `domain_glossary`, `system_vision`).
      library_from_version: library version the artifact was last vendored
        against (or the start of the relevant migration span).
      library_to_version: target library version.
      change_type: short slug categorising the kind of work — examples:
        `section_split`, `section_merge`, `field_inference`, `relationship_restructure`,
        `terminology_rename`, `structural_reorder`, `manual_review`.
      description: human-readable explanation of what changed and why
        a human needs to look at it.
      suggested_transform: optional hint — a sentence the orchestrator
        can show the user as a starting point. May be empty.
      context: free-form structured data (line numbers, surrounding text
        excerpts, related artifacts) the orchestrator may surface to
        improve the LLM's reasoning. Keep small — under ~500 chars.

    JSON serialisation is `asdict()`; nothing exotic.
    """
    artifact_path: str
    artifact_type: str
    library_from_version: str
    library_to_version: str
    change_type: str
    description: str
    suggested_transform: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdvisoryItem:
        return cls(
            artifact_path=data["artifact_path"],
            artifact_type=data["artifact_type"],
            library_from_version=data["library_from_version"],
            library_to_version=data["library_to_version"],
            change_type=data["change_type"],
            description=data["description"],
            suggested_transform=data.get("suggested_transform", ""),
            context=data.get("context", {}),
        )


# --------------------------------------------------------------------------- #
# Migration result + step definition
# --------------------------------------------------------------------------- #


@dataclass
class MarkdownMigrationResult:
    """Outcome of running one migration step against one file."""
    new_text: str | None = None  # set when a mechanical change applied; None otherwise
    advisory: AdvisoryItem | None = None  # set when human review is needed
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarkdownMigration:
    """One migration step for one artifact type spanning one library
    version pair.

    The `apply` callable receives the file path (for context) and the
    current file text, and returns a MarkdownMigrationResult. It MUST be
    a pure function (no I/O side effects) — the orchestrator decides
    whether to write or skip based on `dry_run`.

    The step is selected for a given artifact only when:
      - artifact_type matches, AND
      - the migration span [library_from_version, library_to_version)
        overlaps with the requested upgrade span.
    """
    artifact_type: str
    library_from_version: str
    library_to_version: str
    apply: Callable[[Path, str], MarkdownMigrationResult]
    description: str = ""


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class MarkdownRegistry:
    """Holds markdown migrations and selects relevant ones for a given run."""

    def __init__(self) -> None:
        self._steps: list[MarkdownMigration] = []

    def register(self, migration: MarkdownMigration) -> None:
        self._steps.append(migration)

    def all(self) -> list[MarkdownMigration]:
        return list(self._steps)

    def applicable(
        self,
        artifact_type: str,
        from_version: str,
        to_version: str,
    ) -> list[MarkdownMigration]:
        """Return migrations that apply to `artifact_type` and whose span
        overlaps `[from_version, to_version]`. Ordered by library_from_version
        ascending so earlier migrations run first.
        """
        from_t = _semver_tuple(from_version)
        to_t = _semver_tuple(to_version)
        out: list[MarkdownMigration] = []
        for m in self._steps:
            if m.artifact_type != artifact_type:
                continue
            m_from = _semver_tuple(m.library_from_version)
            m_to = _semver_tuple(m.library_to_version)
            # Migration applies when its [from, to] is contained within
            # [requested_from, requested_to]. Strict containment on the
            # upper bound (we don't re-apply migrations that target a
            # version newer than the requested target).
            if m_from >= from_t and m_to <= to_t:
                out.append(m)
        out.sort(key=lambda m: _semver_tuple(m.library_from_version))
        return out


markdown_default_registry = MarkdownRegistry()


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


@dataclass
class MarkdownMigrationReport:
    library_from_version: str
    library_to_version: str
    files_scanned: int
    files_modified: int
    files_unchanged: int
    files_failed: int
    advisories: list[AdvisoryItem]
    per_file_notes: dict[str, list[str]]
    errors: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "library_from_version": self.library_from_version,
            "library_to_version": self.library_to_version,
            "files_scanned": self.files_scanned,
            "files_modified": self.files_modified,
            "files_unchanged": self.files_unchanged,
            "files_failed": self.files_failed,
            "advisories": [a.to_dict() for a in self.advisories],
            "per_file_notes": self.per_file_notes,
            "errors": self.errors,
        }


# --------------------------------------------------------------------------- #
# Artifact-type detection (mirror of cli._detect_artifact_kind, but maps
# to migration artifact_type names rather than parser keys).
# --------------------------------------------------------------------------- #


_PREFIX_TO_TYPE: tuple[tuple[_re.Pattern[str], str], ...] = (
    (_re.compile(r"^ADR-\d{3,}-"), "adr"),
    (_re.compile(r"^AE-\d{3,}-"), "architecture_element"),
    (_re.compile(r"^WS-\d{3,}-"), "working_spec"),
    (_re.compile(r"^IC-\d{3,}-"), "interface_contract"),
    (_re.compile(r"^IB-\d{3,}-"), "implementation_brief"),
    (_re.compile(r"^INT-\d{3,}-"), "intent"),
    (_re.compile(r"^MSN-\d{3,}-"), "mission"),
    (_re.compile(r"^SP-\d{3,}-"), "security_profile"),
)


def detect_artifact_type(filename: str) -> str | None:
    """Return the migration artifact_type for a markdown filename, or
    None if the file isn't a recognised dekspec artifact."""
    if filename == "system-vision.md":
        return "system_vision"
    if filename == "domain-glossary.md":
        return "domain_glossary"
    if filename == "constitution.md":
        return "constitution"
    for pattern, kind in _PREFIX_TO_TYPE:
        if pattern.match(filename):
            return kind
    return None


# --------------------------------------------------------------------------- #
# Walker
# --------------------------------------------------------------------------- #


_ARTIFACT_SUBDIRS = (
    "adrs",
    "architecture-elements",
    "working-specs",
    "interface-contracts",
    "impl-briefs",
    "intents",
    "missions",
    "security-profiles",
    "provisional",
    "divergences",
)


def iter_markdown_artifacts(repo_root: Path, dekspec_root: str = "dekspec") -> Iterator[tuple[Path, str]]:
    """Yield (path, artifact_type) for every dekspec artifact markdown
    file under `repo_root / dekspec_root`. Skips templates, methodology
    docs, and unrecognised files.
    """
    base = repo_root / dekspec_root
    if not base.exists():
        return
    # Singletons at the top level.
    for name, kind in (
        ("system-vision.md", "system_vision"),
        ("domain-glossary.md", "domain_glossary"),
        ("constitution.md", "constitution"),
    ):
        path = base / name
        if path.is_file():
            yield path, kind
    # Subdirectory walks.
    for sub in _ARTIFACT_SUBDIRS:
        subdir = base / sub
        if not subdir.exists():
            continue
        for path in sorted(subdir.rglob("*.md")):
            artifact_type = detect_artifact_type(path.name)
            if artifact_type is None:
                continue
            yield path, artifact_type


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #


def migrate_markdown_artifacts(
    repo_root: Path,
    from_version: str,
    to_version: str,
    *,
    registry: MarkdownRegistry | None = None,
    dekspec_root: str = "dekspec",
    dry_run: bool = False,
) -> MarkdownMigrationReport:
    """Apply markdown migrations to every dekspec artifact under
    `repo_root / dekspec_root`.

    For each file: collect the applicable migrations for the file's
    artifact_type across `[from_version, to_version]`, apply them in
    order, accumulate advisories, and write the result back (unless
    `dry_run`).

    Reports:
      - files_modified: text actually changed in mechanical migrations.
      - files_unchanged: no migration produced new_text.
      - files_failed: exception raised during migration (logged in errors).
      - advisories: combined queue across all files.
    """
    reg = registry if registry is not None else markdown_default_registry
    files_scanned = 0
    files_modified = 0
    files_unchanged = 0
    files_failed = 0
    advisories: list[AdvisoryItem] = []
    per_file_notes: dict[str, list[str]] = {}
    errors: dict[str, str] = {}

    for path, artifact_type in iter_markdown_artifacts(repo_root, dekspec_root):
        files_scanned += 1
        applicable = reg.applicable(artifact_type, from_version, to_version)
        if not applicable:
            files_unchanged += 1
            continue
        try:
            text = path.read_text(encoding="utf-8")
            changed = False
            file_notes: list[str] = []
            for step in applicable:
                result = step.apply(path, text)
                file_notes.extend(result.notes)
                if result.advisory is not None:
                    # Auto-populate path/type/version fields if the caller
                    # left them empty — saves boilerplate in each migration.
                    adv = result.advisory
                    if not adv.artifact_path:
                        adv = AdvisoryItem(
                            artifact_path=str(path),
                            artifact_type=adv.artifact_type or artifact_type,
                            library_from_version=adv.library_from_version
                                or step.library_from_version,
                            library_to_version=adv.library_to_version
                                or step.library_to_version,
                            change_type=adv.change_type,
                            description=adv.description,
                            suggested_transform=adv.suggested_transform,
                            context=adv.context,
                        )
                    advisories.append(adv)
                if result.new_text is not None and result.new_text != text:
                    text = result.new_text
                    changed = True
            if changed:
                if not dry_run:
                    path.write_text(text, encoding="utf-8")
                files_modified += 1
            else:
                files_unchanged += 1
            if file_notes:
                per_file_notes[str(path)] = file_notes
        except Exception as exc:
            files_failed += 1
            errors[str(path)] = f"{type(exc).__name__}: {exc}"

    return MarkdownMigrationReport(
        library_from_version=from_version,
        library_to_version=to_version,
        files_scanned=files_scanned,
        files_modified=files_modified,
        files_unchanged=files_unchanged,
        files_failed=files_failed,
        advisories=advisories,
        per_file_notes=per_file_notes,
        errors=errors,
    )


# --------------------------------------------------------------------------- #
# Advisory persistence
# --------------------------------------------------------------------------- #


ADVISORY_REPORT_FILENAME = "migration-advisory.json"


def advisory_report_path(repo_root: Path, dekspec_root: str = "dekspec") -> Path:
    """Standard location for the advisory report inside a consumer repo.

    Single, overwriting file. The orchestrator skill reads it, walks the
    items, and deletes it when done (like the carryover skill pattern).
    """
    return repo_root / dekspec_root / ADVISORY_REPORT_FILENAME


def write_advisory_report(
    repo_root: Path,
    report: MarkdownMigrationReport,
    *,
    dekspec_root: str = "dekspec",
) -> Path:
    """Persist the advisory list to disk. Returns the file path written.

    Empty advisories produce an empty array in the JSON file (not a
    deleted file) — explicit "nothing to do" is clearer than absence.
    """
    target = advisory_report_path(repo_root, dekspec_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "library_from_version": report.library_from_version,
        "library_to_version": report.library_to_version,
        "generated_at": _now_iso8601(),
        "advisories": [a.to_dict() for a in report.advisories],
    }
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def read_advisory_report(
    repo_root: Path,
    dekspec_root: str = "dekspec",
) -> tuple[dict[str, Any], list[AdvisoryItem]]:
    """Load the advisory report. Returns (header, items).

    The header carries library_from_version, library_to_version, and
    generated_at. Items is a list of AdvisoryItem.

    Raises FileNotFoundError if no advisory report exists.
    """
    target = advisory_report_path(repo_root, dekspec_root)
    if not target.exists():
        raise FileNotFoundError(str(target))
    payload = json.loads(target.read_text(encoding="utf-8"))
    items = [AdvisoryItem.from_dict(a) for a in payload.get("advisories", [])]
    header = {k: v for k, v in payload.items() if k != "advisories"}
    return header, items


def _now_iso8601() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


__all__ = [
    "ADVISORY_REPORT_FILENAME",
    "AdvisoryItem",
    "MarkdownMigration",
    "MarkdownMigrationReport",
    "MarkdownMigrationResult",
    "MarkdownRegistry",
    "advisory_report_path",
    "detect_artifact_type",
    "iter_markdown_artifacts",
    "markdown_default_registry",
    "migrate_markdown_artifacts",
    "read_advisory_report",
    "write_advisory_report",
]
