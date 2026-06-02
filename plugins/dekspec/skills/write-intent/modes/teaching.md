# Teaching Mode

[← back to dispatcher](../SKILL.md)


See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: Intent (INT-NNN)
- **template_path**: `templates/intent-template.md`
- **methodology_section**: §4 Intent + Mission of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/intents/INT-001-constitution-artifact.md` (documentation-typed design parent), `dekspec/intents/INT-006-lite-profile-for-solo-engineers.md` (methodology refactor)
- **required_sections**: [Status, Intent type, Autonomy, Linked Architecture Elements, Components affected, Verification, Motivation, Desired Outcome, type-specific block]

Skill-specific structural checks to surface as Open Issues: T13 (Intent type enum), T14 (≥1 Verification cmd), T15 (≥1 Components glob), T16 (Autonomy enum), L7a (Linked AE existence), L9 (Verification cmd resolves).

**Skill-unique prompts:** for Intent type, walk through the 7-value enum plus the type-specific field requirements before accepting input. The placeholder revision flag is `--amend` (not `--revise`) for Intents.
