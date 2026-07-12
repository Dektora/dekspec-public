# Fan-Out Mode

[← back to dispatcher](../SKILL.md)


See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:intent-author`
- **substantive_modes**: [Creation (default), `--analyze`, `--accept`]
- **inline_modes**: [`--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock`, `--sync`, `--testpass`, `--amend`, `--decompose`]
- **bundle_list** (Step 1 context):
  1. Template path — `dekspec/templates/intent-template.md`.
  2. Methodology references — `docs/dekspec-methodology.md` §4 Intent + Mission; `dekspec/dekspec-operating-guide.md` §Intents (if present).
  3. CLAUDE.md sections — §Component → File-Glob Map; §Verification Predicate Library.
  4. Related artifacts from the spec graph (paths only — subagent reads what it needs): `dekspec/architecture-elements-index.md` (AE catalog for `Linked Architecture Elements:` validation); for Creation, every existing AE under `dekspec/architecture-elements/`; for `--analyze` / `--accept`, the target Intent path + its linked AE files + any WSes the Components touch (via `dekspec/working-specs-index.md`) + the Mission file at `dekspec/missions/MSN-NNN-*.md` if `Mission:` populated; `dekspec/domain-glossary.md`; `dekspec/intent-index.md` (for next-INT-NNN + serialization-guard scan).
  5. Engineer guidance — `$ARGUMENTS` verbatim, including structured cues (`type:`, `mission:`, `source:`, `autonomy:`).
  6. Constraints — the rules block at the bottom of this skill (Files canonical D2; Serialization per-Mission advisory per ADR-016; Type drives shape; D19/D20 hard; Linked AE mandatory D12; etc.).
- **expected_output_path**: `dekspec/intents/INT-NNN-<slug>.md` (Creation) or the input path (`--analyze` / `--accept`; subagent edits in place).
- **validation**: `dekspec validate --kind intent <output-path>`. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry. Mode-specific post-checks: `--analyze` → Coverage Report + Size Assessment populated; `--accept` → Status flipped to ACCEPTED + Amendment Log entry appended; Creation → branch created + appended to intent-index.

**End of Fan-Out Mode.**
