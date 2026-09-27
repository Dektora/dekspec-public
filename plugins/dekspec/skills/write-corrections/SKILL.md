---
name: write-corrections
description: Manage the terminology corrections log — record a misinterpretation, count its recurrences, walk open entries interactively, audit the log's structural health, and hand an entry that crosses the 3-recurrence threshold to /write-glossary for promotion.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --log | --review | --audit] [correction text]
related_skills: [write-glossary, write-adr, write-ae, write-ic, write-ws, write-ibs]
---

Own the corrections half of the terminology pipeline: `dekspec/terminology-corrections.md`. Record a misinterpretation, count how often it recurs, and when it crosses the threshold, hand it to `/dekspec:write-glossary` to become a defined term.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Scope — what this skill is not

INT-191 split the retired `write-ggc` skill in two. The partition is by artifact:

| | |
|---|---|
| This skill writes | `dekspec/terminology-corrections.md` |
| `/dekspec:write-glossary` writes | `dekspec/domain-glossary.md` |

Two consequences that matter at every step below:

1. **This skill never writes the glossary.** Not on promotion, not on audit, not on review. When an entry earns promotion, this skill flips its status and hands the correction text over; composing and writing the glossary row is `/dekspec:write-glossary`'s job. That is the seam, and `scripts/corrections_ops.py promote` sits exactly on it.
2. **Cross-artifact checks belong to the audit engine, not to this skill.** Glossary structural health, corrections ↔ glossary consistency, promotion-pipeline completeness, whole-corpus terminology compliance and pipeline wiring are rules in `tooling/dekspec/fidelity_audit/linkage.py`, reached by `dekspec doctor`. This skill's `--audit` covers the corrections log's own structural health and nothing beyond it. Re-implementing an engine rule in prose here is the duplication INT-191 removed.

## Starter Prompt

```prompt
/dekspec:write-corrections --log "Assembly was described as compressing nodes in the WS-014 draft. Assembly does not compress — it only concatenates pre-budgeted segments. Source: WS-014. Category: Architecture"

Log this correction. If it crosses the 3-recurrence threshold, mark it promoted and hand the correction text to /dekspec:write-glossary.
```

## Fan-Out Mode

Fan-out is **deliberately deferred** for `write-corrections` (see ds-di2 OI-2 and [`_lib/fan_out.md`](../_lib/fan_out.md) §"When NOT to use fan-out"). Manifest for this skill:

- **subagent_type**: n/a (deferred)
- **substantive_modes**: [] (no modes fan out today)
- **inline_modes**: [`--help`, `--teaching`, `--log`, `--review`, `--audit`] — every mode runs inline in the parent session.

**Reasoning** (per the substrate's deferral rationale):

- `--log` is multi-turn correction work. Step 3 (Match Against Existing Entries) explicitly pauses on partial matches to ask the engineer whether two corrections are the same; Step 5 (Promote) reads recurrence-count state that lives in the corrections log and must be read/written transactionally with the engineer's confirmation context.
- `--review` and `--audit` are already on the preserve-inline list per `ds-di2`.
- `--teaching` and `--help` are engineer-facing prose, never fanned out.

The recurrence semantics rely on iterative back-and-forth that fresh-context subagents cannot replicate without losing the engineer-in-the-loop signal that makes the pipeline useful.

**Trigger to revisit:** if a non-interactive batch mode is ever added (e.g. `--log --batch <file>` that ingests pre-disambiguated corrections), fan that mode out at that time per the standard ds-di2 pattern. Until then, keep `write-corrections` fully inline.

**End of Fan-Out Mode.**

## Mode Detection

Parse `$ARGUMENTS` for flags. If a flag is present, strip it and enter the corresponding mode.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Log mode** — `--log` flag. Skip to **Log Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.

If no flag is present, display help.

If the arguments name a glossary operation — adding a term, extracting term candidates from a corpus, checking for a duplicate or synonym term — that is `/dekspec:write-glossary`'s surface. Say so and route there rather than improvising a glossary write here.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-corrections"
one_line:   "Log terminology corrections, count recurrences, promote at the threshold"
modes:
  - { flag: "--log", args: "<details>", description: "Log a new correction or add a recurrence to an existing one. When the recurrence count reaches the promotion threshold (3), marks the entry promoted and hands the correction text to /dekspec:write-glossary to compose the row. Details can be inline text or structured fields: correction: what was wrong and what is right source: which artifact and context category: Terminology | Architecture | Numeric Ranges | Embedding Types | Document Hierarchy" }
  - { flag: "--review", args: "", description: "Walk the open issues in the corrections log interactively. Present each issue with context and a recommendation. Engineer resolves, revises, defers, or dismisses each." }
  - { flag: "--audit", args: "", description: "Structural health check on dekspec/terminology-corrections.md: entry format, slug uniqueness, category validity, entry-section alignment, duplicate corrections, recurrence format + chronology, phantom recurrence sources, and near-threshold / stale entries. Corrections-log scope only — cross-artifact checks (glossary health, promotion completeness, corpus terminology compliance, pipeline wiring) are audit-engine rules, run via `dekspec doctor`." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through logging a correction and the recurrence-promotion pipeline. Read-only; writes nothing." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-corrections --log \"Assembly was described as compressing nodes in WS-010 draft. Assembly does not compress — it only concatenates pre-budgeted segments. Category: Architecture\""
  - "/write-corrections --review"
  - "/write-corrections --audit"
  - "/write-corrections --help"
extra_sections:
  - heading: "TYPICALLY CALLED BY"
    body:
      - "Authoring skills (write-adr, write-ae, write-ic,"
      - "write-ws, write-ibs) when they correct a"
      - "misinterpretation during creation, review, revise, or audit modes."
      - "Engineer directly for --review and --audit."
  - heading: "SIBLING SURFACE"
    body:
      - "/dekspec:write-glossary owns dekspec/domain-glossary.md —"
      - "term extraction, adding a term, duplicate/synonym checks, and"
      - "composing the row for an entry promoted from here."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: correction entry (in the terminology corrections log)
- **template_path**: the `--log` entry shape (defined inline in Log Mode Step 4b)
- **methodology_section**: §The corrections pipeline of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/terminology-corrections.md`
- **required_sections**: correction text, source artifact + context, category enum

**Skill-unique shape — Teaching Mode is read-only here, no artifact written:**

Walk the `--log` contract without performing the write. Explain the recurrence-counting model (3 recurrences → the entry is promoted and its text handed to `/dekspec:write-glossary`), show one exemplar entry from `dekspec/terminology-corrections.md`, then prompt the engineer to draft an example correction and validate its shape. Do **not** write it.

On exit, summarize the contract the engineer just learned plus the real command they would run to actually log a correction. Name `/dekspec:write-glossary --teaching` as the sibling walkthrough for the glossary side. Teaching Mode here departs from the canonical ritual's "write artifact to disk at DRAFT status" close because correction entries are append-only into an existing file; there is no draft state.

**End of Teaching Mode.**

## Log Mode

Record a correction or add a recurrence to an existing one. Hands the entry to the glossary side when the recurrence threshold is reached.

### Step 1: Parse Input

Extract from the arguments:
- **Correction** — what was wrong and what is correct (required)
- **Source** — which artifact, session, or context triggered this (required)
- **Category** — one of: Terminology, Architecture, Numeric Ranges, Embedding Types, Document Hierarchy (required)

If any required field is missing, infer it from context if unambiguous. If ambiguous, ask.

### Step 2: Read Current State

1. Read `dekspec/terminology-corrections.md`
2. Read `dekspec/domain-glossary.md` — **read-only**, to decide whether the glossary already covers the concept (Step 3b). This skill does not write it.

### Step 3: Match Against Existing Entries and Glossary

Search for the correction concept across both the corrections log and glossary terms. The same concept can appear under different names, spellings, or phrasings — match on meaning, not strings.

**3a. Match against correction entries:**
- **Exact match** — an entry with the same slug or substantially identical correction text exists. Proceed to Step 4a (add recurrence).
- **Synonym match** — an entry covers the same concept using different phrasing (e.g. "token merging" vs "wave compression", "co-occurrence" vs "cooccurrence"). Treat as the same entry. Proceed to Step 4a (add recurrence) and note the variant phrasing in the recurrence description so the pattern is visible.
- **Partial match** — an entry covers a related but not identical correction. Present both to the engineer: "This correction is related to an existing entry: [existing]. Are these the same correction, or a new one?" Wait for response.
- **No match** — continue to 3b.

**3b. Match against glossary terms:**
Before creating a new entry, check whether the glossary already addresses this correction. The glossary's Canonical Definition, "NOT this" column, and Code convention columns define the canonical form.
- **Glossary already covers this** — the correction is about a concept the glossary already defines correctly, and the mistake was using a non-canonical form. This is a compliance failure, not a new correction. Log a recurrence against the existing promoted entry if one exists. If no entry exists (the glossary term was front-loaded without one), create one with `Status: promoted to glossary [original date] (seed entry)` and log the recurrence.
- **Glossary has a related but incomplete entry** — the correction adds insight the glossary doesn't cover (a new "NOT this" pattern, a variant spelling to flag). Proceed to Step 4b (create new entry) — when it reaches threshold, the hand-off will enrich the existing glossary row.
- **No glossary coverage** — proceed to Step 4b (create new entry).

### Step 4a: Add Recurrence

Run `scripts/corrections_ops.py add-recurrence <slug> --source <source> --desc <desc>`
(in this skill's folder). It surgically appends the dated recurrence line under
the entry's `- **Recurrences:**` list, recomputes the count, and returns JSON
with `count` and `promote_ready` (`true` when `count` ≥ 3). Surface stderr on a
non-zero exit (e.g. unknown slug, missing corrections log).

1. If `promote_ready` is `true`: proceed to **Step 5: Promote**.
2. If `false`: report:
   ```
   RECURRENCE LOGGED: [entry slug]
   Count: [N]/3
   Source: [source]
   ```

### Step 4b: Create New Entry

1. Generate a slug from the correction by running
   `scripts/corrections_ops.py slugify "<correction text>"` — it returns a
   lowercase, hyphenated, descriptive slug. (Creating the new entry block
   itself is an AI step — the correction text + category framing are judgment.)
2. Append a new entry to the appropriate category section:
   ```markdown
   ### [slug]
   - **Correction:** [what was wrong and what is correct]
   - **Category:** [category]
   - **Recurrences:**
     - YYYY-MM-DD — [source] — [brief description of the mistake]
   ```
3. Save and report:
   ```
   NEW CORRECTION LOGGED: [slug]
   Category: [category]
   Count: 1/3
   Source: [source]
   ```

### Step 5: Promote — the hand-off to /dekspec:write-glossary

When an entry reaches 3 recurrences it has earned a glossary row. **Owning the threshold and the decision to promote is this skill's job; composing and writing the row is not.**

1. Flip the entry's status by running `scripts/corrections_ops.py promote <slug>`
   (in this skill's folder). It surgically sets
   `- **Status:** promoted to glossary YYYY-MM-DD` and returns the entry's
   Correction text. Surface stderr on a non-zero exit.
2. Hand the returned Correction text, the category, and the recurrence count to
   **`/dekspec:write-glossary --add-term`**. That skill runs its own duplicate /
   synonym check, decides whether to add a new row or enrich an existing one,
   composes the Term / Canonical Definition / NOT this / Code convention cells,
   and bumps the glossary's **Modified** date. Do not edit
   `dekspec/domain-glossary.md` from here, even when the row seems obvious.
3. Report:
   ```
   PROMOTED: [slug]
   Category: [category]
   Recurrences: [N]
   Corrections-log status: promoted to glossary [date]
   Handed to /dekspec:write-glossary --add-term: [correction text]
   Glossary action: [reported back by /dekspec:write-glossary]
   ```

Promotion is automatic and immediate when the threshold is reached during `--log`. Do not defer it, do not ask for confirmation, and do not batch promotions. If the hand-off cannot complete in this run, say so explicitly in the report — a flipped status with no glossary row is exactly the incomplete promotion the audit engine flags.

**End of Log Mode.**

## Review Mode

Walk the open issues in the corrections log interactively — present each with context and a recommendation, resolve with the engineer one at a time.

No arguments required. Scope is `dekspec/terminology-corrections.md`; the glossary's own open issues are `/dekspec:write-glossary --review`.

### Step 1: Read State

1. Read `dekspec/terminology-corrections.md`
2. Parse its `## Open Issues` section. Collect all unchecked items (`- [ ]`).
3. If no unchecked items exist: "No open issues in the corrections log. Nothing to review." **End of Review Mode.**

### Step 2: Present Summary

```
REVIEW SESSION: Terminology Corrections

Open issues: [N] ([M] blocking, [K] non-blocking)

Starting guided review...
```

### Step 3: Walk Through Issues

For each unchecked issue, in order:

a. Present the issue:
   ```
   ───────────────────────────────────────
   ISSUE [N/total]: [issue description]
   Source: [source]
   Severity: [blocking / non-blocking]
   ───────────────────────────────────────
   ```

b. Analyze the issue against current state:
   - Has this issue already been addressed by changes since it was logged?
   - Is the issue still valid given the current state of the corrections log and related artifacts?
   - What would resolving it require — an edit to the corrections log, an edit to another artifact, or a structural change?
   - If resolving it would require a glossary edit, that is a hand-off to `/dekspec:write-glossary`, not an edit made here.

c. Present a recommendation:
   ```
   RECOMMENDATION: [resolve / revise / defer / dismiss]

   [Specific explanation — what to change and why, or why to defer/dismiss]

   [If resolve or revise: show the proposed change]
   ```

d. Wait for the engineer's response.

e. Based on response:
   - **Resolve** — apply the fix, check off the issue: `- [x] [Issue] — **Source:** ... — **Severity:** ... — **Resolved:** [today] [resolution summary]`
   - **Revise** — apply the agreed change, then check off the issue with a resolution note
   - **Defer** — leave unchecked, optionally update the issue description with new context
   - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`

### Step 4: Update and Report

1. Update the **Modified** date if the file was changed.
2. Present summary:
   ```
   REVIEW COMPLETE: Terminology Corrections

   Resolved: [N]
   Dismissed: [N]
   Deferred: [N]
   Handed to /dekspec:write-glossary: [N]

   [If blocking issues remain]: ⚠️  [N] blocking issues remain.
   [If no blocking issues remain]: ✅ No blocking issues remain.
   ```

**End of Review Mode.**

## Audit Mode

Structural health check on `dekspec/terminology-corrections.md`. Read-only.

### Scope, and what the engine owns instead

This mode checks the corrections log against itself. Everything that spans two artifacts or the wider corpus is an audit-engine rule in `tooling/dekspec/fidelity_audit/linkage.py`, run by `dekspec doctor` — not re-implemented here:

| Check | Where it lives |
|---|---|
| Corrections-log structural health | **here** |
| Glossary structural health | engine (the `T-GLOSSARY-*` family) |
| Promotion completeness (promoted entry ⇄ glossary row) | engine |
| Corrections ↔ glossary contradictions | engine |
| Corpus-wide terminology compliance + normalization | engine |
| Pipeline wiring (which skills call `--log`) | engine |

If a check below starts needing the glossary to answer it, it has become an engine rule — file it rather than growing this mode back into a cross-artifact auditor.

### Step 1: Read State

Read `dekspec/terminology-corrections.md`.

### Step 2: Corrections Structural Health

- [ ] **Format compliance.** Every entry follows the structured format: `### [slug]`, `- **Correction:**`, `- **Category:**`, `- **Recurrences:**` (with dated entries), and optionally `- **Status:**`. Flag any entry missing required fields.
- [ ] **Slug uniqueness.** No two entries share the same slug.
- [ ] **Category validity.** Every entry's Category field matches one of the section headers: Terminology, Architecture, Numeric Ranges, Embedding Types, Document Hierarchy.
- [ ] **Entry-section alignment.** Every entry appears under the section header that matches its Category field. An Architecture entry under the Terminology section is a filing error.
- [ ] **No duplicate corrections.** No two entries cover semantically identical corrections under different slugs. Compare correction text — flag pairs that describe the same misinterpretation in different words.
- [ ] **Recurrence format.** Each recurrence line has a date (YYYY-MM-DD), a source artifact/context, and a brief description. Flag entries with undated or unsourced recurrences.
- [ ] **Recurrence chronology.** Recurrence dates within each entry are in chronological order.
- [ ] **Recurrence sources reference real artifacts.** For each recurrence naming a specific artifact (WS-NNN, ADR-NNN, IB-NNN, AE-NNN, IC-NNN), verify the artifact exists via Glob. Flag phantom references.

### Step 3: Threshold Position (informational)

Neither of these is a defect — they are the log's position relative to the threshold, reported so the engineer can see what is about to move.

- [ ] **Near-threshold entries.** Active (non-promoted) entries with 2 recurrences — one more occurrence triggers promotion.
- [ ] **Stale active entries.** Active entries with a single recurrence older than 90 days. The mistake may have been a one-off. Report as stale; do not recommend deletion — the engineer decides.

### Step 4: Report

```
TERMINOLOGY CORRECTIONS AUDIT

═══════════════════════════════════════
Structural Health
═══════════════════════════════════════
Entries: [total] ([N] active, [M] promoted, [K] stale)
Format compliance: [pass / N issues]
Slug uniqueness: [pass / N collisions]
Category alignment: [pass / N misfilings]
Duplicates: [none / N found]
Recurrence format + chronology: [pass / N issues]
Phantom recurrence sources: [none / N found]

═══════════════════════════════════════
Threshold Position (informational)
═══════════════════════════════════════
Near-threshold (2/3): [N entries]
Stale (1 recurrence, >90 days): [N entries]

═══════════════════════════════════════
SUMMARY: [N] issues, [M] informational
═══════════════════════════════════════

Cross-artifact terminology health (glossary structure, promotion
completeness, corpus compliance, pipeline wiring) is not checked here —
run `dekspec doctor` for those.
```

Read-only — no changes made.

**End of Audit Mode.**

## Provisional Mode (Singleton)

`--provisional <incubation-slug>` stages a copy of the corrections singleton inside `dekspec/provisional/<incubation-slug>/` instead of editing the canonical at `dekspec/terminology-corrections.md`. Singletons follow the same CoW discipline as numbered artifacts — the difference is that the `replaces:` field uses the canonical filename rather than a `<KIND>-NNN` ID.

Use this mode when:
- The corrections change is exploratory and might be abandoned before ratification.
- Multiple Intents in the same incubation folder co-vary with the corrections change.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding.
2. CoW the singleton via the auto-stage verb:
   ```
   dekspec library cow-stage dekspec/terminology-corrections.md --incubation <slug>
   ```
   The verb copies the singleton into `dekspec/provisional/<slug>/<basename>-provisional.md`, stamps `replaces: terminology-corrections` in YAML frontmatter, and returns the new path.
3. **Populate the staged copy with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here. The PROVISIONAL banner at the top stays.
4. **Reject `--lock` / `--accept`** in combination with `--provisional`. The singleton's canonical replacement runs as part of the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)), not from this skill body.
5. **`--audit` / `--review`** remain available; they operate on the provisional file's content.
6. Closing step: surface the provisional path, the branch (if `dekspec library new-provisional` was used earlier), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** singleton — guards `dekspec/terminology-corrections.md`.

## Rules

- The promotion threshold is 3 recurrences. This is not configurable per-entry — it is a system constant, unchanged by the INT-191 split.
- Promotion is automatic and immediate when the threshold is reached during `--log`. Do not defer, ask for confirmation, or batch promotions.
- **This skill never writes `dekspec/domain-glossary.md`.** The promotion hand-off ends at `/dekspec:write-glossary --add-term`; that skill is the writer.
- The corrections log is a pipeline, not a curated document. Entries are not edited for prose quality — they capture the correction accurately and move on.
- Promoted entries stay in the log with their full recurrence history for traceability. They are not deleted.
- The glossary is the authoritative source once promoted. If a glossary row and a correction entry contradict each other after promotion, the glossary wins.
- Cross-artifact terminology checks are audit-engine rules. Do not restate one in this skill body; extend `tooling/dekspec/fidelity_audit/linkage.py` instead (and it must be dogfood-clean on this repo's own tree before merge).

## Common Pitfalls

- Don't match corrections on string equality — match on meaning. "co-occurrence" vs "cooccurrence" and "token merging" vs "wave compression" are the *same* concept; treating them as distinct splits the recurrence count and prevents promotion.
- Don't defer, batch, or ask for confirmation on promotion — when `add-recurrence` returns `promote_ready: true`, promote in the same `--log` run.
- Don't compose the glossary row here. `promote` returns the Correction text precisely so `/dekspec:write-glossary` can compose it; writing the row from this skill re-merges the two surfaces INT-191 separated.
- Don't leave a flipped status without a completed hand-off — a promoted entry with no glossary row is an incomplete promotion, and the audit engine will say so.
- Don't hand-edit the recurrence list or the `Status:` line — route those mutations through `scripts/corrections_ops.py add-recurrence` / `promote` so the count is recomputed transactionally; manual edits drift the count from reality.
- Don't grow `--audit` back into a cross-artifact auditor. If a check needs the glossary or the wider corpus to answer it, it is an engine rule.
- Don't skip the `dekspec library cow-stage` guard before editing `dekspec/terminology-corrections.md` — a direct canonical edit while a pre-ACCEPTED Intent claims the path trips `T-COW-CANONICAL-EDITED` (P2).
- Don't write an artifact in Teaching Mode — it is read-only; validate the engineer's draft entry shape and exit.

## Verification Checklist

- [ ] Correct mode was entered from the flag, or help was shown when no flag was present.
- [ ] A glossary-shaped request (add a term, extract candidates, synonym check) was routed to `/dekspec:write-glossary` rather than served here.
- [ ] In `--log`: the correction was matched against both the corrections log AND glossary terms (Step 3a + 3b) on meaning, not strings, before deciding add-recurrence vs. create-new.
- [ ] Recurrence and status mutations went through `scripts/corrections_ops.py` (add-recurrence / slugify / promote), not hand-edits; non-zero exits had stderr surfaced.
- [ ] Any entry that reached 3 recurrences had its status flipped AND its correction text handed to `/dekspec:write-glossary --add-term` in the same run; `dekspec/domain-glossary.md` was not edited from here.
- [ ] Any edit to `dekspec/terminology-corrections.md` was preceded by the `dekspec library cow-stage` guard (or correctly fell through to direct-flow on exit 1).
- [ ] `--audit` / `--review` made no unintended writes beyond their declared resolutions; the **Modified** date was bumped on the file if it actually changed.
- [ ] For substantive modes, `dekspec relink` was run against the repo root as the final action.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise a correction entry — `--log`, `--review`). After the file is saved and any index update is done, run:

```
dekspec relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
