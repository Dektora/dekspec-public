"""The Behavior Specification kind's names, new and old (IB-207, O-12).

Audit rule-id aliases and retired display-form renames also live here (IB-212).
Runtime readers use ``canonical_rule_id``; retired forms are text renames only.
Outcome names, recognition and file discovery share one compatibility boundary.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re
from types import MappingProxyType

__all__ = [
    "BEHAVIOR_SPEC_NAMES",
    "BehaviorSpecNames",
    "OUTCOME_NAMES",
    "OutcomeNames",
    "RETIRED_RULE_ID_RENAMES",
    "RULE_ID_ALIASES",
    "canonical_rule_id",
]

#: Old audit rule id -> new id (IB-212 O-9; append-only).
RULE_ID_ALIASES: Mapping[str, str] = MappingProxyType({
    "LINK-IB-WS-EXISTS": "LINK-IB-BS-EXISTS",
    "LINK-WS-AE-EXISTS": "LINK-BS-AE-EXISTS",
    "LINK-WS-AE-MISSING": "LINK-BS-AE-MISSING",
    "LINK-WS-BLOCKING-PRE-IB-CLEAN": "LINK-BS-BLOCKING-PRE-IB-CLEAN",
    "T20-WS-BUSINESS-RULES": "T20-BS-BUSINESS-RULES",
    "T21-WS-FAILURE-BEHAVIOR": "T21-BS-FAILURE-BEHAVIOR",
    "T-PROSE-WS-BUSINESS-RULE": "T-PROSE-BS-BUSINESS-RULE",
    "T-PROSE-WS-FAILURE-BEHAVIOR": "T-PROSE-BS-FAILURE-BEHAVIOR",
    "D17-AE-NUMERIC-NO-WS-CITE": "D17-AE-NUMERIC-NO-BS-CITE",
    "D19-INT-NUMERIC-NO-WS-CITE": "D19-INT-NUMERIC-NO-BS-CITE",
    "D-15d-IC-NUMERIC-NO-WS-CITE": "D-15d-IC-NUMERIC-NO-BS-CITE",
    "D-15a-WS-RATIONALE-NO-ADR-CITE": "D-15a-BS-RATIONALE-NO-ADR-CITE",
})

#: Retired ``L<n>`` display form -> renamed text form (IB-212 O-11; not runtime aliases).
RETIRED_RULE_ID_RENAMES: Mapping[str, str] = MappingProxyType({
    "L3-WS-AE-EXISTS": "L3-BS-AE-EXISTS",
    "L3-WS-AE-MISSING": "L3-BS-AE-MISSING",
    "L5-IB-WS-EXISTS": "L5-IB-BS-EXISTS",
    "L12-WS-BLOCKING-PRE-IB-CLEAN": "L12-BS-BLOCKING-PRE-IB-CLEAN",
})


def canonical_rule_id(rule_id: str) -> str:
    """Resolve a registered old id; leave all other strings unchanged."""
    return RULE_ID_ALIASES.get(rule_id, rule_id)


@dataclass(frozen=True)
class BehaviorSpecNames:
    """Every old and new name of the Behavior Specification kind (O-12)."""

    id_prefix: str = "BS"
    old_id_prefixes: tuple[str, ...] = ("WS",)
    provisional_prefix: str = "P-BS"
    old_provisional_prefixes: tuple[str, ...] = ("P-WS",)
    folder: str = "behavior-specs"
    old_folders: tuple[str, ...] = ("working-specs",)
    heading: str = "Behavior Specification"
    old_headings: tuple[str, ...] = ("Working Spec",)
    display_name: str = "Behavior Specification"
    short_name: str = "Behavior Spec"
    old_display_names: tuple[str, ...] = ("Working Spec",)
    index_file: str = "behavior-spec-index.md"
    old_index_files: tuple[str, ...] = ("working-spec-index.md", "ws-index.md")
    template: str = "behavior-spec-template.md"
    old_templates: tuple[str, ...] = ("working-spec-template.md",)
    schema_file: str = "behavior-spec.schema.yaml"
    old_schema_files: tuple[str, ...] = ("working-spec.schema.yaml",)
    ir_kind: str = "behavior_spec"
    old_ir_kinds: tuple[str, ...] = ("working_spec",)
    skill: str = "write-bs"
    old_skills: tuple[str, ...] = ("write-ws",)
    rule_ids: Mapping[str, str] = field(default_factory=lambda: RULE_ID_ALIASES)

    @property
    def prefixes(self) -> tuple[str, ...]:
        return (self.id_prefix, *self.old_id_prefixes)

    @property
    def folders(self) -> tuple[str, ...]:
        return (self.folder, *self.old_folders)

    @property
    def id_pattern(self) -> str:
        return "(?:" + "|".join(map(re.escape, self.prefixes)) + r")-\d{3,}"

    @property
    def id_starts(self) -> tuple[str, ...]:
        return tuple(p + "-" for p in self.prefixes)

    def to_new_id(self, artifact_id: str) -> str:
        for prefix in (*self.old_id_prefixes, *self.old_provisional_prefixes):
            if re.fullmatch(re.escape(prefix) + r"-\d{3,}", artifact_id):
                target = self.provisional_prefix if prefix in self.old_provisional_prefixes else self.id_prefix
                return target + artifact_id[len(prefix):]
        return artifact_id

    def paths(self, spec_dir: Path, artifact_id: str | None = None) -> list[Path]:
        """Find canonical files in either folder, matching either spelling of an ID."""
        found = []
        wanted = self.to_new_id(artifact_id) if artifact_id else None
        for folder in self.folders:
            for prefix in self.prefixes:
                for path in (spec_dir / folder).glob(prefix + "-*.md"):
                    match = re.match(self.id_pattern + r"(?=-)", path.name)
                    if match and (wanted is None or self.to_new_id(match[0]) == wanted):
                        found.append(path)
        return sorted(found)

    def index_path(self, spec_dir: Path) -> Path:
        """Use the existing index in priority order, creating only the new name."""
        return next((spec_dir / name for name in (self.index_file, *self.old_index_files)
                     if (spec_dir / name).exists()), spec_dir / self.index_file)


BEHAVIOR_SPEC_NAMES = BehaviorSpecNames()


class OutcomeNames:
    """Hide all Outcome/Intent spellings behind current and canonical.

    Callers never enumerate old names; ids retain their number when canonicalized.
    Unrelated values return None; unknown surfaces raise ValueError, so a caller
    mistake is never confused with a nonmatching artifact. Both operations are pure.
    Alias tables and per-surface methods were rejected: callers need recognition
    and current names, not alias storage or an expanding family of special cases.
    """

    def current(self, surface: str) -> str:
        """Return the current name for a supported surface; unknown: ValueError.

        Surfaces: id, provisional_id, folder, index, template, schema, heading,
        command, changes_heading, check_heading, brief_goal_heading.
        Id surfaces return their prefix (OUT or P-OUT), without a number.
        """
        return self._names(surface)[0]

    def canonical(self, value: str, *, surface: str) -> str | None:
        """Recognize either spelling and return its current name, else None.

        For id surfaces accept a whole numbered id, preserving its numeric text.
        Unknown surfaces raise ValueError. This does not rewrite any artifact.
        """
        names = self._names(surface)
        if surface in ("id", "provisional_id"):
            match = re.fullmatch(self.pattern(surface), value)
            return names[0] + "-" + value.rsplit("-", 1)[1] if match else None
        return names[0] if value in names else None

    legacy_brief_heading = "Outcome"
    legacy_parent_heading = "Intent"
    command_aliases = ("intent",)

    _surfaces = {
        "id": ("OUT", "INT"),
        "id_prefix": ("OUT", "INT"),
        "provisional_id": ("P-OUT", "P-INT"),
        "folder": ("outcomes", "intents"),
        "index": ("outcome-index.md", "intent-index.md"),
        "template": ("outcome-template.md", "intent-template.md"),
        "schema": ("intent.schema.yaml", "outcome.schema.yaml"),
        "heading": ("Outcome", "Intent"),
        "command": ("outcome", "intent"),
        "changes_heading": ("What changes", "Desired Outcome"),
        "check_heading": ("Outcome check", "Outcome Verification"),
        "brief_goal_heading": ("Goal", "Outcome"),
        "beneficiary_heading": ("Who it is for",),
    }

    def _names(self, surface: str) -> tuple[str, ...]:
        try:
            return self._surfaces[surface]
        except KeyError:
            raise ValueError(f"Unknown Outcome name surface: {surface}") from None

    def pattern(self, surface: str = "id") -> str:
        """A noncapturing regex recognizing this surface (no boundary anchors)."""
        pattern = "(?:" + "|".join(map(re.escape, self._names(surface))) + ")"
        return pattern + r"-\d{3,}" if surface in ("id", "provisional_id") else pattern

    def for_artifact(self, artifact_id: str, surface: str) -> str:
        """Vocabulary appropriate to a written id; unrelated ids use current names.

        This preserves unmoved projects' diagnostics and authoring destinations
        without asking callers to distinguish historical spellings.
        """
        names = self._names(surface)
        for index, prefix in enumerate(self._names("id")):
            if re.fullmatch(r"(?:P-)?" + re.escape(prefix) + r"-\d{3,}", artifact_id):
                return names[min(index, len(names) - 1)]
        for spellings in self._surfaces.values():
            if artifact_id in spellings:
                return names[min(spellings.index(artifact_id), len(names) - 1)]
        return names[0]

    def describe(self, text: str, artifact_id: str) -> str:
        """Render human prose in the named artifact's vocabulary; never rewrite ids."""
        recognized = any(self.canonical(artifact_id, surface=surface)
                         for surface in ("id", "provisional_id", "index"))
        if not recognized or self.for_artifact(artifact_id, "heading") != self.current("heading"):
            return text
        for surface in ("heading", "changes_heading", "check_heading"):
            names = self._names(surface)
            for alias in names[1:]:
                text = re.sub(r"\b" + re.escape(alias) + r"(s?)\b",
                              lambda match: names[0] + match[1], text)
        for alias in self._names("command")[1:]:
            text = text.replace("dekspec " + alias + " ", "dekspec " + self.current("command") + " ")
        return text

    def filename_id(self, filename: str) -> str | None:
        """Read a numbered canonical or provisional filename, retaining its id."""
        match = re.fullmatch(rf"((?:{self.pattern()}|{self.pattern('provisional_id')}))-.+\.md", filename)
        return match[1] if match else None

    def paths(self, spec_dir: Path, artifact_id: str | None = None) -> list[Path]:
        """Find canonical files recursively in either home; never choose an ambiguity.

        An id selects its shared numeric identity. No files are changed; callers
        that require one match must refuse multiple results, naming all files.
        """
        wanted = self.canonical(artifact_id, surface="id") if artifact_id else None
        if artifact_id and wanted is None:
            return []
        found = []
        for folder in self._names("folder"):
            for path in (spec_dir / folder).rglob("*.md"):
                ident = self.filename_id(path.name)
                identity = self.canonical(ident or "", surface="id")
                # Unfiltered walks retain malformed files so parsers can report
                # them, just as the original kind-folder loader did.
                recognized_file = re.match(self.pattern("id_prefix") + "-", path.name)
                if (wanted is None and recognized_file) or (wanted is not None and wanted == identity):
                    found.append(path)
        return sorted(found)

    def index_path(self, spec_dir: Path) -> Path:
        """Select an existing index, preferring current; default to current."""
        for name in self._names("index"):
            if (spec_dir / name).is_file():
                return spec_dir / name
        for folder in self._names("folder"):
            if (spec_dir / folder).is_dir():
                return spec_dir / self.for_artifact(folder, "index")
        return spec_dir / self.current("index")

    def next_number(self, spec_dir: Path, reserved: Iterable[str] = ()) -> int:
        """Next canonical number across both forms, plus any reserved ids.

        Provisional hints are not allocations. Reserved ids may be a registry
        snapshot or numbers assigned earlier in the same transaction.
        """
        ids = [self.filename_id(path.name) for path in self.paths(spec_dir)]
        ids.extend(reserved)
        numbers = [int(value.rsplit("-", 1)[1]) for value in ids
                   if value and self.canonical(value, surface="id")]
        return max(numbers, default=0) + 1


OUTCOME_NAMES = OutcomeNames()


# Shared layout registrations. Callers enumerate artifact kinds, never aliases.
# Kept here so name changes do not spread into command, graph or audit tables.
ARTIFACT_FOLDERS = MappingProxyType({
    "ADR": "adrs", "AE": "architecture-elements",
    **dict(zip(BEHAVIOR_SPEC_NAMES.prefixes, BEHAVIOR_SPEC_NAMES.folders)),
    "IC": "interface-contracts", "IB": "impl-briefs", "MSN": "missions",
    "SP": "security-profiles",
    **dict(zip(OUTCOME_NAMES._names("id"), OUTCOME_NAMES._names("folder"))),
})
ARTIFACT_PREFIXES = tuple(ARTIFACT_FOLDERS)
