# DekSpec Multi-Mode Dispatcher — Canonical Pattern

**Status:** AUTHORITATIVE (per ds-int-007-multimode-skills-znn / INT-008-multi-mode-skills-dispatcher).
**Audience:** DekSpec skill authors. Every authoring skill at `skills/write-*/SKILL.md` cites this file and inlines the canonical mode-dispatch prose below.
**Lineage:** Pattern derived from the `write-evals` 8-mode shape (creation + --audit / --review / --resync / --revise / --accept / --dry-run / --help) per Papalini ch. 12 §12.6 *Multi-Mode Agents*. Parameterized for per-artifact lifecycle differences (e.g., L2 artifacts add --lock/--unlock; ADRs add --supersede; Intents add --decompose/--testpass; Missions add --activate/--complete/--kill).

---

## Why this file exists

Before this substrate landed, every authoring skill rolled its own mode-detection prose. Three concrete consequences:

1. **Mode semantics drifted across skills.** `--audit` was interactive in some, pure read in others. `--review` walked open issues in some, was an alias for `--audit` in others. Engineers learning the skill family had to re-learn the contract per skill.
2. **New modes had to be added in N places.** Introducing `--teaching` to one skill required hand-copying the prose into 11 others, each with a different surrounding context.
3. **No canonical reference for "what does mode X mean."** When the skill author and the engineer disagreed about whether `--accept` should block on audit findings, the question had to be re-litigated per skill — there was no source of truth.

This file is the source of truth. Each authoring SKILL.md cites it at the top, inlines the canonical mode-dispatch block parameterized for that skill's mode catalog, and follows the per-mode contract below. A lint test (`tests/test_skills_dispatcher.py`) enforces citation + universal-mode presence + canonical-block shape.

## Universal modes (every authoring skill MUST support)

Every authoring skill ships with **at minimum** these four modes:

| Flag | Purpose | Read-only? | Gates? |
|------|---------|-----------|--------|
| (no flag) | **Creation** — author a brand-new artifact from a description + the engineer's notes. | No (writes new file) | No |
| `--audit` | **Audit** — re-check an existing artifact against its template + linkage rules. Reports findings without changes. | **Yes** | No (but blocks subsequent `--accept` if findings are critical/important) |
| `--review` | **Review** — interactive walk-through of an artifact's `## Open Issues` (or equivalent) section. Resolves one item at a time with the engineer. | No (edits the artifact in place) | No |
| `--teaching` | **Teaching** *(per ds-int-007 / INT-008)* — interactive tutorial walking a new author through this artifact kind. Explains each section's purpose, shows an exemplar, and prompts the engineer for the content section-by-section. Distinct from `--review` (which audits existing content) and from no-flag creation (which assumes the author already knows the artifact). | No (writes new file) | No |
| `--help` | Display the canonical USAGE / MODES / EXAMPLES block (see *Help Mode template* below) and stop. | Yes | No |

## Lifecycle-bound modes (skills MAY support, depending on artifact)

| Flag | Purpose | Where it applies | Read-only? | Gates? |
|------|---------|------------------|-----------|--------|
| `--accept` | Promote PROPOSED → ACCEPTED. Requires clean audit (no critical/important findings). | All L0/L1/L2/L3 lifecycle artifacts. Intents call it after `--testpass`. | No | Yes (refuses if audit dirty) |
| `--lock` | Promote ACCEPTED → LOCKED (or MERGED → LOCKED for Intents). | L0/L1/L2 lifecycle artifacts + Intents. | No | Yes (refuses if not in source status) |
| `--unlock` | Move LOCKED → PROPOSED for substantive edits. Logs the unlock in Amendment Log. | L0/L1/L2 lifecycle artifacts. | No | Yes (refuses if not LOCKED) |
| `--revise` | Edit an existing artifact while preserving status. For LOCKED artifacts, requires prior `--unlock`. | Most authoring skills. | No | Soft (warns if status changes are needed) |
| `--resync` | Re-derive an artifact after its source upstream changed (e.g., IB resynced after WS update). Compares current to updated source; proposes deltas. | Skills whose artifact is derived from an upstream (write-ibs, write-evals, write-constitution, occasionally write-ws). | No (edits) | No |
| `--dry-run` | Preview what creation/revision would do without writing. Useful for scope validation. | Bead-bound skills (write-ibs, write-evals, write-tests). | **Yes** | No |
| `--deprecate` | Mark an artifact DEPRECATED (terminal status). Adds Deprecation Note. | All lifecycle artifacts. | No | Soft (no-op if already DEPRECATED) |

## Artifact-specific modes (used by exactly one or two skills)

| Flag | Skill(s) | Purpose |
|------|----------|---------|
| `--supersede` | write-adr, write-mission | Mark this artifact superseded by a newer one of the same kind. Records `superseded_by` linkage. |
| `--analyze` | write-intent | Read-only top-down coverage check + bottom-up archaeology + decomposition recommendation. |
| `--decompose` | write-intent | Split an OVERSIZED Intent into child Intents under a Mission. |
| `--testpass` | write-intent | Promote IMPLEMENTING → TESTPASS after the verification predicate evaluates true. |
| `--sync` | write-intent | Re-derive Intent fields after upstream AE/ADR changes. (Distinct from `--resync` in derived-from-IB skills.) |
| `--amend` | write-intent | Add an Amendment Log entry without changing status (post-LOCK editorial edits). |
| `--approve` | write-ibs | Alias for `--accept` that also runs `--dry-run` first. (Legacy; consider unifying under `--accept` in a future commit.) |
| `--activate` | write-mission | Promote TODO → ACTIVE Mission. Requires at least one child Intent LOCKED (L8). |
| `--complete` | write-mission | Promote COMPLETING → COMPLETE. Requires every child Intent LOCKED + Mission Verification predicate true. |
| `--kill` | write-mission | Terminal KILLED. Records kill reason + executed rollback steps. |
| `--log` | write-ggc | Append a correction entry to `guidance-and-corrections.md`. |
| `--add-term` | write-ggc | Promote a recurring correction to a glossary term. |
| `--all`, `--integration` | write-tests | Test-tier selectors (run-all vs integration-only). |

## Canonical Mode-Detection prose (inline this in your SKILL.md)

Inline the block below in each SKILL.md's `## Mode Detection` section, parameterized for that skill's mode catalog:

```
## Mode Detection

This skill follows the DekSpec multi-mode dispatcher pattern documented in
`skills/_lib/mode_dispatcher.md`. Parse `$ARGUMENTS` for flags in this order:

1. If `--help` is present, skip to **Help Mode** and stop.
2. If any of [LIST THIS SKILL'S NON-CREATION FLAGS] is present, strip it and
   skip to the corresponding mode (e.g., `--audit` → Audit Mode).
3. If `--teaching` is present, skip to **Teaching Mode**.
4. Otherwise, proceed with **Creation Mode**.

If the argument doesn't fit any recognized pattern (e.g., a path to an
unfamiliar file, or a flag this skill does not implement), ask the engineer
what they want to do — don't guess.

**Mode-flag contract:** the universal modes (`--audit`, `--review`,
`--teaching`, `--help`) behave per the contract in
`skills/_lib/mode_dispatcher.md`. The lifecycle / artifact-specific flags
above are described in their own sections below; their semantics deliberately
do not diverge from the substrate's general contract.
```

## Canonical Help Mode template (inline this in your SKILL.md)

```
## Help Mode

Display this and stop:

\`\`\`
/<skill-name> — <one-line description matching the front-matter `description` field>

USAGE:
  /<skill-name> [FLAG] <target> [notes]

MODES:
  (no flag) <target>           <Creation mode description>

  --audit <target>             <Audit mode description — what it reports;
                                whether findings block --accept>

  --review <target>            <Review mode description — interactive walk-
                                through>

  --teaching <kind-or-target>  <Teaching mode description — interactive
                                tutorial for new authors>

  --<lifecycle-flag> <target>  <Lifecycle mode descriptions (--accept,
                                --lock, --unlock, --revise, etc.)>

  --<artifact-specific>        <Artifact-specific mode descriptions
                                (--decompose, --supersede, etc.)>

  --help                       Show this help message.

EXAMPLES:
  /<skill-name> <typical-target>
  /<skill-name> --audit <target>
  /<skill-name> --teaching <kind-or-target>
\`\`\`

**End of Help Mode.**
```

## Canonical Teaching Mode template

```
## Teaching Mode

Trigger: `--teaching` flag. Audience: an engineer authoring their first
artifact of this kind in this repo.

The mode walks the engineer through authoring a new <artifact-kind>
section-by-section. For each required section in the template:

1. Explain the section's purpose in 1-3 sentences (cite the template +
   the methodology doc section if applicable).
2. Show one or two short exemplars drawn from existing artifacts in
   `dekspec/` (or `tests/fixtures/` if none exist yet).
3. Prompt the engineer for the content. Accept inline text or "skip" to
   leave a placeholder.
4. If the engineer provides content that fails a structural check
   (template format, required field, glossary term not defined), call it
   out immediately with the rule that fired — do not silently accept.

After every required section is filled (or explicitly skipped), the mode
exits with a summary listing:
- Sections completed
- Sections skipped (placeholder text inserted; engineer can fill via `--revise`)
- Open Issues filed for any structural-check failures

The artifact is written to disk at DRAFT status. Engineer reviews with
`--review`, audits with `--audit`, promotes via `--accept` (and so on per
the artifact's lifecycle).

**Distinct from `--review`:** review walks an existing artifact's open
issues; teaching walks a brand-new artifact's required sections.

**Distinct from creation (no flag):** creation assumes the engineer knows
the artifact kind and can supply content from a description; teaching
assumes the engineer is new and needs section-by-section guidance.
```

## Per-skill migration checklist

When refactoring an existing authoring skill to the substrate:

- [ ] Add a top-of-file citation: `**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics.`
- [ ] Replace the existing `## Mode Detection` block with the canonical Mode-Detection prose above, parameterized for this skill's modes.
- [ ] Replace the existing `## Help Mode` block with the canonical Help Mode template, populated with this skill's mode descriptions + examples.
- [ ] Add a `## Teaching Mode` section using the canonical Teaching Mode template, parameterized for this skill's artifact kind.
- [ ] Update the front-matter `argument-hint` to include `--teaching` and to order flags as `[--help | --teaching | <universal-modes> | <lifecycle-modes> | <artifact-specific-modes>]`.
- [ ] Confirm the skill's mode-specific sections (Audit Mode, Review Mode, Accept Mode, ...) remain functional and that their internal cross-references to mode flags still resolve.
- [ ] Run `pytest tests/test_skills_dispatcher.py` — must be green.

## Reconsideration triggers

This substrate's contracts should be revisited if:

- A new artifact kind enters DekSpec (per ADR-011) that needs a mode not enumerable in the lifecycle / artifact-specific tables above. Add it to the table here first, then introduce it in the new kind's skill.
- The `--teaching` mode in practice degrades into a copy of `--review` (sign that the distinction isn't load-bearing for users). Either merge the modes or sharpen the teaching prose.
- Skills end up with substantially more skill-specific divergence than this substrate captures (sign that the substrate is under-fitting). Document the new shared shape here and reduce the divergence.

## Links

- INT-008-multi-mode-skills-dispatcher.md (the parent Intent for this work)
- ds-int-007-multimode-skills-znn (tracker bead)
- Papalini ch. 12 §12.6 (source pattern)
- AE-006 Skills Library (the AE this substrate lives within)
