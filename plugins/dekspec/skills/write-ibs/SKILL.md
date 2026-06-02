---
name: write-ibs
description: Decompose a finalized Working Spec into Implementation Briefs. Use after a spec is finalized and ready for implementation planning.
mode: full
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --accept | --approve | --lock | --resync | --revise | --dry-run] [path to finalized spec or existing IB] [engineer notes or path to notes file]
related_skills: [write-ws, write-ic, write-beads, write-tests, orchestrate-intent]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/templates/X-template.md` and `dekspec/dekspec-<doc>.md` reference the consumer-vendored layout. If your install is pip-only (no `scripts/install-dekspec.sh` run), resolve any reference via `dekspec resource template X` or `dekspec resource doc <name>` (consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Decompose a finalized Working Spec into Implementation Briefs.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill reconciles specs, ADRs, and interface contracts into a single authoritative implementation document. Prior conversation context can degrade reconciliation quality — the model may resolve against phantom context instead of the actual documents.
>
> First message → proceed. Prior history → ask "context may affect IB reconciliation quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-ibs dekspec/working-specs/WS-021-numeric-routing.md

Decompose this finalized (ACCEPTED) Working Spec into Implementation Briefs.
The spec spans a parser pass and an emitter pass — keep the shared IR types in a
foundation IB the others depend on, and respect the ICs it references.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode (no flag): content-shape dispatch — if the file is a Working Spec, enter **Decomposition Mode**; if it is an existing IB, enter **Audit Mode**; otherwise ask the engineer what they want to do.

- **Help mode** — `--help` flag is present. Skip to the **Help Mode** section below.
- **Teaching mode** — `--teaching` flag is present. Skip to the **Teaching Mode** section below.
- **Accept mode** — `--accept` or `--approve` flag is present (`--approve` is a retained alias). Proceed to **Fan-Out Mode (default decomposition path)**.
- **Lock mode** — `--lock` flag is present, expects a path to an existing IB in ACCEPTED. Skip to the **Lock Mode** section below. Do NOT run the decomposition workflow.
- **Audit mode** — `--audit` flag is present, OR the file contains `## Constraints & Decisions` and `## Done When` (i.e., it is an existing IB). Skip to the **Audit Mode** section below. Do NOT run the decomposition workflow.
- **Review mode** — `--review` flag is present. Skip to the **Review Mode** section below.
- **Resync mode** — `--resync` flag is present. Skip to the **Resync Mode** section below.
- **Revise mode** — `--revise` flag is present. Proceed to **Fan-Out Mode (default decomposition path)**.
- **Dry-run mode** — `--dry-run` flag is present. Skip to the **Dry-Run Mode** section below.
- **Decomposition mode** — no flag + the file is a Working Spec (contains `## Specification` or located under `dekspec/working-specs/`). Default substantive-work path. Proceed to **Fan-Out Mode (default decomposition path)**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag + WS shape, i.e. Decomposition), `--accept` / `--approve`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--audit`, `--review`, `--resync`, `--lock`, `--dry-run`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:ib-author`
- **substantive_modes**: [default decomposition (no flag + Working Spec path), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`, `--review`, `--resync`, `--lock`, `--dry-run`]
- **mechanical precondition** (orchestrator runs inline BEFORE dispatch; refuse if it fails): walk the spec graph to confirm the parent WS is `ACCEPTED` or higher (the L12 precondition — see §L12 Precondition below).
- **bundle_list** (Step 1 context — resolve every path to absolute before dispatch; workers should not guess `cwd`):
  1. Template path — `dekspec/templates/implementation-brief-template.md` (absolute). If missing, halt and tell the engineer to vendor dekspec.
  2. Parent Working Spec — the WS path from `$ARGUMENTS` (decomposition) OR the WS named in the IB's `Spec` header field (accept / revise). L12 status gate run BEFORE dispatch.
  3. Parent Intent (if present) — if the WS's `Parent Intent` field names an INT-NNN, include its absolute path (worker uses for cross-IB traceability).
  4. Governing ADRs — walk the WS's ADR references; for each, run `python ../_lib/scripts/resolve_supersession.py <ADR-ID>` and use the resolved live ADR (the script walks the `Superseded by` chain deterministically and detects cycles / dangling refs; surface stderr on non-zero exit). Include the resolved ADR paths.
  5. Interface Contracts — the ICs referenced by the WS, by absolute path.
  6. Sibling IBs — any existing IBs under the flat `dekspec/impl-briefs/` directory whose `Spec` field matches the parent WS (for cross-IB coupling checks in Phase 5). For the collision-free starting IB-NNN, run `python ../_lib/scripts/artifact_ops.py next-id ib` (surface stderr on non-zero exit); allocate sequential ids from there.
  7. Domain glossary — absolute path to `dekspec/domain-glossary.md` (L10 terminology checks).
  8. Engineer guidance — `$ARGUMENTS` verbatim (free-form notes, inline notes for revise, or `.md`/`.txt` file path); do NOT summarize.
  9. Mode-specific constraints: **Decomposition** — full decomposition workflow (Phase 1–5 below), IB Decomposition Principles, Decomposition Checklist, Fidelity Audit content + cohesion + coupling rules, Conflict Detection procedure (passed by reference to this skill body's anchors — worker reads them from the vendored skill, keeping the prompt compact and authoritative); **Accept** — "Run Audit Mode against the IB path. If clean and engineer confirmed, walk PROPOSED→ACCEPTED per Accept Mode Step 4. Refuse if any severity-important-or-worse finding"; **Revise** — "Apply engineer notes per Revise Mode classification (constraint / scope / clarity / structural / rejection). Run Conflict Detection + Fidelity Audit + sibling coupling checks before save. If structural, halt and return the structural escalation rather than mutating."
  10. Return-shape contract — worker returns a structured summary with `mode`, `artifacts` (list of `{path, status, validate_result, ib_number}`), `audit_summary` (per-IB pass/fail with check counts), `escalations` (unresolved issues needing engineer input), `failure_mode` ∈ {clean, insufficient_context, structural_escalation, audit_failure}.
- **expected_output_path**:
  - Decomposition: one or more `dekspec/impl-briefs/IB-NNN-<slug>-brief.md` files in the flat `dekspec/impl-briefs/` directory, each at `Status: PROPOSED`.
  - Accept: the existing IB path, mutated in place to `Status: ACCEPTED` with an Amendment-Log row appended.
  - Revise: the existing IB path, mutated in place, with `Engineer review` reset and (if new ambiguity surfaced) new `## Open Issues` entries.
- **validation**: `dekspec check validate <absolute-path-to-IB> --json` per IB. Worker runs and includes the result in its return summary; orchestrator re-runs as trust-but-verify (worker's claim is suggestive; the validate call is authoritative). Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md). Failure-mode routing: `insufficient_context` → surface gap verbatim, do NOT retry blindly; `structural_escalation` → present per Phase 4 step 16 ("requires re-decomposition"), wait for engineer decision; `audit_failure` → present failing checks (worker already iterated up to 2 rounds per Phase 4 step 17; further iteration requires engineer judgment); `clean` → present per-IB summary (mirrors Engineer Review Gate report), serve per **Serve for Review** section, instruct engineer on next steps (accept → `/write-beads`). In all cases, do NOT swallow worker errors — the raw return is a first-class signal about material quality.

**End of Fan-Out Mode — the inline sections below (Workflow, IB Decomposition Principles, Decomposition Checklist, Conflict Detection, Fidelity Audit, etc.) are the AUTHORITATIVE SPEC the worker follows. Do NOT execute them in the orchestrator's context.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-ibs"
one_line:   "Manage Implementation Briefs for the DekSpec workflow"
modes:
  - { flag: "", args: "<spec-path>", description: "Decompose a finalized Working Spec into IBs. Auto-detects Audit Mode if given an IB path (i.e., a file containing `## Constraints & Decisions` + `## Done When`). (Decomposition Mode)" }
  - { flag: "--audit", args: "<IB-path | glob>", description: "Run conflict detection + fidelity audit on existing IB(s). Read-only — reports findings without changes. (Audit Mode)" }
  - { flag: "--review", args: "<IB-path>", description: "Walk through open issues interactively; resolve one at a time with the engineer. (Review Mode)" }
  - { flag: "--resync", args: "<IB-path>", description: "Re-derive IB sections after the source WS / ADRs / ICs changed. Diffs upstream against IB and proposes per-section updates. (Resync Mode)" }
  - { flag: "--revise", args: "<IB-path> <notes>", description: "Targeted update from engineer feedback. Notes: inline text or path to a .md / .txt file. (Revise Mode)" }
  - { flag: "--accept", args: "<IB-path | glob>", description: "Promote IB(s) PROPOSED → ACCEPTED after a clean audit + engineer confirmation. `--approve` is a retained alias. (Accept Mode)" }
  - { flag: "--lock", args: "<IB-path>", description: "Promote IB ACCEPTED → LOCKED after parent-WS + cohort-coherence checks; re-runs the fidelity audit. IB must be LOCKED before downstream beads + tests can reference it. (Lock Mode)" }
  - { flag: "--dry-run", args: "<spec-path>", description: "Preview the decomposition: estimated IB count, dependency graph, silent-failure-domain coverage. Lightweight (1 round of checks). (Dry-Run Mode)" }
  - { flag: "--teaching", args: "<spec-path>", description: "Interactive tutorial walking a new author through decomposing a finalized Working Spec into Implementation Briefs. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-ibs dekspec/working-specs/WS-001-foo.md"
  - "/write-ibs --audit dekspec/impl-briefs/IB-001-component-brief.md"
  - "/write-ibs --audit \"dekspec/impl-briefs/**/*.md\""
  - "/write-ibs --review IB-001-component-brief.md"
  - "/write-ibs --resync IB-001-component-brief.md"
  - "/write-ibs --revise IB-001-component-brief.md \"done-when too vague; remove graph_cache.py\""
  - "/write-ibs --revise IB-001-component-brief.md review-notes.md"
  - "/write-ibs --accept IB-001-component-brief.md"
  - "/write-ibs --lock dekspec/impl-briefs/IB-001-component-brief.md"
  - "/write-ibs --dry-run dekspec/working-specs/WS-001-foo.md"
  - "/write-ibs --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: IB (Implementation Brief)
- **template_path**: `templates/implementation-brief-template.md`
- **methodology_section**: §4 Layer 3 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/impl-briefs/`
- **required_sections**: [Parent WS, Source AEs, Depends-on, Goal, Constraints & Decisions, Files to Modify, Do Not Touch, Governing ADRs, Done When]

Skill-specific structural checks to surface as Open Issues: T40-IB-GOAL, T41-IB-DONE-WHEN, L5-IB-AE.

**Skill-unique scope note:** Teaching Mode walks a single IB section-by-section. The default no-flag creation mode triggers a full Working-Spec decomposition workflow that produces multiple IBs; Teaching Mode does not — it is for the engineer who is authoring their first IB by hand.

## Accept Mode

Promote one or more IBs from PROPOSED → ACCEPTED after a clean audit + engineer confirmation. `--approve` is a retained alias for `--accept`.

### Steps

1. Resolve the target(s) — single IB path or glob expanding to multiple IBs under `dekspec/impl-briefs/`.
2. **For each IB, run Audit Mode first.** If any IB has severity-important-or-worse findings, refuse to accept that IB until the findings are resolved (via `--revise` or `--review`).
3. Present the per-IB summary:

```
ACCEPT PLAN — N IBs:
  ✅ IB-001-component-brief.md — audit clean, ready to accept
  ✅ IB-002-component-brief.md — audit clean, ready to accept
  ❌ IB-003-component-brief.md — 2 fidelity failures (must resolve before accept)
  ⏭️  IB-004-component-brief.md — already ACCEPTED, skipped

Proceed with the ✅ IBs? (yes / no)
```

4. Wait for explicit "yes". Then for each ready IB, run the status walk deterministically:
   `python ../_lib/scripts/artifact_ops.py transition <IB-path> --from PROPOSED --to ACCEPTED --note "Audit passed; engineer confirmed; promoted PROPOSED to ACCEPTED." --engineer <author>` — this flips Status and appends the Amendment-Log row in one step (IB files carry no Modified field, so none is bumped). Surface stderr on non-zero exit; skip that IB and report the failure.
5. Report:

```
✅ N IB(s) promoted PROPOSED → ACCEPTED.
   Next: run /write-beads on each accepted IB in dependency order.
```

If all queued IBs are now ACCEPTED, the report ends with: *"All IBs accepted. Run `/write-beads` on each IB in numbered order."*

**End of Accept Mode — do not continue to the decomposition workflow.**

## Lock Mode

Promote a single IB from ACCEPTED → LOCKED. This is the gate downstream consumers (write-beads, write-tests) check via `_assert_ib_locked` — without this step those skills refuse the IB and point the engineer here.

Unlike `/write-intent --lock`, IBs do **not** have an engineer-judgment reason-gate or an ADR-017 Path-A/Path-B split. IBs are spec-graph artifacts whose Lock gate is mechanical: parent WS must be at status `ACCEPTED` or higher, every sibling IB in the same cohort (same parent WS) must be at status `ACCEPTED` or higher, and the IB's own fidelity audit must re-run clean.

Arguments: a single IB path (no glob — Lock Mode operates on one IB at a time).

### Steps

1. **Read the IB at the provided path.** Confirm Status is currently `ACCEPTED`. If any other status, refuse and name the current status:
   - `PROPOSED` → tell the engineer to run `/write-ibs --accept <IB-path>` first.
   - `LOCKED` → already locked; report the no-op and stop.
   - `DRAFT` / `TODO` / `QUEUED` / `ACTIVE` / `COMPLETED` → refuse with the IB's current status and the required `ACCEPTED` precondition.

2. **Parent WS gate.** Read the IB's `Spec:` header field. If it names a WS path:
   - Read the WS Status. If the WS Status is below `ACCEPTED` (i.e., `TODO`, `DRAFT`, or `PROPOSED`), refuse and name the WS path and its current status. The parent WS is the contract source; locking an IB whose contract has not been accepted creates downstream-of-pre-accepted-parent drift.
   - If `Spec:` is `none` (legacy stand-alone IB), skip this check — the cohort gate below still applies if any siblings exist.
   - If the WS path does not exist, refuse and tell the engineer to fix the broken `Spec:` reference via `/write-ibs --revise` before locking.

3. **Cohort coherence gate.** Walk `dekspec/impl-briefs/` (flat or `queued/` / `active/` / `completed/` subdirs) for sibling IBs whose `Spec:` field matches this IB's parent WS:
   - Every sibling must be at Status `ACCEPTED` or higher (`ACCEPTED` or `LOCKED`). If any sibling is below `ACCEPTED`, refuse and name each blocker with its current status. The "cohort coherence" rule prevents locking one IB while peers under the same WS are still in flight — the next IB the engineer locks would otherwise be operating against a partially-locked spec graph.
   - The IB being locked counts as its own cohort entry; it does not need to wait on itself.
   - If no siblings exist (single-IB cohort), the check passes trivially.

4. **Re-run Audit Mode.** Run the full Audit Mode procedure (conflict detection + fidelity audit) against this IB. If any severity-important-or-worse finding emerges, refuse and route the engineer to `--revise` (substantive) or `--review` (editorial). A LOCKED IB must have a clean audit at the moment of lock — the engineer's earlier `--accept` is not sufficient if the IB or its sources have drifted since.

5. **Promote.** Run the deterministic status walk:

   ```
   python ../_lib/scripts/artifact_ops.py transition <IB-path> --from ACCEPTED --to LOCKED --note "<note>" --engineer <engineer-or-agent>
   ```

   Where `<note>` records the path taken: `"Locked via /write-ibs --lock — parent WS + cohort gates clean, fidelity audit re-run clean"`. The script flips Status, bumps Modified (no-op for IBs which lack a Modified field), and appends the Amendment Log row in one step. Surface stderr on non-zero exit and STOP.

6. **Report:**

   ```
   ✅ <IB-id> promoted ACCEPTED → LOCKED.
      Parent WS: <WS-id> (<status>)
      Cohort: <N> sibling IB(s), all at ACCEPTED or higher
      Audit: clean
      Next: this IB is now LOCKED — author beads from it via `/write-beads <IB-path>`.
   ```

   If the cohort still has ACCEPTED-only siblings (none yet LOCKED besides this one), append:

   > Note: <M> sibling IB(s) remain at ACCEPTED. Run `/write-ibs --lock` on each in implementation order as their parent-WS + cohort gates settle.

**End of Lock Mode — do not continue to the decomposition workflow.**

## Review Mode

Walk through open issues interactively — present each issue with context and a recommendation, resolve with the engineer one at a time.

Arguments: the IB path.

### Steps

1. Read the IB at the provided path
2. Parse the `## Open Issues` section. Collect all unchecked items (`- [ ]`).
3. If no unchecked items exist: "No open issues in [path]. Nothing to review." **End of Review Mode.**
4. Read the artifact's Goal, Constraints & Decisions, Done When, and Out of Scope sections for context.
5. Read the source spec (from the Spec header field) and governing ADRs to check for cross-artifact relevance.
6. Present a summary:
   ```
   REVIEW SESSION: [path]
   Engineer review: [current field value]
   Open issues: [N] ([M] blocking, [K] non-blocking)
   
   Starting guided review...
   ```
7. For each unchecked issue, in order:
   a. Present the issue:
      ```
      ───────────────────────────────────────
      ISSUE [N/total]: [issue description]
      Source: [source]
      Severity: [blocking / non-blocking]
      ───────────────────────────────────────
      ```
   b. Analyze the issue against the current IB content:
      - Has this issue already been addressed by changes to the IB since it was logged?
      - Is the issue still valid given the current state of the source spec, governing ADRs, and sibling IBs?
      - What would resolving this issue require — a change to this IB, a resync from the spec, or an upstream change?
   c. Present a recommendation:
      ```
      RECOMMENDATION: [resolve / revise IB / defer / dismiss]
      
      [Specific explanation — what to change and why, or why to defer/dismiss]
      
      [If resolve or revise: show the proposed change]
      ```
   d. Wait for the engineer's response.
   e. Based on response:
      - **Resolve** — check off the issue, append resolution: `- [x] [Issue] — **Source:** ... — **Severity:** ... — **Resolved:** [today] [resolution summary]`
      - **Revise** — apply the agreed change to the IB body, then check off the issue with resolution note
      - **Defer** — leave unchecked, optionally update the issue description with new context
      - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`
8. Update **Modified** date. If any IB body changes were made, reset the `Engineer review` field to `[ ] Not yet reviewed — do not run /write-beads until checked` (changes invalidate prior approval).
9. Run **Conflict Detection** and **Fidelity Audit** on the revised IB if any body changes were made.
10. Present summary:
    ```
    REVIEW COMPLETE: [path]
    
    Resolved: [N]
    Dismissed: [N]
    Deferred: [N]
    
    [If blocking issues remain]: ⚠️  [N] blocking issues remain — IB should not be approved.
    [If no blocking issues remain]: ✅ No blocking issues remain — IB is ready for engineer approval.
    [If body changes were made]: Engineer review has been reset — re-approve before /write-beads.
    ```

**End of Review Mode — do not continue to the decomposition workflow.**

## Resync Mode

Run this when `--resync` is present. Use when the spec has changed and specific IBs need to be refreshed against the updated spec. The file path may be a single IB or a glob pattern.

For each resolved IB file:

1. Read the IB
2. Identify the source spec from the IB's Spec Context section
3. Read the current version of the spec
4. Read all ADRs listed in the IB's Governing ADRs table (applying supersession rules as in the decomposition workflow)
5. Diff the IB's embedded spec context against the current spec — identify what changed
6. Present the changes to the engineer:
   ```
   IB: [IB-NNN-component-brief.md]
   Spec changes affecting this IB:
     - [description of each change]
   
   Proposed updates to Constraints & Decisions:
     - [what will change]
   
   Proceed with update? (y/n)
   ```
7. If approved: update the IB's Spec Context (re-copy relevant sections verbatim), re-reconcile Constraints & Decisions, and update the `Modified` date
8. Run **Conflict Detection** on the updated IB
9. Run **Fidelity Audit** on the updated IB (content completeness + cohesion checks)
10. Run **coupling checks** against all sibling IBs for the same spec — the resync may have changed the IB's scope or constraints in ways that affect coupling with siblings.
11. If all checks pass — save. Reset `Status` to `PROPOSED` (the update invalidates prior acceptance).
12. If any check fails — report failures, do not save until resolved.

After processing all IBs:

```
UPDATE RESULTS:
  ✅ IB-001-component-brief.md — updated, needs re-acceptance
  ✅ IB-002-component-brief.md — updated, needs re-acceptance
  ⏭️  IB-003-component-brief.md — no spec changes affect this IB, skipped
```

If any beads exist for updated IBs, warn: "Beads exist for updated IBs. Open beads should be deleted and re-created after re-acceptance. Run `br delete <bead-id>` for affected beads."

**End of Resync Mode — do not continue to the decomposition workflow.**

## Revise Mode

Run this when `--revise` is present. Use when the engineer has review notes — from a review session, present annotations, or their own analysis — that need to be worked into an IB.

Arguments after the IB path are the engineer's notes. These can be:
- **Inline text** — free-form notes directly in the arguments
- **A file path** — if the remaining argument is a path to an existing `.md` or `.txt` file, read it as the notes

### Steps

1. Read the IB
2. Read the engineer's notes (inline or from file)
3. Classify each note as one of:
   - **Constraint change** — affects Constraints & Decisions (e.g., "add bfloat16 dtype constraint", "remove the fallback path")
   - **Scope change** — affects Files to Modify, Out of Scope, or the IB's boundary (e.g., "this shouldn't touch graph_cache.py", "add the migration script")
   - **Clarity fix** — affects Done When, Spec Context, or domain constraints (e.g., "done-when for endpoint X is too vague", "clarify which CUDA device")
   - **Structural issue** — affects dependency ordering, IB splits, or requires a new IB (e.g., "this should be two IBs", "this depends on IB-003 not IB-001")
   - **Rejection** — the note indicates a fundamental problem that can't be patched (e.g., "this IB is based on a wrong assumption about the data model")
4. Present the classified notes and proposed changes:
   ```
   REVISION PLAN for [IB-NNN-component-brief.md]:
   
   Constraint changes:
     - [note] → update C&D entry: [proposed change]
   
   Scope changes:
     - [note] → update Files to Modify / Out of Scope: [proposed change]
   
   Clarity fixes:
     - [note] → update [section]: [proposed change]
   
   Structural issues (require engineer decision):
     - [note] → [what needs to happen]
   
   Proceed with non-structural changes? (y/n)
   ```
5. Wait for engineer approval. Structural issues and rejections always require explicit engineer direction before proceeding.
   - If the engineer approves a structural change that requires creating new IBs (split this IB, merge with another IB, re-cut boundaries), **exit Revise Mode**. Instruct the engineer: "This structural change requires re-decomposition. Run `/write-ibs <spec-path>` to re-derive the affected IBs, or manually restructure and re-run `/write-ibs --audit` on the results." Revise Mode can only modify a single existing IB — it cannot create or delete IBs.
6. Apply approved non-structural changes. Update the `Modified` date.
7. If the revision introduces ambiguity, contradictions, or concerns that cannot be fully resolved during this revision, log them as new entries in the `## Open Issues` section with **Source:** `review` and appropriate severity. Inform the engineer: "New open issues were logged. Run `--review` to walk through them."
8. Run **Conflict Detection** on the revised IB
9. Run **Fidelity Audit** on the revised IB (content completeness + cohesion checks)
10. Run **coupling checks** against all sibling IBs for the same spec — the revision may have introduced coupling problems (e.g., a scope change that now overlaps with another IB's files, a new C&D entry that creates common coupling). Read sibling IBs from `dekspec/impl-briefs/` matching the same spec reference.
11. If all checks pass — save. Reset the `Engineer review` field to `[ ] Reviewed and approved` (the revision invalidates prior approval).
12. If any check fails — report failures, do not save until resolved.

### Examples

Inline notes:
```
/write-ibs --revise IB-001-component-brief.md done-when criteria for the /synthesize endpoint are too vague, need explicit status codes. Also remove graph_cache.py from files to modify — that belongs in IB-002.
```

Notes from file:
```
/write-ibs --revise IB-001-component-brief.md review-notes.md
```

**End of Revise Mode — do not continue to the decomposition workflow.**

## Dry-Run Mode

Preview the decomposition without drafting full IBs. Use to validate spec scoping before committing to the expensive decomposition pass.

### Input

Spec path: the argument after `--dry-run`.

### Steps

1. Read the spec
2. Read all ADRs referenced in the spec (applying supersession rules)
3. Identify the independently verifiable units of work — the same decomposition logic as the full workflow, but produce only titles and one-line scope descriptions, not full IB drafts
4. Map the dependency graph between units
5. Identify which silent failure domains are touched (injection, quantization, graph, CUDA)
6. Run the IB Count Assessment
7. **Lightweight decomposition spot-check (1 round only).** Run a subset of the decomposition checklist for fast feedback:

   **Cohesion (per candidate):**
   - [ ] Can state purpose in one sentence without "and" connecting unrelated concerns
   - [ ] Single primary failure domain

   **Coupling (across candidates):**
   - [ ] No two candidates modify the same file's functions (content coupling check)
   - [ ] No circular dependencies in the graph

   **Graph:**
   - [ ] DAG is valid
   - [ ] Depth > 3 flagged
   - [ ] Anti-pattern scan: kitchen sink, God IB, circular dependency

   **Checks deferred to full run:** passenger files, narrow dependency surface, control coupling, transitive leakage, fan-out limits, stability of high-fan-in IBs, all fidelity audit checks, conflict detection.

8. Present:

```
DRY RUN — [spec path] (1 round, lightweight checks)

Estimated IBs: [N] ([assessment from count table])

Dependency graph:
  IB-1: [component] — no dependencies
  IB-2: [component] — no dependencies
  IB-3: [component] — depends on IB-1
  IB-4: [component] — depends on IB-1, IB-3
  IB-5: [component] — depends on IB-4

Silent failure domains: [list]
Governing ADRs: [list]

Decomposition spot-check:
  [✅/⚠️/❌ per check run — list results]

Checks deferred to full run: passenger files, dependency surface,
  control coupling, transitive leakage, fan-out, fidelity audit

[If 7-10]: ⚠️  Consider whether this is two subsystems in one spec.
[If 10+]:  ❌ Too large — split the spec before decomposing.

Proceed with full decomposition? (yes / no / rescope)
```

If the engineer says "yes," proceed to the full **Decomposition Mode** workflow starting at Phase 1 step 1. The full run re-derives candidates from scratch with full decomposition checklist rigor — the dry-run's candidates are guidance, not a starting point. Phase 1 can reuse already-loaded sources (spec, ADRs) without re-reading them.

If "no" or "rescope," stop.

**End of Dry-Run Mode.**

## Input

Spec path: $ARGUMENTS

If no path is provided, list all `.md` files in `dekspec/working-specs/` and ask the engineer to select one.

## Safety Check

Before proceeding, check if IBs already exist for this spec in `dekspec/impl-briefs/`:
- If IBs exist in `queued/` — warn: "IBs already exist for this spec. Continuing will regenerate them. Continue or abort?"
- If IBs exist in `active/` or `completed/` — warn: "IBs for this spec are already in progress or completed. This is unusual. Continue or abort?"

Wait for engineer confirmation before proceeding.

## L12 Precondition — `blocking_pre_ib` open_issues must be clean

**Per L12-WS-BLOCKING-PRE-IB-CLEAN audit rule + ADR-013 severity vocabulary.** A Working Spec that has walked past PROPOSED (i.e., status is `ACCEPTED`, `IMPLEMENTING`, `TESTPASS`, `TESTFAIL`, `MERGED`, or `LOCKED`) must not carry any P1 open_issues. P1 is the canonical severity for the legacy `blocking_pre_ib` / `blocking_pre_code` / `blocking` artifact-side aliases — these signal spec-blocking questions that must be settled BEFORE IBs land. This is the "Clarify Before Plan" gate documented in `templates/working-spec-template.md` ("Zero `blocking (pre-IB)` open issues must remain when `/write-ibs` is invoked.").

Before entering the decomposition workflow, run the gate check:

```bash
dekspec check validate <spec-path> --json
```

Read the returned IR's `status` field and `open_issues` array.

- If `status` is `DRAFT` or `PROPOSED`: skip the gate (P1 open_issues are expected during authoring). Proceed to Workflow.
- If `status` is `ACCEPTED` or higher, filter `open_issues` for entries with `severity == "P1"`.
  - If the P1 list is empty: gate clean, proceed to Workflow.
  - **If any P1 entries remain: REFUSE.** Emit an error naming each unresolved issue (the `text` field), the WS's `id`, and pointing the engineer at the WS's `## Open Issues` section. Suggested error shape:

    ```
    Refuse: /write-ibs against {ws_id} ({status}) blocked by L12 — {N} unresolved P1
    open_issue(s) (`blocking_pre_ib` semantic per ADR-013):

      1. {issue.text (first 120 chars)}
      2. ...

    Resolve each in the WS's `## Open Issues` section (settle the question
    and demote the severity to P2/P3 with a resolution note, OR check the
    `[x]` box), or unlock the WS back to PROPOSED until the blockers
    resolve. Re-run /write-ibs once the gate is clean.
    ```

  Exit without writing any IB.

**Why this exists:** the IR field already collapses `blocking_pre_ib` (and its sibling aliases) to P1 per ADR-013; the audit rule L12-WS-BLOCKING-PRE-IB-CLEAN fires when these reach ACCEPTED. Pairing the audit (a doctor-time finding) with this skill-time precondition closes the gap where an engineer could `/write-ibs` against a WS whose blockers were never resolved.

**No bypass flag.** The whole point of the gate is mechanical enforcement; if override is needed, unlock the WS back to PROPOSED first.

## Workflow

### Phase 1: Gather Sources

1. Read the Planning Agent role from `dekspec/project-context.md`
2. Read `dekspec/domain-glossary.md` for canonical domain terminology
3. Read the finalized spec from the provided path (default: `dekspec/working-specs/`)
4. Read all ADRs referenced in the spec. For each ADR, check its Status and Supersession fields:
   - If `Superseded by` names another ADR — read the superseding ADR instead. Do NOT use the superseded ADR's decisions.
   - If `Proposed` — note it as proposed, not accepted. Flag to the engineer if it governs a critical constraint.
   - If `Accepted` — use as authoritative.
4. Read the IB template from `dekspec/templates/implementation-brief-template.md`

### Phase 2: Decompose (with iteration)

5. Draft all candidate IBs — one per independently verifiable unit of work — without saving yet. Apply the **IB Decomposition Principles** (cohesion, coupling, anti-patterns — see sections below) when deciding where to cut boundaries.
6. Run the **Decomposition Checklist** (see section below) against all candidates
7. **Classify each failure:**
   - **Auto-fixable** — missing file, passenger file, narrow interface needed, incomplete dependency declaration. Fix immediately and re-check.
   - **Requires re-decomposition** — scattered responsibility, circular dependency, kitchen sink, artificial split, God IB, fan-out explosion. Restructure the candidate IBs (merge, split, or re-cut boundaries) and re-run the full checklist.
   - **Requires engineer decision** — ambiguous scope, conflicting ADRs about where a concern belongs, genuine tension between cohesion and coupling that could be resolved multiple ways.

8. **Iterate up to 3 rounds.** Most decompositions pass after round 1. Round 2 catches cascading issues from round 1 fixes. Round 3 signals a fundamental problem — likely in the spec, not the cut. Each round:
   - Fix all auto-fixable issues
   - Re-decompose if structural issues were found
   - Re-run the full decomposition checklist
   - If all checks pass → proceed to Phase 3
   - If structural issues persist → re-decompose and try the next round

9. **After 3 rounds, if issues remain:** STOP. The problem is almost certainly upstream (ambiguous spec, missing ADR decisions, conflicting scope). Present the unresolved issues to the engineer:
   ```
   DECOMPOSITION QUALITY GATE — 3 rounds completed, [N] issues unresolved:

   Round 1: [M] issues found, [fixed] auto-fixed, [redecomp] required re-decomposition
   Round 2: [M] issues found, [fixed] auto-fixed, [redecomp] required re-decomposition
   Round 3: [M] issues remaining:
     - [issue description — why it could not be resolved]
     - [issue description — requires engineer decision]

   Options:
     A) Resolve these issues and re-run (provide guidance)
     B) Accept the current decomposition with known issues
     C) Abort and rescope the spec
   ```
   Wait for engineer decision before proceeding.

### Phase 3: Present & Confirm

10. Map the full IB dependency graph. Present to the engineer with the decomposition quality summary:
    ```
    DECOMPOSITION COMPLETE — [N] IBs, [rounds] resolution rounds

    Dependency graph:
      IB-001: [component] — no dependencies
      IB-002: [component] — depends on IB-001
      IB-003: [component] — depends on IB-001
      IB-004: [component] — depends on IB-002, IB-003

    Decomposition checklist: all [N] checks passed
    [Or: [N] checks passed, [M] accepted with known issues (see above)]

    Confirm or correct before proceeding.
    ```
11. Wait for engineer confirmation. If the engineer corrects the graph (reorders, merges, splits), re-run the decomposition checklist on the corrected structure before proceeding. Up to 2 engineer correction rounds. If the checklist still fails after 2 corrections, present the remaining issues and proceed only with the engineer's explicit acceptance of the known issues.
12. Assign IB numbers based on confirmed dependency order (see IB Numbering)

### Phase 4: Draft, Audit, Save (with iteration per IB)

For each IB, in dependency order:

13. Draft the full IB content (all template sections populated from spec, ADRs, and ICs)
14. Run **Conflict Detection**
15. Run **Fidelity Audit**
16. **Classify each failure:**
    - **Auto-fixable** — missing C&D entry, unexplained n/a, spec context scope bleed, missing escalation protocol, passenger file. Fix by re-reading source documents and correcting the IB.
    - **Requires re-decomposition** — fidelity audit reveals the IB can't be made self-contained because the cut is wrong (e.g., a needed constraint belongs to another IB's scope, or testing this IB requires another IB's implementation). This means the decomposition was flawed. **Escalate to the engineer:**
      ```
      DECOMPOSITION ISSUE discovered during IB-NNN drafting:
        [description of why this IB cannot be made self-contained]
      
      Suggest: [merge with IB-MMM / split differently / add dependency]
      Approve restructure? (yes / no / alternative)
      ```
      If approved, restructure the affected IBs (merge, split, or re-cut). Then restart Phase 4 from step 13 for ALL IBs in the restructured set — not just the failing IB. Restructuring may change IB numbers, dependency order, and file assignments, so previously-saved IBs in the affected set must be re-drafted and re-audited. IBs outside the restructured set (no dependency on the affected IBs) do not need to be restarted.
    - **Requires engineer decision** — conflicting ADRs, ambiguous spec, missing information that can't be inferred.

17. **Iterate up to 2 rounds per IB.** Content issues are mechanical — if they can't be fixed in 2 rounds, the problem is structural (bad decomposition boundary), not content. Each round:
    - Fix all auto-fixable issues
    - Re-run Conflict Detection and Fidelity Audit
    - If all checks pass → save the IB
    - If issues persist → try round 2

18. **After 2 rounds per IB, if issues remain:** The boundary is likely wrong. STOP for that IB and escalate to the engineer as a decomposition issue (step 16, "requires re-decomposition"). Do NOT save an IB that fails the fidelity audit. Other IBs that do not depend on the failing IB may proceed.

### Phase 5: Final Cross-IB Validation (1 round — escalate immediately)

After all IBs are drafted and individually audited:

19. Run the **coupling checks from the Fidelity Audit** across the full IB set one final time — content coupling, common coupling, control coupling, transitive leakage, fan-out, stability of high-fan-in IBs. This is a single pass — cross-IB issues at this stage indicate a decomposition problem that per-IB iteration cannot fix.
20. If cross-IB issues are found that were not caught during per-IB auditing (possible because some coupling issues only emerge when viewing the full set):
    - Fix auto-fixable issues (e.g., a shared type that appeared in IB-3 but wasn't in the foundation IB)
    - Escalate structural issues to the engineer immediately — do not iterate
21. Save all passing IBs. Report:
    ```
    IB GENERATION COMPLETE:
      ✅ IB-001: [title] — all checks passed (N rounds)
      ✅ IB-002: [title] — all checks passed (N rounds)
      ⚠️  IB-003: [title] — accepted with known issues: [list]
      ❌ IB-004: [title] — not saved, [N] unresolved issues (requires engineer)

    Total resolution rounds: [N] decomposition + [M] per-IB
    ```

## IB Decomposition Principles

Two forces drive decomposition:

1. **High cohesion within each IB** — everything in the IB serves one purpose
2. **Low coupling between IBs** — IBs interact through narrow, well-defined interfaces

### Cohesion (what goes IN an IB)

Cohesion is strongest when every element in the IB contributes to a single well-defined task (functional cohesion). Weaker forms are acceptable only when explicitly justified.

- **Functional unity.** An IB has one reason to exist and one primary way it can fail. Test: can you state its purpose in one sentence where removing any clause makes it incomplete? If the sentence uses "and" to connect two unrelated concerns, it is two IBs.
- **No passengers.** Every file in the IB serves its purpose. If you remove a file and the acceptance criteria can still be met, that file belongs in a different IB. The converse: if a file is needed but missing, the IB's scope is incomplete.
- **Single primary failure domain.** An IB has one domain it primarily operates in. Incidental contact with another domain is fine if the primary concern is clear and acceptance criteria are unambiguous about which behavior is verified.
- **Independently testable.** You can write a meaningful test for the IB's output without another IB's implementation. This is the concrete proof of sufficient cohesion.
- **No scattered responsibility.** A single concern must not be split across multiple IBs. If changing one business rule would require modifying three IBs, the concern is scattered — consolidate the pieces that serve that rule into one IB. (Conversely, if one IB contains pieces of three unrelated concerns, it is a kitchen sink.)

**Weak cohesion forms to watch for and reject:**
- **Temporal cohesion** — "these changes all need to happen for the release." That is a schedule constraint, not a functional unit. Each change is its own IB.
- **Logical cohesion** — "these are all the graph-related changes." Domain affinity is not functional unity. Two graph changes that serve different purposes are two IBs.
- **Procedural cohesion** — "step 1 then step 2 then step 3" where the steps serve different purposes. Sequential steps that serve one purpose (e.g., parse → validate → transform for a single data pipeline) are fine. Sequential steps that serve different purposes (e.g., create schema → seed data → build API) are separate IBs with dependencies.

### Coupling (what goes BETWEEN IBs)

Coupling should be as loose as possible. Data coupling (passing simple data between IBs) is the target. Stronger forms must be identified and eliminated or explicitly managed.

**Coupling types, from acceptable to unacceptable:**

| Type | Description | Acceptable? |
|---|---|---|
| **Data coupling** | IBs communicate through simple data — types, function signatures, return values | Yes — target this |
| **Stamp coupling** | IB-A produces a complex structure, IB-B uses only part of it | Acceptable if unavoidable, but prefer narrowing the interface |
| **Control coupling** | IB-A's output includes a flag or mode that changes IB-B's behavior | Avoid — IB-B should not change behavior based on IB-A's internal decisions. Extract the decision into IB-B's own constraints. |
| **Common coupling** | Two IBs share mutable global state (database table, config, cache) | Must be explicit — extract shared state into its own IB or declare the dependency with the coupling documented in C&D |
| **Content coupling** | One IB modifies the internals of code another IB also modifies | Never in parallel — same function requires sequential dependency or consolidation |

**Additional coupling principles:**

- **Shared foundations extracted.** Types, models, constants, or utilities needed by multiple IBs go in a foundation IB that others depend on. Prevents parallel agents from inventing the same abstractions.
- **Narrow dependency surface.** An IB exposes the minimum interface needed by dependent IBs — not the full implementation, just what the next IB consumes. (Interface Segregation: don't force a dependent IB to depend on interfaces it doesn't use.)
- **No transitive leakage.** If IB-3 depends on IB-2, which depends on IB-1, then IB-3 should need nothing from IB-1's internals. IB-2 must fully encapsulate whatever it consumes from IB-1. If IB-3 needs to reach through IB-2 to use IB-1's types or functions directly, the boundary between IB-1 and IB-2 is wrong.
- **Stability principle.** IBs with high fan-in (many other IBs depend on them) should be the simplest and most stable. Foundation IBs that define shared types should contain minimal logic. Conversely, IBs with high fan-out (depend on many other IBs) are inherently riskier and should be scrutinized for scope creep.
- **Fan-out limit.** An IB that depends on more than 3 other IBs is a red flag — it may be trying to orchestrate too much. Consider whether it can be split or whether some dependencies are artificial.

### Decomposition Checklist

Run after drafting candidate IBs, before presenting the dependency graph to the engineer:

**Cohesion checks (per IB):**
- [ ] Can state the IB's purpose in one sentence without "and" connecting unrelated concerns
- [ ] Removing any file would make at least one acceptance criterion unsatisfiable (no passengers)
- [ ] Single primary failure domain — if multiple domains are touched, one is clearly primary
- [ ] Acceptance criteria test one coherent behavior, not multiple unrelated behaviors
- [ ] Can write a meaningful test without another IB's implementation
- [ ] Not temporal cohesion ("all needed for the release") or logical cohesion ("all graph-related")
- [ ] No scattered responsibility — changing one business rule does not require modifying multiple IBs

**Coupling checks (across IBs):**
- [ ] No two IBs modify the same function without an explicit dependency between them (no content coupling)
- [ ] All dependencies are through data interfaces — types, signatures, return values (data coupling)
- [ ] No control coupling — no IB's output includes a flag or mode that changes another IB's behavior
- [ ] Shared types/models/constants are in a foundation IB, not duplicated across IBs
- [ ] Each dependency surface is narrow — dependent IB needs specific outputs, not the full implementation
- [ ] No hidden common coupling (shared DB tables, config mutations, cache state) — all shared state is documented or extracted
- [ ] No transitive leakage — IB-3 does not need IB-1's internals to use IB-2's output
- [ ] No IB depends on more than 3 other IBs (fan-out check — investigate if exceeded)
- [ ] High fan-in IBs (many dependents) are simple and stable — they define interfaces, not complex logic

**Graph checks:**
- [ ] Dependency graph is a DAG (no cycles)
- [ ] Depth > 3 has been investigated — is the depth inherent to the problem or an artifact of the cut?
- [ ] Independent IBs (no mutual dependency) are not artificially chained
- [ ] No anti-patterns present (see below)

### Anti-Patterns

**Cohesion anti-patterns:**

| Anti-pattern | Sign | Fix |
|---|---|---|
| **Kitchen sink** | Many files, multiple failure domains, unrelated acceptance criteria | Split along failure domain boundaries — one primary domain per IB |
| **Artificial split** | Two IBs can't be tested independently despite being separate | Reunite — splitting destroyed cohesion without reducing coupling |
| **Trivial IB** | Work is too small to justify IB + bead + test + PR overhead | Absorb into a related IB |
| **Passenger files** | Files listed but not needed for acceptance criteria | Remove; create separate IB if they need changes |
| **Shotgun surgery** | A single business rule change would require modifying multiple IBs | Responsibility is scattered — consolidate the pieces that serve that rule |
| **Temporal bundle** | IB groups unrelated changes because they're "needed for the same release" | Split into functionally cohesive IBs; the schedule is not a design constraint |

**Coupling anti-patterns:**

| Anti-pattern | Sign | Fix |
|---|---|---|
| **Hidden common coupling** | Two IBs modify same DB table/config but declare no dependency | Extract shared state into its own IB or add explicit dependency |
| **Stamp coupling chain** | IB-1 produces a large structure, downstream IBs each use one field | Narrow the interface — IB-1 produces what each consumer actually needs |
| **Control coupling** | IB-A's output includes a flag that changes IB-B's behavior path | IB-B should own its own decision; move the logic into IB-B's constraints |
| **Transitive leakage** | IB-3 imports types/functions from IB-1 to use IB-2's output | IB-2's interface is incomplete — it should encapsulate what it consumes from IB-1 |
| **God IB** | One IB that every other IB depends on, containing mixed concerns | Split the God IB into focused foundation IBs — types in one, utilities in another |
| **Circular dependency** | IB-A depends on IB-B and IB-B depends on IB-A (directly or transitively) | Restructure — extract the shared concern into a foundation IB both depend on |
| **Feature envy** | An IB spends more time working with another IB's data than its own | Responsibility is misplaced — move the envious logic to the IB that owns the data |
| **Inappropriate intimacy** | Two IBs that reference each other's internal implementation details in their C&D sections | Decouple — define a clean interface between them; each IB should know only the other's public contract |
| **Fan-out explosion** | An IB depends on 4+ other IBs | IB is likely orchestrating too much — split it or question whether all dependencies are real |

### Minimum Viable IB

Not everything warrants its own IB. Minimum bar:
- Changes at least one file in a functionally meaningful way
- Has at least one testable acceptance criterion
- Produces something a dependent IB needs OR is a terminal consumer
- Can be reviewed as one coherent PR

Below this bar, absorb the work into a related IB.

## IB Content Rules

- **Log corrections.** When any mode (decomposition, audit, accept, review, revise, resync) corrects a domain misinterpretation — wrong term usage, confused concepts, contradicted architectural facts — invoke `/write-ggc --log` with the correction details before proceeding. This feeds the glossary promotion pipeline.
- Copy spec context **verbatim** — only the sections directly relevant to this IB's scope. Do not include spec sections that apply to other IBs. Do not summarize what you do include.
- The coding agent has no access to the spec; everything it needs must be in the IB
- State exact files to modify
- State domain constraints explicitly: CUDA device, tensor dtype, read/write path, precision threshold, do-not-touch functions
- List all governing ADRs in the **Governing ADRs** table (number + title only) — for traceability. Do not instruct the coding agent to load them.
- Merge spec context, ADR decisions, and interface contract constraints into a single **Constraints & Decisions** section — one entry per concern, already reconciled. Where sources agree, write one rule. Where they conflict, resolve with the engineer first (see Conflict Detection), then write the resolved rule. Use exactly this format for every entry: `- **[topic]:** [what to do — concrete, not a reference to a document]`. The coding agent reads only this section for implementation guidance.
- **Interface Contracts:** If the spec references an interface contract, extract the specific constraints it imposes on THIS IB's scope and embed them as entries in Constraints & Decisions. Copy the path into the Interface Contracts section for traceability only. If no contract exists but the IB introduces a new API boundary, flag this to the engineer — do not invent a contract.
- **Probe Results:** If the spec or ADRs reference any experimental validation, extract the specific finding that governs THIS IB's behavior and embed it as an entry in Constraints & Decisions. Copy a one-line finding summary into the Probe Results section for traceability only. If none, write "none."
- **Out of Scope:** Every boundary a reasonable engineer might assume is included must be listed here if it belongs to a different IB or is not in scope at all. Do not leave this section vague.
- **Escalation Protocol:** Copy the Escalation Protocol verbatim from the template — do not modify it.
- **Done When:** Each criterion must map to a specific test, observable output, or measurable behavior. Not "works correctly" — instead: "function X returns Y given input Z", "endpoint returns 200 with body matching schema", "eval score >= threshold on dataset D". If a criterion cannot be stated this concretely, ask the engineer before writing it.
- **Golden I/O (required for numerical/data transformation IBs):** Include 2-3 concrete input/output pairs with exact values in the Done When section. For tensor operations, provide small tensors (2x2 or 3x3) with exact expected output values. For non-numerical IBs (pure wiring, configuration), replace with Golden State Transitions showing before/after system states. These values are provided by the engineer or derived from a reference implementation — the coding agent cannot invent them. If Golden I/O is needed but the engineer has not provided it, STOP and ask before proceeding.
- **Test Promotion Criteria:** List which Working Spec business rules and Interface Contract constraints this IB's tests should reference in their docstrings for promotion candidacy. Format: `Promotion refs: WS-NNN Rule N, IC-NNN Constraint N`. This enables automated test promotion after bead closure.
- Reference relevant checklists: `dekspec/templates/checklists/python-quality-checklist.md`, `dekspec/templates/checklists/security-checklist.md`, `dekspec/templates/checklists/eval-quality-checklist.md`
- The template (`dekspec/templates/implementation-brief-template.md`) must be completely filled out. Every section, every placeholder. If information is missing, ask the engineer before proceeding — do not guess or leave blanks.
- The **Precedence** section must be copied verbatim into every IB — do not modify the resolution order.

## IB Count Assessment

| IB count | Assessment |
|----------|-----------|
| 1-3 | Normal — focused feature or component |
| 4-6 | Acceptable — complex subsystem with multiple interacting components |
| 7-10 | Warning — review whether this is actually two subsystems in one spec |
| 10+ | Too large — split the spec |

Split the spec if:
- A new engineer can't understand the full scope in under 30 minutes
- You can't describe the IB dependency graph from memory
- The spec spans two silent failure domains (injection, quantization, graph, CUDA)

## Dependencies and Production Gates

| Type | Meaning | Enforced by |
|------|---------|------------|
| Technical | Next IB's code depends on this IB's code being merged | Bead `depends_on` field |
| Production gate | Next IB depends on this IB's behavior verified in production | Engineer discipline |

Production gates sit between IBs, not within them. The observable must be stated specifically — not "looks good" but a concrete checkable signal.

## Conflict Detection (called from Phase 4, step 14)

Before saving any IB, perform an explicit conflict-detection pass:

1. **ADR vs. ADR** — do any two ADR rules embedded in this IB contradict each other? (e.g., one says "always use bfloat16", another says "upcast to float32 at boundary")
2. **ADR vs. spec context** — does any ADR rule contradict a statement in the embedded spec context?
3. **Constraint vs. checklist** — does any domain constraint or ADR rule contradict a pattern prescribed by the referenced checklists?

For each conflict found:
- State the conflict explicitly: "ADR-NNN says X; spec section Y says Z — these conflict."
- Ask the engineer to resolve it before proceeding.
- Do NOT guess, pick one silently, or write the IB with the conflict unresolved.

If no conflicts are found, state: "No conflicts detected." and proceed to fidelity audit.

## Fidelity Audit (called from Phase 4, step 15; coupling checks also in Phase 5, step 19)

The IB must be fully self-contained. The coding agent and bead creator will not read ADRs, interface contracts, or the Working Spec — they rely entirely on what is inlined in the IB. This audit verifies that inlining is complete and that cohesion/coupling principles are met.

For each IB, verify:

**Content completeness:**
- [ ] **Constraints & Decisions is populated** — not empty, not placeholder text
- [ ] **Every governing ADR's relevant decision is inlined** — for each ADR in the Governing ADRs table, at least one entry in Constraints & Decisions traces back to that ADR's decision. If an ADR is listed but no corresponding C&D entry exists, the decision was not inlined.
- [ ] **Interface contract constraints are embedded in C&D** — not only referenced by path in the Interface Contracts section. If the Interface Contracts section lists a path but no C&D entry reflects its constraints, the contract was not inlined.
- [ ] **Probe Results section is populated or "none"** — if experimental findings exist and are referenced, they are embedded in C&D, not only referenced by path
- [ ] **C&D entries are concrete rules, not document references** — no entry says "see ADR-NNN" or "per the interface contract." Every entry states what to do directly.
- [ ] **Domain Constraints table has no unexplained n/a values** — if the spec specifies a value for a constraint (CUDA device, dtype, read/write path, precision threshold), the IB must carry it. An n/a is valid only when the constraint genuinely does not apply to this IB's scope.
- [ ] **Spec Context is scoped to this IB only** — does not include sections that belong to other IBs
- [ ] **Done When criteria are specific and verifiable** — each criterion maps to a test, observable, or measurable output, not vague language like "works correctly"
- [ ] **Out of Scope is not empty** — at least one boundary is listed
- [ ] **Escalation Protocol is present and verbatim from template**
- [ ] **Files to Modify lists files that exist in the repo** — verify with Glob
- [ ] **Code-state assertions in C&D are verified** — for each C&D entry that asserts something about the current state of a file (e.g., "function X exists," "import Y is already present," "lines N-M implement pattern P"), verify the assertion by reading or grepping the relevant file. Wrong code-state claims directly mislead the coding agent.
- [ ] **Golden I/O is present for numerical/data transformation IBs** — if the IB involves tensor operations, serialization, scoring, or data transformation, Done When must include 2-3 concrete input/output pairs with exact values. If the IB is non-numerical, Golden State Transitions are acceptable. If neither is present and the IB involves computation, flag as a failure.
- [ ] **Test Promotion Criteria is present** — the IB lists which WS business rules and IC constraints its tests should reference for promotion candidacy. Format: `Promotion refs: WS-NNN Rule N, IC-NNN Constraint N`.

**Cohesion checks (per IB):**
- [ ] **Functional unity** — IB purpose can be stated in one sentence. If the sentence has "and" connecting two unrelated concerns, cohesion is suspect.
- [ ] **No passenger files** — every file in Files to Modify is necessary to satisfy at least one Done When criterion. Grep the Done When section for each file; if a file is not referenced by any criterion, it may be a passenger.
- [ ] **Single primary failure domain** — if the IB's Domain Constraints span multiple domains (e.g., both CUDA and graph), one is clearly primary and the acceptance criteria focus on that domain.
- [ ] **Acceptance criteria are coherent** — all Done When criteria relate to the IB's stated purpose. No criterion tests a behavior that belongs to a different IB.

**Coupling checks (across all IBs in this batch):**
- [ ] **No content coupling** — for each file that appears in multiple IBs, verify they modify different functions. If two IBs modify the same function, one must depend on the other or they must be consolidated. Check with Grep for function names across IB Files to Modify lists.
- [ ] **Dependencies are data-only** — for each dependency in the graph, verify the dependent IB needs only a type, return value, or function signature from the upstream IB — not shared mutable state.
- [ ] **No control coupling** — no IB's C&D section describes producing a flag or mode that changes another IB's behavior. Each IB owns its own behavioral decisions.
- [ ] **No hidden common coupling** — check if any two IBs write to the same database table, config file, or cache without declaring a dependency. Grep IB descriptions and C&D sections for database/config/cache references.
- [ ] **Shared types extracted** — if the same type, model, or constant appears in multiple IBs' C&D sections, verify it is defined in a foundation IB that others depend on.
- [ ] **No transitive leakage** — for each IB with a dependency depth > 1, verify it does not reference types or functions from a grandparent IB. It should only know about its direct dependencies.
- [ ] **No circular dependencies** — the dependency graph is acyclic. If a cycle is detected, extract the shared concern into a foundation IB.
- [ ] **Fan-out within limits** — no IB depends on more than 3 others. If exceeded, investigate: is the IB orchestrating too much?
- [ ] **Stability of high-fan-in IBs** — IBs with 3+ dependents contain only interface definitions and simple logic, not complex implementation.

Classify each failure as auto-fixable, requires re-decomposition, or requires engineer decision (see Phase 4, step 16). Iterate up to 2 rounds per IB. Do NOT save an IB that fails the fidelity audit.

## IB Numbering

Number IBs sequentially to encode dependency order — the number is not cosmetic, it is the implementation sequence:

- Filename: `dekspec/impl-briefs/IB-NNN-[component]-brief.md` (NNN = 001, 002, 003…)
- Before assigning numbers, map the full dependency graph: which IBs produce outputs that others require?
- IBs with no dependencies come first. IBs that depend on earlier IBs get higher numbers.
- If two IBs are independent (no dependency either direction), order them by risk — higher-risk or more foundational work gets the lower number.
- The number sequence is the recommended `/write-beads` and implementation order. An engineer should be able to work top-to-bottom without encountering a missing dependency.

## Save

Save each IB to `dekspec/impl-briefs/IB-NNN-[component]-brief.md`

## Serve for Review

After saving IBs (in decomposition mode) or after modifying IBs (in resync or revise mode), check if present is available:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:7979/health
```

If the server responds with `200`, register each saved/modified IB:

```bash
curl -s -X POST http://localhost:7979/open \
  -H "Content-Type: application/json" \
  -d '{"path": "<absolute-path-to-IB>"}'
```

Report the URLs to the engineer:

```
IBs served for review in present:
  - IB-001-component: http://217.77.3.83:7979/doc/<slug>
  - IB-002-component: http://217.77.3.83:7979/doc/<slug>
  
Index: http://217.77.3.83:7979
```

If present is not running, skip silently — do not start it or report an error. The engineer can serve files manually with `/present` if they want.

## Changing a Spec After IBs Exist

When a spec changes after IBs have been written, use the `--resync` flag to update affected IBs. The cascade depends on how far downstream work has progressed:

| State | Action |
|---|---|
| IBs in `queued/` only (no beads) | `/write-ibs --resync <affected IBs>` → re-accept → `/write-beads` |
| Beads exist but no code has run | Resync IBs → delete open beads (`br delete <ids>`) → `br sync` → re-accept → `/write-beads` in numbered order |
| Beads `in_progress` or `closed` | STOP — coding has started. Make an explicit decision: continue with current IBs, revert, or file correction beads. Do not resync silently. |

If the spec change is fundamental enough that resyncing individual IBs is insufficient, delete all IBs and re-run the full decomposition: `/write-ibs <spec-path>`.

## Spec Status Update

After all IBs are saved, prompt the engineer:
"IBs have been generated. The Working Spec should remain at `ACCEPTED` status. Any future spec changes must cascade to all affected IBs and beads."

Do not update the spec status yourself — this is an engineer action.

## Engineer Review Gate

After all IBs are saved, present the engineer with a summary of audit results and what needs human review:

```
IBs ready for engineer review:

IB-NNN-component-brief.md
  Conflict Detection: ✅ passed
  Fidelity Audit: ✅ passed ([N] content, [N] cohesion, [N] coupling checks)
  Cross-IB Validation: ✅ passed
  Engineer judgment needed:
    - [ ] Domain constraints are correct for this component (machine can verify format, not domain truth)
    - [ ] Done When criteria capture the right behaviors (not just any testable behaviors)
    - [ ] Out of Scope boundaries match your intent
    - [ ] Golden I/O values are numerically correct
    - [ ] IB number reflects the right implementation order for your team
```

The automated audit verified structural correctness (completeness, consistency, cohesion, coupling). The engineer's review focuses on **domain truth** — things only a human with domain knowledge can validate.

Instruct the engineer:

"To accept: run `/write-ibs --accept <IB path or glob>` to re-run the full audit and mark accepted if all checks pass. `--approve` is retained as an alias.

Run `/write-beads` on one IB at a time, in numbered order, after each is accepted."

Do NOT suggest running /write-beads until at least the first IB is accepted. Subsequent IBs can be reviewed and beaded independently.

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/impl-briefs/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Implementation Brief depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `IB-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional IB <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/IB-provisional-<title-slug>.md` (the CLI prints the path).
4. **Populate the skeleton with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here (Motivation, Linked AEs, Components affected, Verification, etc.). The PROVISIONAL banner at the top stays.
5. **Reject `--lock`** in combination with `--provisional`. LOCKED state requires linkage-walker visibility that provisional artifacts deliberately lack. The hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion) is the canonical path to LOCKED.
6. **`--analyze` and `--review`** remain available in provisional mode — they operate on the provisional file's content without requiring canonical-graph visibility.
7. Closing step: surface to the engineer the path of the provisional file, the branch (if created), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

### Cross-references

- `INT-079` — provisional folder substrate (parser-ignore, doctor advisory).
- `INT-082` — copy-on-write spec staging (`replaces:` frontmatter, sibling-collision audit).
- `INT-083` — atomic promotion (CLI verb retired 2026-05-25; the hand-promote workflow is canonical — see `_lib/cli_verbs.md`).
- `INT-084` — `dekspec library new-provisional` scaffold + auto-branch.

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

Before any edit to a canonical artifact (anything under `dekspec/<kind-dir>/`), consult the CoW guard:

```bash
dekspec library cow-stage <path-to-canonical> [--incubation <slug>] [--at <repo>]
```

If the target path is claimed by a pre-ACCEPTED Intent (DRAFT/PROPOSED) via that Intent's `Components affected` globs, the verb:

1. Copies the canonical to `dekspec/provisional/<incubation-slug>/<KIND>-provisional-<file-slug>.md`.
2. Stamps `replaces: <CANONICAL-ID>` in the frontmatter so the eventual `promote-provisional` run does a REPLACE (preserving the canonical ID) instead of allocating a new one.
3. Returns the new provisional path. Edit that file instead; the canonical stays frozen.

If the path is not claimed by any pre-ACCEPTED Intent, the verb errors unless you pass an explicit `--incubation <slug>` (the canonical-only path is the normal edit flow).

**Skill discipline.** Inside this skill body, before any canonical-file `Edit`/`Write` call:

1. Compute the target path you intend to write.
2. Run `dekspec library cow-stage <target-path>` once. Surface the verb's stdout to the engineer.
3. If the verb exits 0 with a new provisional path printed, redirect the edit to that path.
4. If the verb exits 1 (no claim + no `--incubation`), proceed with the canonical edit as normal — the canonical is unclaimed and the edit is direct-flow legal.

**Audit pairing.** The `T-COW-CANONICAL-EDITED` rule (P2 mechanical) fires on every `git diff --name-only main` entry that is claimed AND lacks a provisional sibling with `replaces:` set — so a skill that skips this guard surfaces as advisory in the next `dekspec audit linkage` run, but never blocks.


## Output

One or more IB files in `dekspec/impl-briefs/`, each with **Status** set to `PROPOSED` and pending engineer acceptance via `/write-ibs --accept <path or glob>`.

## Common Pitfalls

- Don't `/write-ibs` against a WS still at DRAFT/PROPOSED, or one carrying unresolved P1 `blocking_pre_ib` open_issues — the L12 precondition refuses it; settle the WS blockers (or unlock the WS) first, there is no bypass flag.
- Don't summarize or paraphrase spec/ADR/IC content into an IB — copy the scoped sections verbatim and reconcile every ADR/IC decision into a concrete `Constraints & Decisions` entry; the coding agent reads only the IB, never the sources.
- Don't leave an ADR or IC listed in the Governing ADRs / Interface Contracts section with no matching C&D entry — a listed-but-not-inlined source is a fidelity-audit failure, not traceability.
- Don't cut IBs along domain affinity or release timing ("all the graph changes," "everything needed for the release") — that is logical/temporal cohesion; cut along functional units with one primary failure domain each.
- Don't keep iterating per-IB content fixes past 2 rounds or decomposition past 3 — persistent failures mean the boundary or the spec is wrong; escalate to the engineer as a re-decomposition issue instead of forcing a save.
- Don't restructure only the failing IB after a re-decomposition — restart Phase 4 for the entire affected dependency set, since numbers, order, and file assignments shift.
- Don't `--lock` an IB whose parent WS is below ACCEPTED or whose cohort siblings aren't all ≥ ACCEPTED — the mechanical Lock gate refuses it; lock the cohort in implementation order as gates settle.
- Don't invent Golden I/O values for numerical IBs — the engineer or a reference implementation supplies them; STOP and ask if they're missing.

## Verification Checklist

- [ ] L12 precondition was run via `dekspec check validate <spec-path> --json` and the WS carries zero unresolved P1 open_issues (or status was DRAFT/PROPOSED and the gate was correctly skipped).
- [ ] Every governing ADR (supersession-resolved) and every referenced IC has at least one concrete `Constraints & Decisions` entry in each IB that consumes it — no listed-but-not-inlined source.
- [ ] Each saved IB passed Conflict Detection and the full Fidelity Audit (content + cohesion + coupling) with no severity-important-or-worse finding, and the cross-IB Phase 5 coupling pass ran once over the full set.
- [ ] The dependency graph is a DAG, no IB depends on more than 3 others, and IB numbers encode the confirmed implementation order.
- [ ] No IB that failed the fidelity audit was saved; failing IBs were escalated to the engineer, not silently shipped.
- [ ] Every saved/revised IB is at `Status: PROPOSED` (decomposition/resync/revise) or the correct promoted status (`--accept` → ACCEPTED, `--lock` → LOCKED) with an Amendment-Log row appended.
- [ ] `dekspec audit relink` was run against the repo root after the artifact writes (the mandatory Closing Step).
- [ ] The Engineer Review Gate summary was presented and the engineer was instructed to `--accept` before any `/write-beads`.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an Implementation Brief — Creation, `--accept`, `--lock`, `--resync`, `--revise`, `--review`). After the artifact file(s) are saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.

## Two-Tier Review Pipeline State-Machine (MSN-017)

> Added by **INT-122** + **INT-124** (LOCKED 2026-05-30). MSN-017 layered the IB lifecycle with five new states (REVIEW_IB, REVIEW_IB_FAIL, REVIEW_PR, REVIEW_PR_FAIL, TESTFAIL) per ADR-026. The transitions below name the `/write-ibs` mode that owns each step + the auto-fire / dispatch contract.

### Transition matrix

| From state | Mode / trigger | To state | Auto-fire / dispatch |
|---|---|---|---|
| PROPOSED | `--accept` | ACCEPTED | (engineer approval) |
| ACCEPTED | (state-entry hook) | **REVIEW_IB** | auto-invoke `/dekspec:review-ib <IB-ID>` (INT-106 LOCKED) |
| REVIEW_IB | verdict GO | IMPLEMENTING | (operator advances per RECOMMEND mode; AUTO per INT-118) |
| REVIEW_IB | verdict NO-GO | **REVIEW_IB_FAIL** | `dekspec.action_handlers.dispatch("REVIEW_IB_FAIL", context)` → INT-113 handler module (`/write-ibs --revise` + re-fire REVIEW_IB) |
| REVIEW_IB | verdict INSUFFICIENT_EVIDENCE | (hold) | operator decides; sidecar logs the abstention |
| IMPLEMENTING | green CI | TESTPASS | per **INT-123** (coding-session wiring) |
| IMPLEMENTING | red CI | **TESTFAIL** | `dekspec.action_handlers.dispatch("TESTFAIL", context)` → INT-114 handler (`/exec-coding-session --retry` + re-eval) |
| TESTFAIL | retry green | TESTPASS | handler advances on AUTO mode; operator approves on RECOMMEND |
| TESTFAIL | retry red | IMPLEMENTING (loop) | new failure recorded in TESTFAIL log; sidecar updated |
| TESTPASS | PR-open on IB-aggregate branch | **REVIEW_PR** | auto-invoke `/dekspec:review-pr <PR-#>` (INT-107 LOCKED); trigger seam = `tooling/dekspec/hooks/pr_open.py` OR `dekspec review trigger <PR-#>` per INT-124 |
| REVIEW_PR | verdict GO | MERGED-ready | operator merges per RECOMMEND mode; AUTO auto-merges |
| REVIEW_PR | verdict NO-GO | **REVIEW_PR_FAIL** | `dekspec.action_handlers.dispatch("REVIEW_PR_FAIL", context)` → INT-115 handler (`/write-ibs --revise` + new commits on top + re-fire REVIEW_PR) |
| REVIEW_PR | verdict INSUFFICIENT_EVIDENCE | (hold) | operator decides |

### Action-handler dispatch (INT-121 registry)

Each FAIL state's handler is registered against the `dekspec.action_handlers` Python registry (INT-121 LOCKED) at module import time. The `/write-ibs` lifecycle reaches `dispatch(fail_state, context)` on every transition into a FAIL state. The dispatch contract:

- `register(fail_state, handler_path_or_module)` — idempotent; `ConflictingHandlerError` on different-handler re-register.
- `dispatch(fail_state, context)` → `HandlerResult(transition, staged_artifacts, summary)`. `UnregisteredFailStateError` if no handler for the state.
- `HandlerContext` carries: `ib_id`, `ib_path`, `sidecar_review_path`, `audit_doctor_snapshot_sha`, `mode` (RECOMMEND/MIXED/AUTO), `coding_session_ref`, `ib_branch`.
- The state machine commits the FAIL transition BEFORE calling dispatch — a handler crash leaves the FAIL state standing for operator intervention.

### Mode-aware advancement (INT-118 config)

The active mode is resolved per `dekspec.review.config.resolve_mode(.dekspec/config.yaml, .dekspec/review-thresholds.yaml)`:

- **RECOMMEND** (default) — handlers stage actions + signal operator; no auto-advance. `transition='hold'`.
- **MIXED** — auto-advance on lenses with operator-committed silver thresholds; escalate otherwise.
- **AUTO** — auto-advance on lenses ≥ gold threshold. Reverts to RECOMMEND when thresholds YAML is absent.
