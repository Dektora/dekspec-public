# DekSpec Teaching Mode — Canonical Substrate

**Status:** AUTHORITATIVE (per ds-int-007-multimode-skills-znn / INT-008-multi-mode-skills-dispatcher).
**Audience:** DekSpec skill authors. Every authoring skill at `plugins/dekspec/skills/write-*/SKILL.md` cites this file from its `## Teaching Mode` H2 and declares a per-skill parameter manifest beneath the citation.
**Lineage:** Extracted from the per-skill Teaching Mode bodies that landed alongside INT-008. Prior to extraction, all 13 authoring skills carried a near-identical 4-step ritual (explain → exemplar → prompt → structural-check) with only the artifact kind, template path, methodology section, exemplar paths, and required-section list differing. The contract below pins the ritual; each skill supplies the parameters.

---

## Why this file exists

Before this substrate landed, every authoring skill rolled its own Teaching Mode prose. Three concrete consequences:

1. **The 4-step ritual drifted across skills.** Some skills omitted the structural-check step. Some skipped the exemplar step entirely. Some buried the "this is distinct from `--review`" disambiguation in the wrong place. New engineers learning a second artifact kind had to re-learn the ritual.
2. **Sharpening the ritual required N edits.** When the methodology team decided every Teaching Mode must surface its structural-check failures as Open Issues (not silently accept), the prose had to be hand-edited in all 13 skills. Three skills were missed on the first pass.
3. **No source of truth for "what does Teaching Mode actually do."** When a skill author wanted to know whether Teaching Mode should write the artifact to disk (yes — at DRAFT status) or whether it should validate references inline (yes — call out the failing rule immediately), the answer had to be reconstructed from reading sibling skills.

This file is the source of truth. Each authoring SKILL.md replaces its prior Teaching Mode body with a short citation + a parameter manifest. The body of the ritual lives here exactly once.

## The canonical Teaching Mode contract

Trigger: `--teaching` flag. Audience: an engineer authoring their first `<artifact_kind>` in this repo.

Teaching Mode walks the engineer through authoring a brand-new artifact, section-by-section, against the artifact's template. It is **not** a re-audit of existing content (that is `--review`), and it is **not** a fast creation from a one-shot description (that is the no-flag creation mode). Teaching Mode assumes the engineer is new to this artifact kind and needs section-by-section guidance with exemplars in front of them.

The ritual is a strict 4-step loop. For each required section in the artifact's template (in template order):

1. **Explain the section's purpose** in 1-3 sentences. Cite the relevant template (`template_path`) and the relevant methodology section (`methodology_section`) so the engineer can read deeper if they want. Do not paraphrase the template — refer to it.
2. **Show one or two exemplar artifacts.** Pull from the engineer's own repo first (the paths listed in `exemplar_paths`). If none exist yet, fall back to `tests/fixtures/`. Short excerpts are preferred over whole artifacts; the goal is to make the section's shape obvious, not to overwhelm.
3. **Prompt the engineer for content.** Accept inline text or the literal word `skip` to leave a placeholder that the engineer can fill later via `--revise` (or the skill's equivalent edit mode). Do not invent content on the engineer's behalf — Teaching Mode is interactive by design.
4. **Surface structural-check failures as Open Issues.** If the engineer's content fails any structural rule (template format, required field, glossary term not defined, broken cross-artifact reference), call out the failing rule immediately by name. Do not silently accept. The failure becomes an entry in the artifact's `## Open Issues` section; it does not block the rest of the ritual.

When every required section has been filled or explicitly skipped, exit with a summary listing:

- Sections completed.
- Sections skipped (placeholder text inserted; the engineer can fill via the skill's revise/amend mode).
- Open Issues filed for any structural-check failures encountered during the ritual.

The artifact is written to disk at the artifact's initial draft status (typically `DRAFT` or `PROPOSED`, depending on the artifact's lifecycle). From there, the engineer reviews with `--review`, audits with `--audit`, and promotes via the artifact's lifecycle modes (`--accept`, `--lock`, etc.).

## Recommended skill-side template

Replace the prior `## Teaching Mode` body in each SKILL.md with this exact shape, then fill in the parameters:

```markdown
## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: <e.g., ADR, Working Spec, Mission>
- **template_path**: `templates/<...>-template.md`
- **methodology_section**: §<N> of `docs/dekspec-methodology.md` (if applicable)
- **exemplar_paths**: `dekspec/.../<exemplar-1>.md`, `dekspec/.../<exemplar-2>.md`
- **required_sections**: [<comma-separated H2 names from the template>]
```

If a skill has genuinely skill-unique teaching guidance (a "before you start, decide X" prompt; a routing gate the engineer must pass before content elicitation; a write-vs-no-write distinction unique to that skill's lifecycle), preserve that guidance verbatim beneath the parameter manifest. Skill-unique prose lives at the skill; the ritual lives here.

## Per-skill migration checklist

When refactoring an existing authoring skill to this substrate:

- [ ] Confirm the skill already cites `_lib/mode_dispatcher.md` (the sibling substrate). If not, add the citation per the mode-dispatcher migration checklist first.
- [ ] Replace the existing `## Teaching Mode` body with the recommended skill-side template above.
- [ ] Fill in `artifact_kind`, `template_path`, `methodology_section`, `exemplar_paths`, and `required_sections` from the skill's prior Teaching Mode body (do not re-derive — the prior body already enumerated them).
- [ ] If the skill had skill-unique teaching prose (e.g., write-ae's AE-Classifier routing gate, write-ggc's two-path log-vs-add-term distinction, write-mission's near-immutable-vs-live split, write-sp's loud-placeholder discipline), preserve that prose verbatim beneath the parameter manifest.
- [ ] Run `pytest tests/test_skills_dispatcher.py` — must be green. The dispatcher tests assert that the `## Teaching Mode` H2 still exists in every authoring skill; they do not assert on the body shape.

## Reconsideration triggers

This substrate's contract should be revisited if:

- A new artifact kind enters DekSpec (per ADR-011) whose Teaching Mode genuinely does not fit the 4-step ritual (e.g., an artifact whose template has no required sections, or one whose authoring is non-interactive by design). Add a documented exemption here, then introduce the artifact's skill.
- The 4-step ritual in practice degrades into a fancy `--review` (i.e., engineers never actually use it as a tutorial, only as a slow audit). Either sharpen the prose to make the tutorial intent louder, or merge `--teaching` into `--review` and update the dispatcher substrate accordingly.
- Skills end up with so much skill-unique teaching prose beneath the parameter manifest that the substrate is providing little value (sign the substrate is under-fitting). Promote the common shapes back into this file and reduce the divergence.

## Links

- `_lib/mode_dispatcher.md` — the sibling substrate that defines the universal mode catalog (Teaching Mode is one of the four universal modes).
- INT-008-multi-mode-skills-dispatcher.md — the parent Intent for the dispatcher + teaching-mode substrates.
- ds-int-007-multimode-skills-znn — tracker bead.
- AE-006 Skills Library — the AE this substrate lives within.
