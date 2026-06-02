---
name: write-ggc
description: Manage the Glossary, Guidance, and Corrections pipeline — log misinterpretations, track recurrences, auto-promote to the domain glossary, add terms directly, and audit terminology health across the system.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --log | --add-term] [correction text, term details, or path]
related_skills: [write-ws, write-adr, write-ae, write-ic, write-ibs]
---

Manage the Glossary, Guidance, and Corrections (GGC) pipeline — from correction detection through glossary promotion, plus direct glossary management.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-ggc --log "Assembly was described as compressing nodes in the WS-014 draft. Assembly does not compress — it only concatenates pre-budgeted segments. Source: WS-014. Category: Architecture"

Log this correction. If it crosses the 3-recurrence threshold, auto-promote it to the domain glossary.
```

## Fan-Out Mode

Fan-out is **deliberately deferred** for `write-ggc` (see ds-di2 OI-2 and [`_lib/fan_out.md`](../_lib/fan_out.md) §"When NOT to use fan-out"). Manifest for this skill:

- **subagent_type**: n/a (deferred)
- **substantive_modes**: [] (no modes fan out today)
- **inline_modes**: [`--help`, `--teaching`, `--log`, `--add-term`, `--audit`, `--review`] — every mode runs inline in the parent session.

**Reasoning** (per the substrate's deferral rationale):

- `--log` is multi-turn correction work. Step 3 (Match Against Existing Entries) explicitly pauses on partial matches to ask the engineer whether two corrections are the same; Step 5 (Auto-Promote) mutates the glossary based on recurrence-count state that lives in the g&c file and must be read/written transactionally with the engineer's confirmation context.
- `--add-term` has a synonym-match step (Step 3) that waits for engineer response before deciding whether to add a separate entry or update an existing one.
- `--review` and `--audit` are already on the preserve-inline list per `ds-di2`.
- `--teaching` and `--help` are engineer-facing prose, never fanned out.

The glossary-promotion semantics + interactive synonym disambiguation rely on iterative back-and-forth that fresh-context subagents cannot replicate without losing the engineer-in-the-loop signal that makes the GGC pipeline useful.

**Trigger to revisit:** if a non-interactive batch mode is ever added (e.g., `--log --batch <file>` that ingests pre-disambiguated corrections, or `--add-term --batch <file>` that bulk-adds terms whose synonym checks have already been resolved), fan that mode out at that time per the standard ds-di2 pattern. Until then, keep `write-ggc` fully inline.

**End of Fan-Out Mode.**

## Mode Detection

Parse `$ARGUMENTS` for flags. If a flag is present, strip it and enter the corresponding mode.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Log mode** — `--log` flag. Skip to **Log Mode**.
- **Add-term mode** — `--add-term` flag. Skip to **Add-Term Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.

If no flag is present, display help.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-ggc"
one_line:   "Manage the Glossary, Guidance, and Corrections pipeline"
modes:
  - { flag: "--log", args: "<details>", description: "Log a new correction or add a recurrence to an existing one. If the recurrence count reaches the promotion threshold (3), auto-promotes the entry to the domain glossary. Details can be inline text or structured fields: correction: what was wrong and what is right source: which artifact and context category: Terminology | Architecture | Numeric Ranges | Embedding Types | Document Hierarchy" }
  - { flag: "--add-term", args: "<details>", description: "Add a term directly to the glossary, bypassing the recurrence pipeline. Use for front-loaded terms the engineer knows are canonical. Checks for duplicates and synonym conflicts before adding." }
  - { flag: "--audit", args: "", description: "Comprehensive health check: g&c structural health, promotion pipeline, glossary integrity, g&c ↔ glossary consistency, cross-artifact compliance, terminology normalization (synonym detection across artifacts and code), and pipeline wiring." }
  - { flag: "--review", args: "", description: "Walk through open issues in the glossary and g&c files interactively. Present each issue with context and a recommendation. Engineer resolves, defers, or dismisses each." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through how to log a correction (--log) or add a glossary term (--add-term). Explains the recurrence-promotion pipeline." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-ggc --log \"Assembly was described as compressing nodes in WS-010 draft. Assembly does not compress — it only concatenates pre-budgeted segments. Category: Architecture\""
  - "/write-ggc --add-term \"Term: shadow timeline. Definition: In-memory cache in front of PostgreSQL for timeline data. NOT this: not a secondary cache. Code convention: shadow_timeline. Category: Graph & Storage\""
  - "/write-ggc --audit"
  - "/write-ggc --review"
  - "/write-ggc --help"
extra_sections:
  - heading: "TYPICALLY CALLED BY"
    body:
      - "Authoring skills (write-adr, write-ae, write-ic,"
      - "write-ws, write-ibs) when they correct a"
      - "misinterpretation during creation, review, revise, or audit modes."
      - "Engineer directly for --add-term and --audit."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: GGC entry (Glossary / Guidance / Corrections)
- **template_path**: entry shapes for `--log` and `--add-term` (defined inline below)
- **methodology_section**: §GGC pipeline of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/guidance-and-corrections.md`, `dekspec/domain-glossary.md`
- **required_sections**: per write path — log entries require [correction text, source artifact + context, category enum]; add-term entries require [term, canonical_definition, not_this, code_convention, category]

**Skill-unique two-path shape — Teaching Mode is read-only here, no artifact written:**

The GGC pipeline supports two distinct write paths. Teaching Mode walks both contracts without performing the writes:

1. **`--log` path:** correction-entry shape. Explain the recurrence-counting model (3 recurrences → auto-promote to glossary row) and show one exemplar entry from `dekspec/guidance-and-corrections.md`. Prompt the engineer to draft an example correction; validate the entry shape; do NOT actually write it.
2. **`--add-term` path:** glossary-entry shape. Explain duplicate + synonym checks. Show one exemplar entry from `dekspec/domain-glossary.md`. Prompt the engineer to draft an example term; validate the entry shape; do NOT actually write it.

On exit, summarize the contract the engineer just learned plus the two real-mode commands they would run to actually log a correction or add a term. Teaching Mode here departs from the canonical ritual's "write artifact to disk at DRAFT status" close because GGC entries are append-only into existing files; there is no draft state.

## Log Mode

Record a correction or add a recurrence to an existing one. Auto-promotes to the domain glossary when the recurrence threshold is reached.

### Step 1: Parse Input

Extract from the arguments:
- **Correction** — what was wrong and what is correct (required)
- **Source** — which artifact, session, or context triggered this (required)
- **Category** — one of: Terminology, Architecture, Numeric Ranges, Embedding Types, Document Hierarchy (required)

If any required field is missing, infer it from context if unambiguous. If ambiguous, ask.

### Step 2: Read Current State

1. Read `dekspec/guidance-and-corrections.md`
2. Read `dekspec/domain-glossary.md`

### Step 3: Match Against Existing Entries and Glossary

Search for the correction concept across both g&c entries and glossary terms. The same concept can appear under different names, spellings, or phrasings — match on meaning, not strings.

**3a. Match against g&c entries:**
- **Exact match** — an entry with the same slug or substantially identical correction text exists. Proceed to Step 4a (add recurrence).
- **Synonym match** — an entry covers the same concept using different phrasing (e.g., "token merging" vs "wave compression", "co-occurrence" vs "cooccurrence"). Treat as the same entry. Proceed to Step 4a (add recurrence) and note the variant phrasing in the recurrence description so the pattern is visible.
- **Partial match** — an entry covers a related but not identical correction. Present both to the engineer: "This correction is related to an existing entry: [existing]. Are these the same correction, or a new one?" Wait for response.
- **No match in g&c** — continue to 3b.

**3b. Match against glossary terms:**
Before creating a new g&c entry, check if the glossary already addresses this correction. The glossary's Canonical Definition, "NOT this" column, and Code convention columns define the canonical form.
- **Glossary already covers this** — the correction is about a concept the glossary already defines correctly, and the mistake was using a non-canonical form. This is a compliance failure, not a new correction. Log a recurrence against the existing promoted g&c entry if one exists. If no g&c entry exists (the glossary term was front-loaded without a g&c entry), create one with `Status: promoted to glossary [original date] (seed entry)` and log the recurrence.
- **Glossary has a related but incomplete entry** — the correction adds new insight the glossary doesn't cover (a new "NOT this" pattern, a variant spelling to flag). Proceed to Step 4b (create new entry) — when it reaches threshold, promotion will enrich the existing glossary row.
- **No glossary coverage** — proceed to Step 4b (create new entry).

### Step 4a: Add Recurrence

Run `scripts/ggc_ops.py add-recurrence <slug> --source <source> --desc <desc>`
(in this skill's folder). It surgically appends the dated recurrence line under
the entry's `- **Recurrences:**` list, recomputes the count, and returns JSON
with `count` and `promote_ready` (`true` when `count` ≥ 3). Surface stderr on a
non-zero exit (e.g. unknown slug, missing g&c file).

1. If `promote_ready` is `true`: proceed to **Step 5: Auto-Promote**.
2. If `false`: report:
   ```
   RECURRENCE LOGGED: [entry slug]
   Count: [N]/3
   Source: [source]
   ```

### Step 4b: Create New Entry

1. Generate a slug from the correction by running
   `scripts/ggc_ops.py slugify "<correction text>"` — it returns a lowercase,
   hyphenated, descriptive slug. (Creating the new entry block itself is an AI
   step — the correction text + category framing are judgment.)
2. Append a new entry to the appropriate category section in g&c:
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

### Step 5: Auto-Promote

When an entry reaches 3 recurrences, promote it to the domain glossary automatically.

1. Read the glossary to determine the correct category table and check for an existing row.
2. **If a matching term already exists in the glossary:** Update the row — enrich the "NOT this" column with the correction's insight if it adds information not already present.
3. **If no matching term exists:** Add a new row to the appropriate category table:
   - **Term** — derive from the correction
   - **Canonical Definition** — the correct understanding
   - **NOT this** — the common misinterpretation that keeps recurring
   - **Code convention** — if applicable, otherwise `—`

   Composing the glossary row (Term / Canonical Definition / NOT this) is an AI
   judgment step.
4. Update the g&c entry status to promoted by running
   `scripts/ggc_ops.py promote <slug>` (in this skill's folder). It surgically
   sets `- **Status:** promoted to glossary YYYY-MM-DD` on the entry and
   returns the entry's Correction text so the glossary row above can be
   composed from it. Surface stderr on a non-zero exit.
5. Update the glossary's **Modified** date.
6. Report:
   ```
   AUTO-PROMOTED TO GLOSSARY: [slug]
   Category: [category]
   Recurrences: [N]
   Glossary action: [new row added / existing row updated]
   
   The correction has been promoted. Future authoring skills will read it
   proactively from the glossary.
   ```

**End of Log Mode.**

## Add-Term Mode

Add a term directly to the glossary, bypassing the recurrence pipeline. Use when the engineer knows a term is canonical and wants it in the glossary immediately — no g&c entry, no recurrence tracking.

### Step 1: Parse Input

Extract from the arguments:
- **Term** — the canonical name (required)
- **Canonical Definition** — what the term means in this system (required)
- **NOT this** — common misinterpretations to avoid (required — if there are none yet, use `—`)
- **Code convention** — the variable/function naming pattern, or `—` if not applicable
- **Category** — which glossary section: Embedding & Tensor, Quantization & Compression, Architecture & Pipeline, Graph & Storage, Scoring & Geometry, Position & Injection, Timeline & Topics, Numeric Constraints, Document Hierarchy Rules (required)

If any required field is missing, ask.

### Step 2: Read Glossary

1. Read `dekspec/domain-glossary.md`

### Step 3: Duplicate and Synonym Check

Before adding, verify this term doesn't already exist. Run
`scripts/ggc_ops.py find-synonym "<term>"` (in this skill's folder) — it returns
candidate glossary rows (and g&c slugs) whose text overlaps the term. The script
is a word-overlap heuristic; the AI judges which candidates, if any, are true
matches:

- **Exact match** — a candidate row has the same Term. STOP: "This term already exists in the glossary under [category]. Use `--audit` to review it, or edit the glossary directly."
- **Synonym match** — a candidate row defines the same concept under a different name. Present both: "The glossary already has [existing term] which appears to cover the same concept. Add anyway as a separate entry, or update the existing entry?" Wait for engineer response.
- **No match** — no candidate is a true match; proceed.

### Step 4: Add to Glossary

1. Determine the correct category table in the glossary.
2. Add a new row:
   - For term tables (most categories): `| **[Term]** | [Canonical Definition] | [NOT this] | [Code convention] |`
   - For Numeric Constraints: `| [Constraint] | [Value] | [Rationale] |`
   - For Document Hierarchy Rules: `| [Rule] | [Rationale] |`
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

## Audit Mode

Comprehensive health check on the corrections pipeline, glossary integrity, and cross-artifact compliance.

### Step 1: Read State

1. Read `dekspec/guidance-and-corrections.md`
2. Read `dekspec/domain-glossary.md`
3. Read `dekspec/domain-glossary.md` Amendment Log for last-modified context

### Step 2: G&C Structural Health

Verify the g&c file is well-formed and internally consistent.

- [ ] **Format compliance.** Every entry follows the structured format: `### [slug]`, `- **Correction:**`, `- **Category:**`, `- **Recurrences:**` (with dated entries), and optionally `- **Status:**`. Flag any entry missing required fields.
- [ ] **Slug uniqueness.** No two entries share the same slug.
- [ ] **Category validity.** Every entry's Category field matches one of the g&c section headers: Terminology, Architecture, Numeric Ranges, Embedding Types, Document Hierarchy.
- [ ] **Entry-section alignment.** Every entry appears under the section header that matches its Category field. An Architecture entry under the Terminology section is a filing error.
- [ ] **No duplicate corrections.** No two entries cover semantically identical corrections under different slugs. Compare correction text — flag pairs that describe the same misinterpretation in different words.
- [ ] **Recurrence format.** Each recurrence line has a date (YYYY-MM-DD), a source artifact/context, and a brief description. Flag entries with undated or unsourced recurrences.
- [ ] **Recurrence chronology.** Recurrence dates within each entry are in chronological order.
- [ ] **Recurrence sources reference real artifacts.** For each recurrence that names a specific artifact (WS-NNN, ADR-NNN, IB-NNN, AE-NNN, IC-NNN), verify the artifact exists via Glob. Flag phantom references.

### Step 3: Promotion Pipeline Health

Verify the threshold mechanism is working correctly.

- [ ] **No missed promotions.** Every entry with 3+ recurrences has `Status: promoted to glossary [date]`. If any entry has 3+ recurrences without a promoted status, the auto-promote in Log Mode was skipped or failed. Flag with: "Entry [slug] has [N] recurrences but was not promoted."
- [ ] **No premature promotions.** No entry with fewer than 3 recurrences has a promoted status (exception: seed entries marked `promoted to glossary 2026-04-10 (seed entry)` which were front-loaded, not process-generated).
- [ ] **Stale active entries.** Active entries (not promoted) with only 1 recurrence older than 90 days. The mistake may have been a one-off. Flag as stale but do not recommend deletion — the engineer decides.
- [ ] **Near-threshold entries.** Active entries with 2 recurrences — one more occurrence triggers promotion. Report these as informational, not as issues.

### Step 4: Glossary Structural Health

Verify the glossary itself is well-formed.

- [ ] **All category tables have correct columns.** Term tables must have: Term, Canonical Definition, NOT this, Code convention. Numeric Constraints table must have: Constraint, Value, Rationale. Document Hierarchy table must have: Rule, Rationale.
- [ ] **No empty or placeholder rows.** Every cell in every table row is populated (Code convention may be `—` when not applicable, but not blank).
- [ ] **No duplicate terms.** No two rows in the same category table define the same term.
- [ ] **No cross-category term conflicts.** A term appearing in two different category tables must not have contradictory definitions.
- [ ] **Dates set.** Glossary has Created and Modified dates. The glossary has no status field — it is a living document that grows continuously via the promotion pipeline.

### Step 5: G&C ↔ Glossary Consistency

Verify the pipeline's output matches the glossary's content.

- [ ] **Every promoted entry has a glossary row.** For each g&c entry with `Status: promoted`, verify a corresponding term or constraint exists in the glossary. If the promotion happened but the glossary row is missing, the promotion was incomplete.
- [ ] **No contradictions between g&c corrections and glossary definitions.** For each promoted entry, compare the g&c Correction text with the glossary row's Canonical Definition and "NOT this" columns. Flag any semantic contradictions — the glossary is authoritative, but contradictions indicate a promotion error or a later glossary edit that drifted from the original correction.
- [ ] **Glossary coverage of active corrections.** For each active (non-promoted) g&c entry, check if the glossary already covers the same concept. If the glossary already has a row addressing the same misinterpretation, the g&c entry may be redundant — flag it.

### Step 6: Cross-Artifact Compliance

Verify that corrections and glossary definitions are actually being followed across DekSpec artifacts. This is the most important check — if artifacts still use wrong terminology after corrections exist, the pipeline is not achieving its purpose.

1. Extract the "NOT this" column from every glossary term table row. These are the known misinterpretations.
2. For each "NOT this" pattern that can be expressed as a grep-able string or regex:
   - Grep `dekspec/working-specs/`, `dekspec/adrs/`, `dekspec/architecture-elements/`, `dekspec/interface-contracts/`, `dekspec/impl-briefs/` for the misinterpretation pattern.
   - Exclude matches inside the glossary itself, g&c itself, and archaeology docs.
   - For each match: read surrounding context to determine if it is a genuine violation (the artifact uses the wrong term/concept) or a false positive (the artifact is quoting the glossary's "NOT this" for clarity, or using the word in a different sense).
3. Report genuine violations:
   ```
   TERMINOLOGY VIOLATIONS:

   [artifact path]:[line] — uses "[wrong term/pattern]"
     Glossary says: [canonical definition]
     NOT this: [the pattern that matched]
   ```

Key patterns to check (derived from glossary "NOT this" columns):
- "embeddings" or "vectors" used generically without specifying cooccurrence or semantic
- "compression" used to mean quantization or vice versa
- "dropped" or "pruned" used to mean fully merged
- "prompt stuffing" or "RAG" used to describe injection
- "system prompt" used in Dektora context
- "1D position" or sequential position IDs in the content pipeline
- Assembly described as compressing, quantizing, or modifying fidelity
- Mind map described as a "vector database" or "RAG index"
- Shadow graph described as a "secondary cache"

### Step 7: Terminology Normalization

Detect terms that are semantically identical but appear under different names, spellings, or phrasings — across the glossary, g&c, specs, ADRs, architecture elements, contracts, IBs, and code. These are consolidation targets: the system should use one canonical form everywhere.

**7a. Build the canonical term map.**

From the glossary, extract every term and its known variants:
- **Canonical form** — the Term column (e.g., "Cooccurrence embedding")
- **Code convention** — the Code convention column (e.g., `cooccurrence`, `cooccurrence_embeddings`)
- **Known anti-patterns** — the "NOT this" column phrases that name the concept incorrectly (e.g., "vectors", "embeddings" used generically)

This produces a map: `canonical term → [code forms, known wrong forms]`.

**7b. Scan for unregistered synonyms in artifacts.**

Grep all DekSpec artifacts (`dekspec/working-specs/`, `dekspec/adrs/`, `dekspec/architecture-elements/`, `dekspec/interface-contracts/`, `dekspec/impl-briefs/`) for terms that:
- Refer to a glossary concept but use a form not in the canonical term map — a spelling variant (e.g., "co-occurrence" vs "cooccurrence"), a synonym (e.g., "hidden state embedding" for "cooccurrence embedding"), an abbreviation, or a phrasing that is close but not canonical.
- Appear consistently enough to be a de facto term (2+ occurrences across artifacts) but are not in the glossary.

For each unregistered synonym found:
```
SYNONYM DETECTED: "[variant]" appears to mean "[canonical term]"
  Occurrences: [N] across [list of artifacts]
  Canonical form: [glossary term]
  Code convention: [glossary code convention]
  Action needed: Consolidate to canonical form, or add as recognized alias in glossary
```

**7c. Scan for unregistered synonyms in code.**

If Python source files exist in the project, grep for variable names, function names, and class names that:
- Use a variant spelling of a glossary code convention (e.g., `cooccurrence_emb` vs `cooccurrence_embeddings`, `shadow_cache` vs `shadow_graph`)
- Use a term the glossary explicitly marks as wrong (e.g., a variable named `vectors` or `embeddings` without a qualifier)

For each code synonym found:
```
CODE SYNONYM: [file]:[line] — "[code name]"
  Likely means: [canonical term]
  Glossary code convention: [expected name]
  Action needed: Rename to canonical form or document as intentional alias
```

**7d. Detect glossary-internal synonym clusters.**

Check within the glossary itself for rows that may describe the same concept:
- Two rows whose Canonical Definitions overlap substantially
- Two rows where one's "NOT this" column describes the other's Term
- Two rows with identical or overlapping Code convention values

For each potential cluster:
```
GLOSSARY SYNONYM CLUSTER:
  Row 1: [Term] in [Category] — "[definition excerpt]"
  Row 2: [Term] in [Category] — "[definition excerpt]"
  Overlap: [what they share]
  Action needed: Merge into one entry, or add cross-reference to distinguish
```

**7e. Detect g&c-internal synonym entries.**

Check within g&c for entries that correct the same underlying misinterpretation using different framing:
- Two entries whose Correction text addresses the same concept
- Two entries whose slugs are near-synonyms

For each potential duplicate:
```
G&C SYNONYM ENTRIES:
  Entry 1: [slug] — "[correction excerpt]"
  Entry 2: [slug] — "[correction excerpt]"
  Action needed: Merge into single entry, combine recurrence logs
```

### Step 8: Pipeline Wiring Check

Verify the authoring skills are wired to call `/write-ggc --log`.

- [ ] **write-adr** Rules section contains the "Log corrections" rule referencing `/write-ggc --log`
- [ ] **write-ae** Rules section contains the "Log corrections" rule
- [ ] **write-ic** Rules section contains the "Log corrections" rule
- [ ] **write-ws** Rules section contains the "Log corrections" rule
- [ ] **write-ibs** IB Content Rules section contains the "Log corrections" rule

If any skill is missing the rule, flag: "Skill [name] is not wired to the corrections pipeline. Misinterpretations corrected by this skill will not be tracked."

### Step 9: Report

```
CORRECTIONS PIPELINE AUDIT

═══════════════════════════════════════
G&C Structural Health
═══════════════════════════════════════
Entries: [total] ([N] active, [M] promoted, [K] stale)
Format compliance: [pass / N issues]
Duplicates: [none / N found]
Category alignment: [pass / N misfilings]

═══════════════════════════════════════
Promotion Pipeline
═══════════════════════════════════════
Missed promotions: [none / N entries at threshold without promotion]
Premature promotions: [none / N found]
Near-threshold (2/3): [N entries — informational]
Stale (1 recurrence, >90 days): [N entries — informational]

═══════════════════════════════════════
Glossary Health
═══════════════════════════════════════
Tables well-formed: [pass / N issues]
Duplicate terms: [none / N found]
Status/dates: [pass / issues]

═══════════════════════════════════════
G&C ↔ Glossary Consistency
═══════════════════════════════════════
Promoted entries with glossary rows: [N/N]
Contradictions: [none / N found]
Redundant active entries: [none / N found]

═══════════════════════════════════════
Cross-Artifact Compliance
═══════════════════════════════════════
Artifacts scanned: [N]
Terminology violations: [none / N found]
  [list each violation with path, line, and glossary reference]

═══════════════════════════════════════
Terminology Normalization
═══════════════════════════════════════
Canonical terms in glossary: [N]
Unregistered synonyms in artifacts: [none / N found]
  [list each with variant, canonical form, and occurrences]
Unregistered synonyms in code: [none / N found]
  [list each with file, code name, and canonical convention]
Glossary-internal synonym clusters: [none / N found]
  [list each cluster with rows and overlap description]
G&C-internal synonym entries: [none / N found]
  [list each pair with slugs]

═══════════════════════════════════════
Pipeline Wiring
═══════════════════════════════════════
Skills wired: [N/5]
  [list any unwired skills]

═══════════════════════════════════════
SUMMARY: [N] issues, [M] informational
═══════════════════════════════════════
```

Read-only — no changes made.

**End of Audit Mode.**

## Review Mode

Walk through open issues in the glossary and g&c files interactively — present each issue with context and a recommendation, resolve with the engineer one at a time.

No arguments required — review mode covers both files.

### Step 1: Read State

1. Read `dekspec/domain-glossary.md`
2. Read `dekspec/guidance-and-corrections.md`
3. Parse the `## Open Issues` section from each file. Collect all unchecked items (`- [ ]`).
4. If no unchecked items exist in either file: "No open issues in glossary or g&c. Nothing to review." **End of Review Mode.**

### Step 2: Present Summary

```
REVIEW SESSION: Glossary & Guidance-and-Corrections

Glossary open issues: [N] ([M] blocking, [K] non-blocking)
G&C open issues: [N] ([M] blocking, [K] non-blocking)
Total: [N]

Starting guided review...
```

### Step 3: Walk Through Issues

Process glossary issues first, then g&c issues. For each unchecked issue, in order:

a. Present the issue:
   ```
   ───────────────────────────────────────
   ISSUE [N/total]: [issue description]
   File: [glossary | g&c]
   Source: [source]
   Severity: [blocking / non-blocking]
   ───────────────────────────────────────
   ```

b. Analyze the issue against current state:
   - Has this issue already been addressed by changes since it was logged?
   - Is the issue still valid given the current state of the glossary, g&c, and related artifacts?
   - What would resolving this issue require — an edit to the glossary, an edit to g&c, an edit to another artifact, or a structural change?

c. Present a recommendation:
   ```
   RECOMMENDATION: [resolve / revise / defer / dismiss]
   
   [Specific explanation — what to change and why, or why to defer/dismiss]
   
   [If resolve or revise: show the proposed change]
   ```

d. Wait for the engineer's response.

e. Based on response:
   - **Resolve** — apply the fix, check off the issue: `- [x] [Issue] — **Source:** ... — **Severity:** ... — **Resolved:** [today] [resolution summary]`
   - **Revise** — apply the agreed change to the file, then check off the issue with resolution note
   - **Defer** — leave unchecked, optionally update the issue description with new context
   - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`

### Step 4: Update and Report

1. Update **Modified** dates on any files that were changed.
2. Present summary:
   ```
   REVIEW COMPLETE: Glossary & Guidance-and-Corrections
   
   Resolved: [N]
   Dismissed: [N]
   Deferred: [N]
   
   [If blocking issues remain]: ⚠️  [N] blocking issues remain.
   [If no blocking issues remain]: ✅ No blocking issues remain.
   ```

**End of Review Mode.**

## Provisional Mode (Singleton)

`--provisional <incubation-slug>` stages a copy of the Glossary, Guidance & Corrections singleton inside `dekspec/provisional/<incubation-slug>/` instead of editing the canonical at `dekspec/domain-glossary.md`. Singletons follow the same CoW discipline as numbered artifacts — the difference is that the `replaces:` field uses the canonical filename rather than a `<KIND>-NNN` ID.

Use this mode when:
- The Glossary, Guidance & Corrections change is exploratory and might be abandoned before ratification.
- Multiple Intents in the same incubation folder co-vary with the Glossary, Guidance & Corrections change.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding.
2. CoW the singleton via the auto-stage verb:
   ```
   dekspec library cow-stage dekspec/domain-glossary.md --incubation <slug>
   ```
   The verb copies the singleton into `dekspec/provisional/<slug>/<basename>-provisional.md`, stamps `replaces: domain-glossary` in YAML frontmatter, and returns the new path.
3. **Populate the staged copy with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here. The PROVISIONAL banner at the top stays.
4. **Reject `--lock` / `--accept`** in combination with `--provisional`. The singleton's canonical replacement runs as part of the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)), not from this skill body. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)
5. **`--audit` / `--review`** remain available; they operate on the provisional file's content.
6. Closing step: surface the provisional path, the branch (if `dekspec library new-provisional` was used earlier), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

Before any edit to the Glossary, Guidance & Corrections singleton at `dekspec/domain-glossary.md`, consult the CoW guard:

```bash
dekspec library cow-stage dekspec/domain-glossary.md [--incubation <slug>] [--at <repo>]
```

If a pre-ACCEPTED Intent (DRAFT/PROPOSED) claims the singleton's path via Components-affected globs, the verb copies the canonical into the incubation folder + stamps `replaces:`. Edit the staged copy; the canonical stays frozen.

If the singleton is unclaimed, the verb errors unless `--incubation <slug>` is passed explicitly — the canonical-only path is then the normal edit flow.

**Skill discipline.** Inside this skill body, before any canonical `Edit`/`Write` call on `dekspec/domain-glossary.md`:

1. Run `dekspec library cow-stage dekspec/domain-glossary.md` once.
2. On exit 0 (provisional path printed): redirect the edit there.
3. On exit 1 (no claim + no `--incubation`): proceed with the canonical edit (direct-flow legal).

**Audit pairing.** `T-COW-CANONICAL-EDITED` (P2 mechanical) fires on direct-edit bypasses of this guard.

## Rules

- The promotion threshold is 3 recurrences. This is not configurable per-entry — it is a system constant.
- Promotion is automatic and immediate when the threshold is reached during `--log`. Do not defer, ask for confirmation, or batch promotions.
- The g&c file is a pipeline, not a curated document. Entries are not edited for prose quality — they capture the correction accurately and move on.
- Promoted entries remain in g&c with their full recurrence log for traceability. They are not deleted.
- The glossary is the authoritative source once promoted. If a glossary entry and a g&c entry contradict each other after promotion, the glossary wins.
- When creating glossary rows during promotion, maintain the glossary's existing table format and category organization. Do not add new category sections to the glossary without engineer approval.

## Common Pitfalls

- Don't match corrections or terms on string equality — match on meaning. "co-occurrence" vs "cooccurrence" and "token merging" vs "wave compression" are the *same* concept; treating them as distinct splits the recurrence count and prevents promotion.
- Don't defer, batch, or ask for confirmation on auto-promotion — when `add-recurrence` returns `promote_ready: true`, promote in the same `--log` run. The threshold (3) is a system constant, never a per-entry knob.
- Don't hand-edit the recurrence list or the `Status:` line — route those mutations through `scripts/ggc_ops.py add-recurrence` / `promote` so the count is recomputed transactionally; manual edits drift the count from reality.
- Don't `--add-term` a concept the glossary already covers — run the Step 3 duplicate/synonym check first and STOP on an exact match; a compliance failure belongs in `--log` as a recurrence, not as a second glossary row.
- Don't treat Audit Step 6 grep hits as violations without reading context — an artifact quoting a glossary "NOT this" for clarity is a false positive, not a terminology violation.
- Don't skip the `dekspec library cow-stage` guard before editing `dekspec/domain-glossary.md` — a direct canonical edit while a pre-ACCEPTED Intent claims the path trips `T-COW-CANONICAL-EDITED` (P2).
- Don't write an artifact in Teaching Mode — it is read-only; validate the engineer's draft entry shape and exit without touching g&c or the glossary.

## Verification Checklist

- [ ] Correct mode was entered from the flag, or help was shown when no flag was present.
- [ ] In `--log`: the correction was matched against both g&c entries AND glossary terms (Step 3a + 3b) on meaning, not strings, before deciding add-recurrence vs. create-new.
- [ ] Recurrence and status mutations went through `scripts/ggc_ops.py` (add-recurrence / slugify / promote), not hand-edits; non-zero exits had stderr surfaced.
- [ ] Any entry that reached 3 recurrences was auto-promoted in the same run, with a glossary row added/enriched and the g&c `Status:` set.
- [ ] In `--add-term`: the Step 3 duplicate + synonym check ran and STOPPED on an exact match; no duplicate glossary row was added.
- [ ] Any edit to `dekspec/domain-glossary.md` was preceded by the `dekspec library cow-stage` guard (or correctly fell through to direct-flow on exit 1).
- [ ] `--audit` / `--review` made no unintended writes beyond their declared resolutions; the glossary **Modified** date was bumped on any file actually changed.
- [ ] For substantive modes, `dekspec audit relink` was run against the repo root as the final action.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise a Glossary / Guidance-and-Corrections entry — `--log`, `--add-term`, `--review`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
