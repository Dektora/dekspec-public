---
name: write-adr
description: Write an Architectural Decision Record. Use when an undocumented architectural decision exists, the expertise audit flags one, or the Options Architect surfaces an architectural choice.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --accept | --approve | --lock | --unlock | --revise | --supersede | --amend] [description or path to ADR]
related_skills: [write-ae, write-sv, write-ws, write-ic, write-intent]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Write, lock, or unlock an Architectural Decision Record.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill requires precise architectural reasoning. Prior conversation context can degrade quality by introducing bias and competing patterns.
>
> First message → proceed. Prior history → ask "context may affect ADR quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-adr the constraint compiler should parse each IR kind with a dedicated parser rather than one monolithic dispatch parser

Capture the decision to use per-kind parsers over a single dispatch parser.
Drivers: isolation of schema-evolution blast radius, parallel authoring, clearer
audit attribution. Note the maintenance cost of N parsers as the negative consequence.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode**.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Lock mode** — `--lock` flag. Skip to **Lock Mode**.
- **Unlock mode** — `--unlock` flag. Skip to **Unlock Mode**.
- **Accept mode** — `--accept` flag. Skip to **Accept Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Revise mode** — `--revise` flag. Skip to **Revise Mode**.
- **Supersede mode** — `--supersede` flag. Skip to **Supersede Mode**.
- **Amend mode** — `--amend` flag. Skip to **Amend Mode** (editorial-at-LOCKED; no unlock cycle).
- **Approve mode** — `--approve` flag. Skip to **Approve Mode**.
- **Creation mode** — no flag. Proceed to **Input**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock`, `--supersede`, `--amend`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:adr-author`
- **substantive_modes**: [Creation (no flag), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock`, `--supersede`]
- **bundle_list** (Step 1 context):
  1. Template path — `dekspec/templates/adr-template.md` (read verbatim).
  2. Engineer guidance — raw `$ARGUMENTS` (Creation); existing ADR + notes (`--revise`); existing ADR + audit findings to address (`--accept`).
  3. Related Architecture Elements — run `python ../_lib/scripts/bundle_related.py --keywords "<decision-domain-keywords>" --include ae` (for `--revise` / `--accept`, also `--for <existing-ADR-path> --include ae --backlinks`) to get candidate AE paths whose linkage sections touch the decision's domain. From the returned paths, judge which AEs are relevant; bundle those — paths AND content.
  4. Prior ADRs on the same axis (supersession surface) — run `python ../_lib/scripts/bundle_related.py --keywords "<decision-domain-keywords>" --include adr` to get candidate ADR paths whose linkage sections overlap this decision. From the returned paths, judge which the new ADR may supersede or be superseded by; bundle those (paths AND content); at minimum every ADR in that supersession relationship.
  5. Constraints — relevant Interface Contracts (`dekspec/interface-contracts/`), the System Vision (`dekspec/system-vision.md`), the domain glossary (`dekspec/domain-glossary.md`), and any cross-cutting governance the decision must respect.
  6. ADR index state — `dekspec/adr-index.md` for the next ADR-NNN.
- **expected_output_path**: Creation — `dekspec/adrs/ADR-NNN-<slug>.md` (orchestrator pre-computes NNN); `--revise` / `--accept` — the existing ADR path.
- **validation**: `dekspec check validate <output-path>` + the Audit Mode checklist (§Audit Mode below). Orchestrator also updates `dekspec/adr-index.md` for Creation (new row) and `--accept` (status change) — the subagent's job is the ADR file, not the index. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-adr"
one_line:   "Create, audit, review, revise, accept, supersede, lock, or unlock ADRs"
modes:
  - { flag: "", args: "<description>", description: "Create a new ADR from the engineer's description." }
  - { flag: "--audit", args: "<ADR-path>", description: "Read-only quality check: template completeness, validation criteria, supersession accuracy. Also checks if this ADR should be superseded." }
  - { flag: "--review", args: "<ADR-path>", description: "Walk through open issues interactively. Present each issue with context and a recommendation. Engineer resolves, defers, or dismisses each." }
  - { flag: "--revise", args: "<ADR-path> <notes>", description: "Incorporate engineer review notes into the ADR. Notes can be inline text or a path to a notes file." }
  - { flag: "--accept", args: "<ADR-path>", description: "Promote a PROPOSED ADR to ACCEPTED (PROPOSED → ACCEPTED). Runs final audit including the supersession check; refuses if any check fails. Passing the flag counts as deliberate engineer approval — no additional confirmation is asked." }
  - { flag: "--supersede", args: "<ADR-path>", description: "Create a new ADR that supersedes the given one. Pre-fills context from the old ADR and updates both supersession fields automatically." }
  - { flag: "--lock", args: "<ADR-path>", description: "Lock an ACCEPTED ADR (ACCEPTED → LOCKED). Runs pre-lock audit. Rejects if any check fails." }
  - { flag: "--unlock", args: "<ADR-path>", description: "Unlock a LOCKED ADR (LOCKED → PROPOSED). Runs downstream impact assessment. Requires a reason." }
  - { flag: "--amend", args: "<ADR-path>", description: "Editorial-at-LOCKED: record a surface-only correction (Decision prose / Links / Related Architecture Elements) with an Amendment Log row, NO unlock cycle, Status untouched. Refuses on diffs to Status / supersession / Context / Options Considered / Consequences / Validation (those need --unlock + --lock). Mirrors /write-intent --amend --editorial. ds-qxpq." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing an ADR section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows ADRs)." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-adr inject embeddings into hidden state space rather than concatenating"
  - "/write-adr --audit dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --review dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --revise ADR-001-inject-embeddings.md \"validation criteria too vague\""
  - "/write-adr --accept dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --supersede dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --lock dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --unlock dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --amend dekspec/adrs/ADR-001-inject-embeddings.md"
  - "/write-adr --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: ADR (Architectural Decision Record)
- **template_path**: `templates/adr-template.md`
- **methodology_section**: §4 Layer 1 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/adrs/ADR-005-severity-graded-findings-and-audit-profiles.md`, `dekspec/adrs/ADR-011-new-ir-kind-vs-subtype.md`
- **required_sections**: [Status, Context and Decision Drivers, Decision, Options Considered, Consequences, Validation, Links, Open Issues, Amendment Log]

Skill-specific structural checks to surface as Open Issues: missing Validation, Decision without Options Considered, broken AE backlink.

## Audit Mode

Read-only quality check on an existing ADR. **Always checks for supersession.**

1. Read the ADR at the provided path
2. Check:
   - [ ] All template sections are populated — no placeholders, no TODOs in the body
   - [ ] Title is verb-first and specific
   - [ ] Decision drivers are explicit
   - [ ] Rationale is specific to this system, not generic
   - [ ] Context is past tense
   - [ ] Consequences are stated (positive and negative)
   - [ ] Validation criteria are concrete and observable
   - [ ] Supersession fields are accurate (check both directions)
   - [ ] No downstream specs contradict this ADR (grep specs for ADR reference, spot-check)
   - [ ] Created and Modified dates are set
3. **Supersession check** — always run regardless of other results:
   - Read all other ADRs in `dekspec/adrs/` that share overlapping domain (grep for shared keywords in title/decision)
   - Check if any newer ADR partially or fully contradicts this one
   - Check if this ADR's decision has been effectively overridden by code changes (grep for the decision's key pattern in the codebase)
   - If potential supersession found, flag:
     ```
     ⚠️  POSSIBLE SUPERSESSION: [ADR-NNN] may partially/fully supersede this ADR.
     Evidence: [what contradicts or overlaps]
     Recommend: /write-adr --supersede <this-ADR-path>
     ```
4. Report:

```
AUDIT: [path]
Status: [current status]

Passed: [N/total]
Failed:
  - [description of each failure]

Supersession: [clean / possible supersession found — see above]
```

Read-only — no changes made.

**End of Audit Mode.**

## Review Mode

Walk through open issues interactively — present each issue with context and a recommendation, resolve with the engineer one at a time.

Arguments: the ADR path.

### Steps

1. Read the ADR at the provided path
2. Parse the `## Open Issues` section. Collect all unchecked items (`- [ ]`).
3. If no unchecked items exist: "No open issues in [path]. Nothing to review." **End of Review Mode.**
4. Read the artifact's Decision, Context and Decision Drivers, and Consequences sections for context.
5. Read all governing ADRs and related artifacts referenced in Links to check for cross-artifact relevance.
6. Present a summary:
   ```
   REVIEW SESSION: [path]
   Status: [current status]
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
   b. Analyze the issue against the current artifact content:
      - Has this issue already been addressed by changes to the artifact since it was logged?
      - Is the issue still valid given the current state of governing ADRs and related artifacts?
      - What would resolving this issue require — a text change to this artifact, a structural change, or an upstream change to another artifact?
   c. Present a recommendation:
      ```
      RECOMMENDATION: [resolve / revise artifact / defer / dismiss]
      
      [Specific explanation — what to change and why, or why to defer/dismiss]
      
      [If resolve or revise: show the proposed text change]
      ```
   d. Wait for the engineer's response.
   e. Based on response:
      - **Resolve** — check off the issue, append resolution: `- [x] [Issue] — **Source:** ... — **Severity:** ... — **Resolved:** [today] [resolution summary]`
      - **Revise** — apply the agreed change to the artifact body, then check off the issue with resolution note
      - **Defer** — leave unchecked, optionally update the issue description with new context
      - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`
8. Update **Modified** date.
9. Present summary:
   ```
   REVIEW COMPLETE: [path]
   
   Resolved: [N]
   Dismissed: [N]
   Deferred: [N]
   
   [If blocking issues remain]: ⚠️  [N] blocking issues remain — artifact should not advance status.
   [If no blocking issues remain]: ✅ No blocking issues remain — artifact is clear for status advancement.
   ```

**End of Review Mode.**

## Revise Mode

Incorporate engineer review notes into an ADR. Note: ACCEPTED ADRs are normally immutable — revise only PROPOSED or DRAFT ADRs. If the ADR is ACCEPTED or LOCKED, warn the engineer and suggest `--supersede` instead.

Arguments after the path are the engineer's notes — inline text or a path to a `.md`/`.txt` file.

**This is a substantive-work mode** — the actual revision is performed by a fresh-context subagent per §Fan-Out Mode. The parent only orchestrates: status guard, context bundling, dispatch, post-validation. The parent does NOT edit the ADR body itself.

### Pre-flight (parent, inline)

1. Read the ADR.
2. Check status — if ACCEPTED or LOCKED, warn: "This ADR is [status]. ADRs are immutable once accepted. Use `--supersede` to create a replacement, or `--unlock` first if you need to make corrections. Continue anyway? (y/n)" Wait for the engineer's response. Stop if the engineer declines.
3. Read the engineer's notes (inline or from file).

### Fan-out (parent → dekspec:adr-author subagent)

Bundle context per §Fan-Out Mode Step 1 — include the **existing ADR contents** and the **engineer's notes** in the `Engineer guidance` block of the prompt, marking the mode as `Revise`. Related AEs, prior ADRs, and constraints are bundled as for Creation Mode.

Dispatch per §Fan-Out Mode Step 2 with `subagent_type: dekspec:adr-author`. The subagent classifies each note, applies the approved changes to the artifact body, updates the **Modified** date, and returns the revised ADR plus a list of any new open issues it logged.

### Post-flight (parent, inline)

Validate per §Fan-Out Mode Step 3.

If the subagent reports new open issues (ambiguity / contradictions surfaced during revision that could not be fully resolved), surface them to the engineer:

```
NEW OPEN ISSUES logged on [path]:
  - [issue 1]
  - [issue 2]
Run `/write-adr --review [path]` to walk through them.
```

Re-run the verification checks from Step 4 of the Creation Workflow against the revised artifact.

**End of Revise Mode.**

## Accept Mode (PROPOSED → ACCEPTED)

Promotes a PROPOSED ADR to ACCEPTED after every quality check passes. Passing the `--accept` flag is itself the deliberate engineer action of approval — no additional confirmation prompt is raised. The skill refuses to accept if any check fails; no partial acceptance exists.

**This is a substantive-work mode** — the final audit + any required cleanup is performed by a fresh-context subagent per §Fan-Out Mode. The parent orchestrates the status guard, dispatches the subagent, then applies the status change + index update on a clean return.

### Step 1: Validate (parent, inline)

1. Read the ADR at the provided path.
2. Verify current status is PROPOSED — run `python ../_lib/scripts/artifact_ops.py status-guard <ADR-path> --expect PROPOSED`. If it exits non-zero, surface stderr and STOP. Interpret the actual status for the engineer:
   - TODO, DRAFT → "This ADR is still [status]. It must be revised to PROPOSED before it can be accepted."
   - ACCEPTED → "This ADR is already ACCEPTED."
   - LOCKED → "This ADR is LOCKED. Unlock first with `--unlock` if changes are needed, or use `--supersede` to replace it with a new ADR."

### Step 2: Fan-out final audit (parent → dekspec:adr-author subagent)

Bundle context per §Fan-Out Mode Step 1 — include the **existing ADR contents** and the **full Audit Mode checklist below** in the `Engineer guidance` block of the prompt, marking the mode as `Accept`. Related AEs, prior ADRs (the supersession surface), and constraints are bundled as for Creation Mode.

The subagent runs the complete checklist against the artifact, including the always-run supersession check:

- [ ] All template sections are populated — no placeholders, no TODOs in the body
- [ ] Title is verb-first and specific
- [ ] Decision drivers are explicit
- [ ] Rationale is specific to this system, not generic
- [ ] Context is past tense
- [ ] Consequences are stated (positive and negative)
- [ ] Validation criteria are concrete and observable
- [ ] Supersession fields are accurate (check both directions)
- [ ] No downstream specs contradict this ADR (grep specs for ADR reference, spot-check)
- [ ] Created and Modified dates are set
- [ ] Supersession check — no newer ADR partially or fully contradicts this one; decision not effectively overridden by code
- [ ] No blocking open issues remain

Dispatch per §Fan-Out Mode Step 2 with `subagent_type: dekspec:adr-author`. The subagent returns its pass/fail report against the checklist plus supersession evidence.

### Step 3: Report (parent, inline)

```
FINAL AUDIT: [path]
Subagent: dekspec:adr-author

Passed: [N/total]
Failed:
  - [description of each failure]

Supersession: [clean / possible supersession found]

[If all passed and supersession clean]: All checks pass. Promoting PROPOSED → ACCEPTED.
[If any failed or supersession flagged]: Cannot accept — resolve failures first. No changes made.
```

If any check fails or the supersession check flags a conflict, STOP — do not change status, do not update the index, do not make any other changes.

### Step 4: Accept (parent, inline)

Only executed if Step 3 reported zero failures and clean supersession. This is a mechanical status walk performed by the parent — no fresh context is needed.

1. Flip Status PROPOSED → ACCEPTED and bump Modified — run `python ../_lib/scripts/artifact_ops.py transition <ADR-path> --from PROPOSED --to ACCEPTED` (no `--note`: no Amendment Log entry on accept). Surface stderr on non-zero exit and STOP.
2. Update `dekspec/adr-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/adr-index.md --id ADR-NNN --status ACCEPTED` (surface stderr on non-zero exit).

No Amendment Log entry is written — the log is reserved for changes made after LOCKED status, when unlocking back to PROPOSED, or when the ADR is superseded.

**End of Accept Mode.**

## Supersede Mode

Create a new ADR that supersedes an existing one. Use when an architectural decision needs to change — the old ADR remains as history, the new one carries the current decision.

1. Read the existing ADR at the provided path
2. Ask the engineer: "What has changed? Why does this decision need to be superseded?"
3. Wait for the engineer's response.
4. Create a new ADR using the creation workflow (Step 1 through Step 5), with these pre-filled values:
   - **Context** — pre-fill with the old ADR's context plus the engineer's reason for supersession
   - **Supersedes** — set to the old ADR's number
   - **Links** — include the old ADR
5. After the new ADR is saved, update the old ADR:
   - Set `Superseded by` to the new ADR's number
   - Add an Amendment Log entry: `| [today] | Superseded | Superseded by ADR-NNN | engineer |`
   - Update `dekspec/adr-index.md` for both ADRs
6. Run a downstream impact check — grep for the old ADR's number across specs, contracts, IBs, and architecture elements. Report which artifacts reference the superseded ADR and may need updating.

**End of Supersede Mode.**

## Lock Mode (ACCEPTED → LOCKED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Lock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: ADR
- **pre_lock_audit_ref**: §Audit Mode of this skill, extended with the ADR-specific checks below
- **status_before**: ACCEPTED
- **status_after**: LOCKED
- **artifact_index_path**: `dekspec/adr-index.md`

ADR-specific pre-lock audit extensions (added on top of the substrate's audit run):
- Validation criteria are concrete and observable
- Supersession fields are accurate in both directions
- No downstream specs contradict this ADR (grep specs for the ADR reference, spot-check)

## Unlock Mode (LOCKED → PROPOSED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: ADR
- **status_before**: LOCKED
- **status_after**: PROPOSED
- **artifact_index_path**: `dekspec/adr-index.md`

Downstream impact scan (run during Step 2 alongside the reason gate): grep all specs, interface contracts, and architecture elements for references to this ADR number; surface the impact list to the engineer before recording the reason. Cascade reminder to surface in Step 4: downstream specs / interface contracts / architecture elements may need review, affected IBs may need regeneration, and the ADR must be re-locked when the substantive change settles.

## Amend Mode (editorial-at-LOCKED, ds-qxpq)

`--amend` records a **surface-only, cross-reference / discoverability** correction to an ADR — at any status, including `LOCKED` — **without** the `--unlock` → edit → `--lock` cycle and **without** flipping Status. It mirrors `/dekspec:write-intent --amend --editorial` (the working precedent). This is an **inline mode** (parent context) — the change is bounded and editorial, so no fan-out.

**Use it for:** cross-reference housekeeping (a referenced concept gets renamed), adding a mantra/principle opening sentence to the `Decision` for discoverability, and forward-cross-link additions (a new downstream ADR/AE the LOCKED ADR should point at). The decision body's semantics must not change.

**Editable surface (only):** the `## Decision` section prose, the `## Links` section, and the Related/Linked Architecture Elements section. **Refused surface:** `Status`, the supersession fields (`*Supersedes:*` / `*Superseded by:*`), `Context`, `Options Considered`, `Consequences`, `Validation` — a change to any of those alters the *decision* and must go through `--unlock` + `--lock`.

### Steps

1. **Validate.** Read the ADR. Confirm it exists. (Any status is amendable editorially — the guard below is what bounds the change, not the status.)
2. **Apply the editorial edit in place** with the `Edit` tool — touching ONLY the Decision prose / Links / Related Architecture Elements. Never edit the refused sections here.
3. **Classify + record** by invoking the shared kind-aware helper, which diffs the on-disk ADR against its git-HEAD baseline, REFUSES (non-zero, writes nothing) if the diff touches any refused section, and otherwise appends an `editorial` Amendment Log row + bumps `Modified` (Status untouched):

   ```bash
   python ../_lib/scripts/artifact_ops.py editorial-amend <ADR-path> \
     --note "<one-line summary of the editorial change>" [--engineer <email>] [--baseline <path>]
   ```

   On a non-zero exit, surface the helper's refusal verbatim (it names the offending decision field) and STOP — the engineer routes the change through `--unlock` + `--lock` instead. Do **not** hand-edit the Amendment Log to bypass the guard.
4. **Closing step.** Run `dekspec audit relink` (the shared closing step) so any newly-added forward cross-links re-derive their backlinks.

**End of Amend Mode.**

## Input

Engineer's description of the decision: $ARGUMENTS

## Workflow

**This is the default drafting path — a substantive-work mode.** Per §Fan-Out Mode, the actual drafting is performed by a fresh-context `dekspec:adr-author` subagent. The parent orchestrates: context gathering, escalation check, dispatch, post-validation, and index update. The parent does NOT draft ADR prose itself.

### Step 1: Context Gathering (parent, inline)

The parent assembles the bundle the subagent will receive. Per §Fan-Out Mode Step 1, read and stage:

1. The Writer role from `dekspec/project-context.md` (engineer-facing tone guidance for the subagent).
2. `dekspec/domain-glossary.md` for canonical domain terminology (jargon-drift guard for the subagent).
3. The ADR template from `dekspec/templates/adr-template.md` (verbatim).
4. Compute the next ADR-NNN id deterministically — run `python ../_lib/scripts/artifact_ops.py next-id adr` (surface stderr on non-zero exit). Then read `dekspec/adr-index.md` to surface existing ADRs on this topic.
5. Related Architecture Elements (grep `dekspec/architecture-elements/` for keyword overlap with the engineer's description).
6. Prior ADRs on the same axis (the supersession surface — grep `dekspec/adrs/` for keyword overlap).
7. The System Vision, relevant Interface Contracts, and any cross-cutting governance constraints.

### Step 2: Escalation Check (parent, inline)

Check if the decision falls on the "always a full ADR" list:
- Injection strategy
- Tensor serialization format
- Shadow graph consistency semantics
- GPU device assignment
- Quantization thresholds
- Wave compression contract
- Formula DSL namespace

If yes, the dispatched subagent MUST produce a full ADR — no lightweight alternative. Flag this in the `Engineer guidance` block of the prompt.

### Step 3: Fan-out Draft (parent → dekspec:adr-author subagent)

Dispatch per §Fan-Out Mode Step 2 with `subagent_type: dekspec:adr-author`. Mark the mode as `Creation` in the prompt. The subagent runs in a fresh context and is responsible for the complete draft, filling in all template sections per the template's structure:

- **Status:** PROPOSED on save (the subagent moves DRAFT → PROPOSED at write time)
- **Created:** today's date
- **Modified:** today's date
- **Supersession:** both `Supersedes` and `Superseded by` — use ADR-NNN references or "none". New ADRs typically have both as "none". Only when deliberately replacing an existing ADR should `Supersedes` be filled; the cross-update of the superseded ADR's `Superseded by` field is handled per the subagent's authoring flow.
- **Deciders:** the subagent asks the engineer via the orchestrator if not obvious — surface as an explicit "subagent needs deciders" return.
- **Context and Decision Drivers:** past tense, explicit driver list, technical story link if applicable
- **Decision:** what was decided and why this option over the alternatives in this system's specific context
- **Options Considered:** include only if genuine alternatives were evaluated; omit for straightforward architectural decisions
- **Consequences:** positive and negative — both required
- **Validation:** observable criteria, metrics, or conditions that would trigger reconsideration
- **Links:** related ADRs, specs, or external references
- **Amendment Log:** empty on initial creation

The subagent writes the file to the expected output path (`dekspec/adrs/ADR-NNN-<slug>.md`) and returns the final content + validation result.

### Step 4: Verification (parent, inline — post-fan-out)

When the subagent returns, the parent independently verifies per §Fan-Out Mode Step 3:

- Title is verb-first and specific — the title alone tells you what was decided
- Decision drivers are explicit, not buried in prose
- Rationale is specific to this system, not generic praise of a technology
- Context is past tense
- Consequences are stated (positive and negative)
- Validation criteria are observable and concrete
- Content is at architectural level — no function signatures, line numbers, config key names, or variable names
- All template sections are filled

If verification fails, surface per §Fan-Out Mode "SUBAGENT COULD NOT PRODUCE CLEAN ARTIFACT" — do not patch the artifact in the parent context.

### Step 5: Index Update + Handoff (parent, inline)

Only executed if Step 4 verification passes.

1. Confirm **Status** is PROPOSED on the returned artifact — run `python ../_lib/scripts/artifact_ops.py status-guard dekspec/adrs/ADR-NNN-[slug].md --expect PROPOSED` (surface stderr on non-zero exit).
2. Confirm **Modified** is today's date.
3. Confirm the file is at `dekspec/adrs/ADR-NNN-[slug].md`.
4. Update `dekspec/adr-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/adr-index.md --id ADR-NNN --status PROPOSED` (surface stderr on non-zero exit). **The parent does this — not the subagent.**
5. Engineer promotes status to ACCEPTED when approved — either by editing the file directly, or by running `/write-adr --accept <path>` which enforces a final audit plus supersession check before promoting.

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/adrs/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Architecture Decision Record depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `ADR-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional ADR <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/ADR-provisional-<title-slug>.md` (the CLI prints the path).
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


## Rules

- **Log corrections.** When any mode (creation, audit, review, revise) corrects a domain misinterpretation — wrong term usage, confused concepts, contradicted architectural facts — invoke `/write-ggc --log` with the correction details before proceeding. This feeds the glossary promotion pipeline.
- One decision per ADR
- Immutable once accepted — never edit, write a new one that supersedes
- Options Considered section is optional — include only when genuine alternatives were evaluated
- All architectural decisions get an ADR. One mechanism, one artifact.
- The template (`dekspec/templates/adr-template.md`) must be completely filled out. Every section, every placeholder. If information is missing, ask the engineer before proceeding — do not guess or leave blanks.
- **Write at the architectural level, not the code level.** ADRs capture concepts, intent, constraints, and high-level patterns. Use code only to extract meaning and verify the architectural narrative. Do not include function signatures, line numbers, config key names, variable names, or code-level edge cases — those belong in the code itself, not in ADRs, Working Specs, or Implementation Briefs. An ADR should be understandable by someone who has never read the codebase.

## Output

- `dekspec/adrs/ADR-NNN-[slug].md` with status PROPOSED
- Updated `dekspec/adr-index.md`

## Approve Mode

`--approve` records a peer-review approval signature on an ADR under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the ADR's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <ADR-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED` or `LOCKED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the ADR may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Common Pitfalls

- Don't edit an ACCEPTED or LOCKED ADR in place to change the decision — write a new ADR via `--supersede` and let the old one stand as history; in-place mutation breaks the supersession audit and the decision audit trail.
- Don't draft ADR prose in the parent context — Creation, `--accept`, and `--revise` are substantive-work modes that MUST fan out to the `dekspec:adr-author` subagent; parent-authored prose carries the orchestration context's bias the §Context Check exists to exclude.
- Don't drop code-level detail into the body — no function signatures, line numbers, config key names, or variable names; an ADR captures the architectural decision and must read cleanly to someone who has never opened the codebase.
- Don't skip the supersession check on `--audit` / `--accept` — it runs regardless of every other result; a "clean" audit that never grepped the overlapping-domain ADRs is a false pass.
- Don't claim a canonical ADR-NNN id for long-lived exploration — use `--provisional <slug>` so the id is allocated only at hand-promote, and never pair `--lock` with `--provisional` (the skill rejects it).
- Don't let the parent flip Status to ACCEPTED while any check fails or supersession is flagged — there is no partial acceptance; STOP, leave the index untouched, and report the failures.

## Verification Checklist

- [ ] The correct mode ran for the flag supplied, and substantive modes (Creation / `--accept` / `--revise`) executed via the `dekspec:adr-author` subagent — not parent-authored prose.
- [ ] Every template section is populated — no placeholders, no TODOs — and Status is PROPOSED on a fresh Creation save.
- [ ] The body is at architectural level only: no function signatures, line numbers, config key names, or variable names.
- [ ] The supersession check ran (both directions) and either reported clean or surfaced the conflicting ADR with evidence.
- [ ] `dekspec check validate <output-path>` exited 0; any non-zero exit was surfaced verbatim and the run stopped.
- [ ] `dekspec/adr-index.md` was updated by the parent (new row on Creation, status change on `--accept`), not by the subagent.
- [ ] Created and Modified dates are set, with Modified bumped to today on any write/revise.
- [ ] `dekspec audit relink` was run at the repo root as the final action of every substantive mode.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an ADR — Creation, `--accept`, `--revise`, `--lock`, `--unlock`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
