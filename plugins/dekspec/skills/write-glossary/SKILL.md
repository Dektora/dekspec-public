---
name: write-glossary
description: Own the domain glossary — extract glossary-term candidates from a corpus (proposes only; never auto-writes), add a canonical term directly after a duplicate + synonym check, and compose the glossary row when the corrections pipeline promotes an entry at the recurrence threshold. The glossary half of the terminology pipeline; corrections live in /dekspec:write-corrections.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --extract | --add-term] [term details or corpus path]
related_skills: [write-corrections, doctor, interview-me, setup-dekspec]
---

Own `dekspec/domain-glossary.md` — the project's canonical vocabulary. This skill captures
candidate terms from a corpus, adds terms directly, and composes the glossary row when the
corrections pipeline promotes an entry.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Scope — where the glossary ends

This skill is one half of a two-artifact pipeline (INT-191). It owns the glossary and nothing else:

| Concern | Owner |
|---|---|
| Glossary-term capture from a corpus (`--extract`) | this skill |
| Direct term add, duplicate + synonym check (`--add-term`) | this skill |
| Composing / enriching a glossary row on promotion | this skill (§Promotion Hand-Off) |
| Logging a correction, counting recurrences, the 3-recurrence threshold | `/dekspec:write-corrections` |
| Walking open corrections interactively | `/dekspec:write-corrections` |
| Glossary structural health (duplicates, missing definitions, dangling aliases) | the audit engine — `dekspec doctor` (§Glossary Structural Health) |

Do not log a correction from here and do not re-implement a health check the engine already runs.
Route those out; the routing targets are named in each section below.

## Starter Prompt

```prompt
/dekspec:write-glossary --add-term "Term: shadow timeline. Definition: In-memory cache in front of PostgreSQL for timeline data. NOT this: not a secondary cache. Code convention: shadow_timeline. Category: Graph & Storage"

Add this term. Run the duplicate + synonym check first and stop if it already exists.
```

## Fan-Out Mode

Fan-out is **deliberately deferred** for `write-glossary` (see ds-di2 OI-2 and [`_lib/fan_out.md`](../_lib/fan_out.md) §"When NOT to use fan-out"). Manifest for this skill:

- **subagent_type**: n/a (deferred)
- **substantive_modes**: [] (no modes fan out today)
- **inline_modes**: [`--help`, `--teaching`, `--extract`, `--add-term`] — every mode runs inline in the parent session.

**Reasoning** (per the substrate's deferral rationale):

- `--extract` requires PER-CANDIDATE engineer confirmation before routing any candidate into `--add-term` or the corrections pipeline; that engineer-in-the-loop triage is exactly the signal a fresh-context subagent would lose.
- `--add-term` has a synonym-match step (Step 3) that waits for the engineer's response before deciding whether to add a separate entry or update an existing one.
- `--teaching` and `--help` are engineer-facing prose, never fanned out.

The interactive synonym disambiguation relies on iterative back-and-forth that fresh-context subagents cannot replicate without losing the engineer-in-the-loop signal that makes the pipeline useful.

**Trigger to revisit:** if a non-interactive batch mode is ever added (e.g. `--add-term --batch <file>` that bulk-adds terms whose synonym checks have already been resolved), fan that mode out at that time per the standard ds-di2 pattern. Until then, keep `write-glossary` fully inline.

**End of Fan-Out Mode.**

**Roles (ADR-061).** This skill plays DekSpec's Agent Role Specifications; the engineer never selects one. Authoring, revise and resync modes play the **`specifier`** role, audit modes the **`auditor`** role: run `dekspec resource role specifier` or `dekspec resource role auditor` at the start of the mode and follow it (a delegated `*-author` agent loads `specifier` itself). See [`_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) §The role each universal mode plays and [`_lib/agent_roles.md`](../_lib/agent_roles.md).

## Mode Detection

Parse `$ARGUMENTS` for flags. If a flag is present, strip it and enter the corresponding mode.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Extract mode** — `--extract` flag. Skip to **Extract Mode**.
- **Add-term mode** — `--add-term` flag. Skip to **Add-Term Mode**.
- **Provisional modifier** — `--provisional <slug>`. Not a standalone mode: strip the flag pair, then run the selected write mode against the staged copy. See **Provisional Mode (Singleton)**.

If no flag is present, display help.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:write-glossary"
one_line:   "Own the domain glossary — capture candidates, add terms, compose promoted rows"
modes:
  - { flag: "--extract", args: "[corpus path | text]", description: "Extraction capture stage. Scans a corpus (conversation + governed-artifact folders) for glossary-term candidates and PROPOSES a 3-way disposition per candidate: canonical-now (handoff to --add-term), ambiguous (seed a correction via /dekspec:write-corrections), or drop. NEVER writes the glossary and never auto-promotes; requires per-candidate engineer confirmation before routing. Corpus boundary: IN = conversation + dekspec/{architecture-elements,intents,missions,adrs,working-specs,interface-contracts,impl-briefs}/; OUT = source code, tooling/, plugins/ code, comments." }
  - { flag: "--add-term", args: "<details>", description: "Add a term directly to the glossary, bypassing the recurrence pipeline. Use for front-loaded terms the engineer knows are canonical. Checks for duplicates and synonym conflicts before adding. Fields: term, canonical definition, NOT this, code convention, category." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through adding a glossary term (--add-term) and explaining how the 3-recurrence promotion pipeline delivers rows here from the corrections side." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:write-glossary --add-term \"Term: shadow timeline. Definition: In-memory cache in front of PostgreSQL for timeline data. NOT this: not a secondary cache. Code convention: shadow_timeline. Category: Graph & Storage\""
  - "/dekspec:write-glossary --extract \"<conversation or governed-artifact corpus>\""
  - "/dekspec:write-glossary --teaching"
  - "/dekspec:write-glossary --help"
extra_sections:
  - heading: "NOT THIS SKILL"
    body:
      - "Logging a correction, recurrence counting, the"
      - "3-recurrence threshold, and walking open corrections:"
      - "/dekspec:write-corrections."
      - "Glossary structural health (duplicate terms, missing"
      - "definitions, dangling aliases, coverage): the audit"
      - "engine — run `dekspec doctor`."
  - heading: "TYPICALLY CALLED BY"
    body:
      - "The engineer directly for --add-term and --extract."
      - "/dekspec:write-corrections, which hands over a promoted"
      - "correction for this skill to compose into a glossary row."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: glossary term (a row in `dekspec/domain-glossary.md`)
- **template_path**: `templates/glossary-template.md`
- **methodology_section**: §Terminology pipeline of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/domain-glossary.md`
- **required_sections**: per row — [term, canonical_definition, not_this, code_convention, category]

**Skill-unique shape — Teaching Mode is read-only here, no artifact written:**

Glossary rows are appended into an existing living document; there is no draft state, so Teaching Mode departs from the canonical ritual's "write artifact to disk at DRAFT status" close. Walk the contract without performing the write:

1. Explain the row shape (Term / Canonical Definition / NOT this / Code convention) and why the "NOT this" column exists — it records the misinterpretation the term is defending against.
2. Explain the duplicate + synonym check (Add-Term Step 3) and why an exact match STOPS rather than adding a second row.
3. Explain the two routes a row can arrive by: `--add-term` (direct, engineer knows it is canonical) and promotion (a correction reaching 3 recurrences in `/dekspec:write-corrections`, handed here to compose the row). The threshold is a system constant, not a knob.
4. Prompt the engineer to draft one example row; validate its shape; do NOT write it.

On exit, summarize the contract the engineer just learned plus the real command they would run to actually add the term.

## Extract Mode

Extraction is the **capture stage** that sits in FRONT of the two promotion paths. It scans a corpus for glossary-term candidates and PROPOSES a disposition for each — it adds **no new writer and no new promotion threshold**. Every actual write still flows through `--add-term` (direct glossary add) or the 3-recurrence pipeline in `/dekspec:write-corrections`; those two remain the ONLY glossary writers.

### Hard invariant — no auto-write

Extraction **NEVER writes `dekspec/domain-glossary.md` directly, and there is NO auto-`--add-term`.** The capture stage only PROPOSES dispositions; nothing reaches the glossary without per-candidate engineer confirmation routed through the existing paths. State this to the engineer up front. The runnable teeth for this invariant live in the extraction outcome test (the helper is byte-checked to leave the glossary unchanged).

### Corpus boundary (pinned)

- **IN** — the supplied conversation text + the governed-artifact folders: `dekspec/architecture-elements/`, `dekspec/intents/`, `dekspec/missions/`, `dekspec/adrs/`, `dekspec/working-specs/`, `dekspec/interface-contracts/`, `dekspec/impl-briefs/`.
- **OUT** — source code, `tooling/`, `plugins/` code, and code comments (codebase-audit overlap, D20).

Do not widen the corpus past this boundary; source-symbol normalization is the codebase-audit's job, not the glossary capture stage's.

### Step 1: Assemble the Corpus

Gather the IN-boundary text: the current conversation/correction context plus any governed-artifact files the engineer points at (restricted to the folders above). Never read source code, `tooling/`, or `plugins/` code into the corpus.

### Step 2: Run the No-Auto-Write Helper

Run `scripts/extract_candidates.py` (in this skill's folder) with the assembled corpus, e.g.

```bash
scripts/extract_candidates.py "<corpus text>" --glossary dekspec/domain-glossary.md
```

(or pipe the corpus on stdin). The helper is deterministic and **read-only** with respect to the glossary — `--glossary` is consulted only to drop candidates the glossary already covers; it is never written. It returns JSON mapping each candidate to a 3-way disposition with a routing payload:

- **`canonical-now`** (`route: --add-term`) — a de-facto term used consistently with no conflicting senses and not already in the glossary. Payload is an `--add-term` handoff.
- **`ambiguous`** (`route: --log`) — a term used with conflicting / overloaded senses. It must NOT be promoted as a single canonical term; it earns promotion only via the existing 3-recurrence pipeline in `/dekspec:write-corrections`. Payload is a correction seed.
- **`drop`** — noise (low-frequency, stopword-dominated, or already covered). Discarded.

### Step 3: Present Candidates and Triage Per-Candidate

Present each non-dropped candidate with its proposed disposition and the helper's rationale, then **require PER-CANDIDATE engineer confirmation** before any routing:

```
EXTRACTION CANDIDATES (proposed — nothing written yet)
───────────────────────────────────────
[1/N] "[candidate]"  →  proposed: [canonical-now | ambiguous]
      [helper rationale]
      Route on confirm: [--add-term | /dekspec:write-corrections]
───────────────────────────────────────
Confirm (canonical-now → --add-term), reclassify (→ corrections), or drop?
```

Wait for the engineer's decision on each candidate. The engineer may override the proposed disposition (e.g. reclassify a `canonical-now` as `ambiguous`, or drop a candidate entirely). Nothing is written until they confirm.

### Step 4: Route Confirmed Candidates Into the Existing Paths

For each candidate the engineer confirms:

- **canonical-now** → enter this skill's **Add-Term Mode** with the handoff payload. That path runs its own duplicate/synonym check (Add-Term Step 3) and is the writer.
- **ambiguous** → hand the correction seed to `/dekspec:write-corrections`. The term enters the recurrence pipeline and is promoted only when it crosses the 3-recurrence threshold — never directly. Do not write the correction log from here.
- **drop** → discard; no write.

Extraction itself performs no glossary write — it only hands confirmed candidates to `--add-term` or to the corrections pipeline.

### Step 5: Report

```
EXTRACTION CAPTURE COMPLETE
Candidates proposed: [N]  (canonical-now [a], ambiguous [b], drop [c])
Routed to --add-term:      [list]
Seeded via write-corrections: [list]
Dropped:                   [count]

The glossary was not written by extraction. Confirmed candidates were routed
to the existing --add-term / corrections paths, which remain the only writers.
```

**End of Extract Mode.**

## Add-Term Mode

Add a term directly to the glossary, bypassing the recurrence pipeline. Use when the engineer knows a term is canonical and wants it in the glossary immediately — no correction entry, no recurrence tracking.

### Step 1: Parse Input

Extract from the arguments:
- **Term** — the canonical name (required)
- **Canonical Definition** — what the term means in this system (required)
- **NOT this** — common misinterpretations to avoid (required — if there are none yet, use `—`)
- **Code convention** — the variable/function naming pattern, or `—` if not applicable
- **Category** — which glossary section the row belongs in. Categories are per-project: read the H2 headings of `dekspec/domain-glossary.md` and use one of them (required)

If any required field is missing, ask.

### Step 2: Read Glossary

1. Read `dekspec/domain-glossary.md`

### Step 3: Duplicate and Synonym Check

Before adding, verify this term doesn't already exist. Run
`scripts/glossary_ops.py find-synonym "<term>"` (in this skill's folder) — it
returns candidate glossary rows (and corrections-log slugs) whose text overlaps
the term. Global options precede the subcommand:

```bash
scripts/glossary_ops.py --glossary dekspec/domain-glossary.md find-synonym "<term>"
```

The script is a word-overlap heuristic; the AI judges which candidates, if any, are true matches:

- **Exact match** — a candidate row has the same Term. STOP: "This term already exists in the glossary under [category]. Run `dekspec doctor` to review glossary health, or edit the glossary directly."
- **Synonym match** — a candidate row defines the same concept under a different name. Present both: "The glossary already has [existing term] which appears to cover the same concept. Add anyway as a separate entry, or update the existing entry?" Wait for engineer response.
- **No match** — no candidate is a true match; proceed.

A corrections-log slug in the results is context, not a blocker: it means the concept is already in the recurrence pipeline. Tell the engineer, and let them decide between front-loading the term here and letting the pipeline promote it.

### Step 4: Add to Glossary

1. Determine the correct category table in the glossary.
2. Add a new row, matching the table's existing column shape:
   - Term tables (most categories): `| **[Term]** | [Canonical Definition] | [NOT this] | [Code convention] |`
   - A constraints table: `| [Constraint] | [Value] | [Rationale] |`
   - A rules table: `| [Rule] | [Rationale] |`
3. Update the glossary's **Modified** date.
4. Add an Amendment Log entry: `| [today] | Addition | Added term: [Term] | engineer |`

### Step 5: Report

```
TERM ADDED: [Term]
Category: [category]
Definition: [canonical definition]
NOT this: [not this]
Code convention: [code convention]
```

**End of Add-Term Mode.**

## Promotion Hand-Off

Not a flag — the entry point `/dekspec:write-corrections` calls when a correction reaches the
3-recurrence threshold. The corrections side owns the threshold and the decision to promote; this
skill owns composing and writing the resulting row. The seam is the `promote` helper's return
value: it flips the correction's status and returns the entry's Correction text so the glossary
row can be composed from it.

On receiving a promotion hand-off (slug + correction text + category):

1. Read `dekspec/domain-glossary.md` to determine the correct category table and check for an
   existing row covering the concept.
2. **If a matching term already exists:** update the row — enrich the "NOT this" column with the
   correction's insight if it adds information not already present. Do not add a second row.
3. **If no matching term exists:** add a new row to the appropriate category table:
   - **Term** — derive from the correction
   - **Canonical Definition** — the correct understanding
   - **NOT this** — the common misinterpretation that keeps recurring
   - **Code convention** — if applicable, otherwise `—`

   Composing the row (Term / Canonical Definition / NOT this) is an AI judgment step.
4. Update the glossary's **Modified** date and add an Amendment Log entry.
5. Return to the caller: the slug, the category, and whether a row was added or an existing row
   was enriched. The caller reports the promotion; this skill does not also announce it.

The corrections-side status flip is **not** this skill's write. Do not edit
`dekspec/terminology-corrections.md` from here — if the hand-off arrives without the status
already flipped, say so and hand it back rather than writing the other artifact.

**End of Promotion Hand-Off.**

## Audit Mode

_Plays the **`auditor`** role — run `dekspec resource role auditor` first and follow it: deterministic `dekspec validate` / `dekspec audit` output is primary evidence; report findings, change nothing._

Glossary structural health is an **engine** concern, not a prose one. This mode is a thin router:
it runs the authoritative check and reads back its findings. It deliberately implements no checks
of its own.

Run:

```bash
dekspec doctor --at .
```

The L10 rule family covers it: `T-GLOSSARY-DUPLICATE` (two rows defining the same term),
`T-GLOSSARY-MISSING-DEFINITION` (a row with no canonical definition),
`T-GLOSSARY-DANGLING-ALIAS` (an alias pointing at no term), and `LINK-GLOSSARY-COVERAGE`
(Title-Case domain terms used in artifacts but undefined here).

Report the findings that name `DOMAIN-GLOSSARY` or a glossary term, verbatim, and stop.

INT-191 removed the prose re-implementation of these checks that the predecessor skill carried:
two checkers of one property drift apart, and only one of them runs in CI. When a glossary-health
question comes up, run `dekspec doctor` and read its findings; do not hand-roll an equivalent pass
in this skill.

Cross-artifact consistency between the glossary and the corrections log is likewise engine-owned
(`LINK-CORRECTIONS-GLOSSARY-*`, `T-TERM-VARIANT-COLLISION`).

**No `--review` mode.** Review Mode walked open *correction* entries — recurrence counts, promotion
status. The glossary has no open-issue concept, so there is nothing to walk. Recorded as a
documented exemption in `tests/test_skills_dispatcher.py::_UNIVERSAL_MODE_EXEMPTIONS`, not an
oversight.

## Provisional Mode (Singleton)

`--provisional <incubation-slug>` stages a copy of the glossary singleton inside `dekspec/provisional/<incubation-slug>/` instead of editing the canonical at `dekspec/domain-glossary.md`. Singletons follow the same CoW discipline as numbered artifacts — the difference is that the `replaces:` field uses the canonical filename rather than a `<KIND>-NNN` ID.

Use this mode when:
- The glossary change is exploratory and might be abandoned before ratification.
- Multiple Intents in the same incubation folder co-vary with the glossary change.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding.
2. CoW the singleton via the auto-stage verb:
   ```
   dekspec library cow-stage dekspec/domain-glossary.md --incubation <slug>
   ```
   The verb copies the singleton into `dekspec/provisional/<slug>/<basename>-provisional.md`, stamps `replaces: domain-glossary` in YAML frontmatter, and returns the new path.
3. **Populate the staged copy with this skill's authoring discipline** — every row the canonical-mode flow would add goes here. The PROVISIONAL banner at the top stays.
4. **Reject `--lock` / `--accept`** in combination with `--provisional`. The singleton's canonical replacement runs as part of the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)), not from this skill body.
5. Closing step: surface the provisional path, the branch (if `dekspec library new-provisional` was used earlier), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** singleton — guards `dekspec/domain-glossary.md`.

## Rules

- `dekspec/domain-glossary.md` is the only artifact this skill writes. The corrections log belongs to `/dekspec:write-corrections`; never edit it from here.
- The promotion threshold is 3 recurrences and it is not this skill's to apply. This skill composes the row it is handed; the corrections side decides when a row is earned.
- Extraction proposes; it never writes. `--add-term` and the promotion hand-off are the only glossary writers.
- The glossary is the authoritative source once a term lands. If a glossary row and a correction entry contradict each other after promotion, the glossary wins.
- Maintain the glossary's existing table format and category organization. Do not add a new category section without engineer approval.
- Glossary categories are per-project — read the file's H2 headings rather than assuming a category list.
- Glossary structural health is `dekspec doctor`'s job. Do not re-implement it here.

## Common Pitfalls

- Don't match terms on string equality — match on meaning. "co-occurrence" vs "cooccurrence" and "token merging" vs "wave compression" are the *same* concept; a second row for a synonym splits the vocabulary the glossary exists to unify.
- Don't `--add-term` a concept the glossary already covers — run the Step 3 duplicate/synonym check first and STOP on an exact match. A repeated misuse of an already-defined term is a correction, not a second glossary row: route it to `/dekspec:write-corrections`.
- Don't auto-write from `--extract`. A candidate the helper labels `canonical-now` is a proposal; per-candidate engineer confirmation is the invariant, and the outcome test byte-checks the glossary is untouched.
- Don't widen the extraction corpus to source code or `tooling/` / `plugins/` — symbol normalization is the codebase-audit's job.
- Don't skip the `dekspec library cow-stage` guard before editing `dekspec/domain-glossary.md` — a direct canonical edit while a pre-ACCEPTED Intent claims the path trips `T-COW-CANONICAL-EDITED` (P2).
- Don't write an artifact in Teaching Mode — it is read-only; validate the engineer's draft row shape and exit without touching the glossary.
- Don't answer a "is the glossary healthy?" question by inspection — run `dekspec doctor` and report its L10 findings.

## Verification Checklist

- [ ] Correct mode was entered from the flag, or help was shown when no flag was present.
- [ ] In `--extract`: the corpus stayed inside the pinned IN boundary, every candidate got an explicit engineer decision, and the glossary was not written by the capture stage.
- [ ] In `--add-term`: the Step 3 duplicate + synonym check ran via `scripts/glossary_ops.py find-synonym` and STOPPED on an exact match; no duplicate glossary row was added.
- [ ] On a promotion hand-off: exactly one row was added or enriched, and `dekspec/terminology-corrections.md` was not edited from this skill.
- [ ] Any edit to `dekspec/domain-glossary.md` was preceded by the `dekspec library cow-stage` guard (or correctly fell through to direct-flow on exit 1).
- [ ] The glossary **Modified** date and Amendment Log were updated on any run that actually changed the file.
- [ ] For substantive modes, `dekspec relink` was run against the repo root as the final action.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write a glossary row — `--add-term`, and the promotion hand-off). After the glossary file is saved and any index update is done, run:

```
dekspec relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
