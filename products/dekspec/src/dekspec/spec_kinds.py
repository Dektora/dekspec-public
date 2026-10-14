"""The Behavior Specification kind's names, new and old (IB-207, O-12).

Audit rule-id aliases and retired display-form renames also live here (IB-212).
Runtime readers use ``canonical_rule_id``; retired forms are text renames only.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re
from types import MappingProxyType

__all__ = [
    "BEHAVIOR_SPEC_NAMES",
    "BehaviorSpecNames",
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
