---
name: write-ic
description: Write an Interface Contract for a cross-component boundary. Use when two independently-built components need a formal boundary definition, or when /write-ws identifies a boundary that warrants a contract.
mode: full
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --accept | --approve | --lock | --unlock | --revise] [description, "from WS-NNN", or path to contract] [notes]
related_skills: [write-ws, write-ae, write-adr, write-ibs]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Write, lock, or unlock an Interface Contract.

## Starter Prompt

```prompt
/dekspec:write-ic from WS-007

Cut the contract for the boundary WS-007 flags between the model server (provider) and the API server (consumer). Pin the error semantics for request timeout and malformed-payload on both sides, and state the consistency guarantee for concurrent inference requests.
```

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill requires precise boundary definition, error semantics, and consistency guarantees. Prior conversation context can degrade quality by introducing assumptions from unrelated work.
>
> First message → proceed. Prior history → ask "context may affect IC quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

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
- **Approve mode** — `--approve` flag. Skip to **Approve Mode**.
- **Creation mode** — no flag. Proceed to **Fan-Out Mode (default drafting path)**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--audit`, `--review`, `--lock`, `--unlock`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:ic-author`
- **substantive_modes**: [Creation (no flag), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`, `--review`, `--lock`, `--unlock`]
- **bundle_list** (Step 1 context, mode-specific):
  1. Template — `dekspec/templates/interface-contract-template.md` (Creation).
  2. Existing contract path + full body (Accept / Revise).
  3. Engineer guidance — `$ARGUMENTS` verbatim. For Creation, free-form description or `from WS-NNN`; if `from WS-NNN`, also bundle the referenced WS at `dekspec/working-specs/WS-NNN-<slug>.md` for parties / data / error / consistency extraction. For Revise, engineer notes (inline string OR resolved from `.md`/`.txt` path).
  4. Provider AE — the AE document for the producing-side component (`dekspec/architecture-elements/AE-NNN-<slug>.md`).
  5. Consumer AE(s) — every AE on the consuming side(s); a contract may have multiple.
  6. Governing ADRs — every relevant ADR from `dekspec/adr-index.md` and `dekspec/adrs/ADR-NNN-<slug>.md`. For each, run `python ../_lib/scripts/resolve_supersession.py <ADR-ID>` and read the resolved live ADR (the script walks the `Superseded by` chain deterministically and detects cycles / dangling refs; surface stderr on non-zero exit). Mark any PROPOSED ADRs so the subagent does not silently treat them as ACCEPTED.
  7. Sibling ICs — `dekspec/interface-contract-index.md` plus any ICs under `dekspec/interface-contracts/` sharing parties or governing ADRs (conflict-detection input).
  8. Domain glossary — `dekspec/domain-glossary.md`.
  9. Next IC-NNN number (Creation only) — computed deterministically by running `python ../_lib/scripts/artifact_ops.py next-id ic` (surface stderr on non-zero exit).
  10. Constraints — every Rule from §Rules at the bottom of this skill (every error condition has stated behavior for both parties; "silent degradation" never valid; boundary domain constraints explicit — dtype/serialization/device/precision; contract self-contained; all governing ADR decisions inlined; mandatory sections enumerated). Plus mode-specific checklist: Audit Mode checklist (Accept); Revise Mode classification rules + version bump + reset to PROPOSED if previously ACCEPTED/LOCKED; Phase 4 conflict-detection rules (Creation).
  11. Mechanical precondition (do NOT dispatch on incomplete bundle): if provider AE undefined, governing ADR path broken, or `--revise` notes empty → STOP and surface the gap.
- **expected_output_path**: Creation — `dekspec/interface-contracts/IC-NNN-<slug>.md` (computed NNN + proposed slug); Accept / Revise — the input path.
- **validation**: `dekspec check validate <output-path>` (subagent runs before return; orchestrator re-runs independently) + `dekspec doctor --at .` (orchestrator final post-write fidelity check). Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry. Mode-specific post-checks: Creation → update `dekspec/interface-contract-index.md` by running `python ../_lib/scripts/artifact_ops.py update-index dekspec/interface-contract-index.md --id IC-NNN --status PROPOSED` (surface stderr on non-zero exit; the script appends a minimal row — fill in the Title cell); Accept → mechanical status walk via `python ../_lib/scripts/artifact_ops.py transition <IC-path> --from PROPOSED --to ACCEPTED` then `python ../_lib/scripts/artifact_ops.py update-index dekspec/interface-contract-index.md --id IC-NNN --status ACCEPTED` (surface stderr on non-zero exit; subagent does NOT walk status — only the pass/fail audit decision); Revise → version bumped if interface-affecting, Status reset to PROPOSED if previously ACCEPTED/LOCKED, index Modified updated.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-ic"
one_line:   "Create, audit, review, revise, accept, lock, or unlock Interface Contracts"
modes:
  - { flag: "", args: "<description>", description: "Create a new Interface Contract from the engineer's description or a spec reference (\"from WS-NNN\")." }
  - { flag: "--audit", args: "<IC-path>", description: "Read-only quality check: error semantics coverage, consistency guarantees, domain constraints, ADR consistency, and version number." }
  - { flag: "--review", args: "<IC-path>", description: "Walk through open issues interactively. Present each issue with context and a recommendation. Engineer resolves, defers, or dismisses each." }
  - { flag: "--revise", args: "<IC-path> <notes>", description: "Incorporate engineer review notes. Re-runs conflict detection on changed sections. Notes: inline text or path to notes file." }
  - { flag: "--accept", args: "<IC-path>", description: "Promote a PROPOSED Interface Contract to ACCEPTED (PROPOSED → ACCEPTED). Runs final audit; refuses if any check fails. Passing the flag counts as deliberate engineer approval — no additional confirmation is asked." }
  - { flag: "--lock", args: "<IC-path>", description: "Lock an ACCEPTED Interface Contract (ACCEPTED → LOCKED). Runs pre-lock audit. Rejects if any check fails." }
  - { flag: "--unlock", args: "<IC-path>", description: "Unlock a LOCKED Interface Contract (LOCKED → PROPOSED). Runs downstream impact assessment. Requires a reason." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing an Interface Contract section-by-section. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-ic the boundary between model server and API server"
  - "/write-ic from WS-001"
  - "/write-ic --audit dekspec/interface-contracts/IC-001-model-server-api.md"
  - "/write-ic --review dekspec/interface-contracts/IC-001-model-server-api.md"
  - "/write-ic --revise IC-001-model-server-api.md \"missing error case for timeout, consistency guarantee unclear for concurrent writes\""
  - "/write-ic --accept dekspec/interface-contracts/IC-001-model-server-api.md"
  - "/write-ic --lock dekspec/interface-contracts/IC-001-model-server-api.md"
  - "/write-ic --unlock dekspec/interface-contracts/IC-001-model-server-api.md"
  - "/write-ic --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: IC (Interface Contract)
- **template_path**: `templates/interface-contract-template.md`
- **methodology_section**: §4 Layer 2 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/interface-contracts/IC-001-contract-test-emitter.md` (compiler pipeline), `dekspec/interface-contracts/IC-004-executor-contract.md` (executor contract)
- **required_sections**: [Provider AE, Consumer AEs, Interface Definition, Domain Constraints, Error Semantics, Consistency Guarantees, Open Issues]

Skill-specific structural checks to surface as Open Issues: L4-IC-AE (missing provider, broken consumer reference). When prompting for Provider AE / Consumer AEs, validate that each AE-NNN reference resolves to an existing AE before accepting.

## Audit Mode

Read-only quality check on an existing Interface Contract.

1. Read the contract at the provided path
2. Check:
   - [ ] All template sections are populated — no placeholders, no TODOs in the body
   - [ ] Error semantics cover all error conditions for both parties
   - [ ] Consistency guarantees state what holds AND what does not hold
   - [ ] Domain constraints are explicit (no unexplained n/a)
   - [ ] Version number is set (not 0.1.0 placeholder)
   - [ ] No contradictions with governing ADRs (read each and verify consistency)
   - [ ] No contradictions with existing contracts in `dekspec/interface-contracts/`
   - [ ] Created and Modified dates are set
3. Report:

```
AUDIT: [path]
Status: [current status]

Passed: [N/total]
Failed:
  - [description of each failure]
```

Read-only — no changes made.

**End of Audit Mode.**

## Review Mode

Walk through open issues interactively — present each issue with context and a recommendation, resolve with the engineer one at a time.

Arguments: the contract path.

### Steps

1. Read the contract at the provided path
2. Parse the `## Open Issues` section. Collect all unchecked items (`- [ ]`).
3. If no unchecked items exist: "No open issues in [path]. Nothing to review." **End of Review Mode.**
4. Read the artifact's Purpose, Interface Definition, Error Semantics, and Consistency Guarantees sections for context.
5. Read governing ADRs and related contracts to check for cross-artifact relevance.
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
      - **Revise** — apply the agreed change to the artifact body, then check off the issue with resolution note. Bump the version number if the change affects the interface definition, error semantics, or consistency guarantees.
      - **Defer** — leave unchecked, optionally update the issue description with new context
      - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`
8. Update **Modified** date.
9. If any artifact body changes were made, re-run conflict detection (Phase 4 from the creation workflow) on the revised contract.
10. Present summary:
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

Incorporate engineer review notes into an Interface Contract.

Arguments after the path are the engineer's notes — inline text or a path to a `.md`/`.txt` file.

> **Fan-Out dispatch (per `ds-di2`).** Revise Mode is a substantive-work path: do NOT classify/edit the contract inline in this parent session. Instead, gather sources (existing contract, engineer notes, governing ADRs, related AEs/WSes) and dispatch a `dekspec:ic-author` subagent via the **Fan-Out Mode (default drafting path)** section, passing a revision-shaped prompt. The orchestrator validates the returned artifact and writes it to disk. Use the inline classification/iteration steps below only as the *bundled instructions* the subagent must follow.

1. Read the contract
2. Read the engineer's notes (inline or from file)
3. Classify each note as:
   - **Error semantics change** — affects error conditions or party behaviors
   - **Consistency change** — affects guarantees
   - **Domain constraint change** — affects boundary constraints
   - **Interface change** — affects the interface definition itself
   - **Structural issue** — suggests splitting or fundamental redesign
4. Present a revision plan with proposed changes per section
5. Wait for engineer approval. Structural issues always require explicit direction.
6. Apply approved changes. Update **Modified** date. Bump the version number.
7. If the revision introduces ambiguity, contradictions, or concerns that cannot be fully resolved during this revision, log them as new entries in the `## Open Issues` section with **Source:** `review` and appropriate severity. Inform the engineer: "New open issues were logged. Run `--review` to walk through them."
8. Re-run conflict detection (Phase 4 from the creation workflow) on the revised contract
9. If status was ACCEPTED or LOCKED, reset to PROPOSED.

**End of Revise Mode.**

## Accept Mode (PROPOSED → ACCEPTED)

Promotes a PROPOSED Interface Contract to ACCEPTED after every quality check passes. Passing the `--accept` flag is itself the deliberate engineer action of approval — no additional confirmation prompt is raised. The skill refuses to accept if any check fails; no partial acceptance exists.

> **Fan-Out dispatch (per `ds-di2`).** Accept Mode performs the substantive final-audit pass via a `dekspec:ic-author` subagent rather than inline. The orchestrator gathers the contract, governing ADRs, related AEs, and the full audit checklist; dispatches via the **Fan-Out Mode (default drafting path)** section with an audit-shaped prompt; then, on a clean return, performs the mechanical status-walk (set Status to ACCEPTED, update Modified, update the index) in this parent session. The mechanical status walk is NOT delegated — only the audit-pass-decision is.

### Step 1: Validate

1. Read the contract at the provided path
2. Verify current status is PROPOSED. If not, STOP:
   - TODO, DRAFT → "This contract is still [status]. It must be revised to PROPOSED before it can be accepted."
   - ACCEPTED → "This contract is already ACCEPTED."
   - LOCKED → "This contract is LOCKED. Unlock first with `--unlock` if changes are needed."

### Step 2: Final Audit

Run the complete Audit Mode check list — every check must pass.

- [ ] All template sections are populated — no placeholders, no TODOs in the body
- [ ] Error semantics cover all error conditions for both parties
- [ ] Consistency guarantees state what holds AND what does not hold
- [ ] Domain constraints are explicit (no unexplained n/a)
- [ ] Version number is set (not 0.1.0 placeholder)
- [ ] No contradictions with governing ADRs (read each referenced ADR and verify consistency)
- [ ] No contradictions with existing contracts in `dekspec/interface-contracts/`
- [ ] Created and Modified dates are set
- [ ] No blocking open issues remain (all items in Open Issues section are checked or non-blocking)

### Step 3: Report

```
FINAL AUDIT: [path]

Passed: [N/total]
Failed:
  - [description of each failure]

[If all passed]: All checks pass. Promoting PROPOSED → ACCEPTED.
[If any failed]: Cannot accept — resolve failures first. No changes made.
```

If any check fails, STOP — do not change status, do not update the index, do not make any other changes.

### Step 4: Accept

Only executed if Step 3 reported zero failures.

1. Flip Status PROPOSED → ACCEPTED and bump Modified — run `python ../_lib/scripts/artifact_ops.py transition <IC-path> --from PROPOSED --to ACCEPTED` (no `--note`: no Amendment Log entry on accept). Surface stderr on non-zero exit and STOP.
2. Update `dekspec/interface-contract-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/interface-contract-index.md --id IC-NNN --status ACCEPTED` (surface stderr on non-zero exit).

No Amendment Log entry is written — the log is reserved for changes made after LOCKED status, or when unlocking back to PROPOSED.

**End of Accept Mode.**

## Lock Mode (ACCEPTED → LOCKED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Lock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: Interface Contract
- **pre_lock_audit_ref**: §Audit Mode of this skill, extended with the IC-specific checks below
- **status_before**: ACCEPTED
- **status_after**: LOCKED
- **artifact_index_path**: `dekspec/interface-contract-index.md`

IC-specific pre-lock audit extensions (added on top of the substrate's audit run):
- Error semantics cover all error conditions for both parties
- Consistency guarantees state what holds AND what does not hold
- Domain constraints are explicit (no unexplained n/a)
- Version number is set (not the `0.1.0` placeholder)

## Unlock Mode (LOCKED → PROPOSED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: Interface Contract
- **status_before**: LOCKED
- **status_after**: PROPOSED
- **artifact_index_path**: `dekspec/interface-contract-index.md`

Downstream impact scan (run during Step 2 alongside the reason gate): grep specs and IBs for references to this contract; surface the impact list to the engineer before recording the reason. Cascade reminder to surface in Step 4: downstream specs and IBs may need review, affected IBs may need `/write-ibs --resync <affected IBs>`, and the contract must be re-locked via `/write-ic --lock <path>` when the substantive change settles.

## Input

Engineer's description or spec reference: $ARGUMENTS

## When to Use

- A cross-component boundary exists where both sides could be implemented independently
- The interface is external-facing
- Error semantics are complex enough that prose in a Working Spec is ambiguous
- Invoked standalone, or from Phase 5 of `/write-ws`

**Prose in the Working Spec is sufficient when:**
- Same team builds both sides in the same session or closely coordinated work

When in doubt, write the contract. The cost of an unnecessary contract is low; the cost of a misunderstood boundary is high.

## Phase 1: Context Gathering

1. Read the template from `dekspec/templates/interface-contract-template.md`
2. Read `dekspec/domain-glossary.md` for canonical domain terminology
3. Check `dekspec/interface-contract-index.md` — if a contract for this boundary already exists, read it and determine if this is an update (unlock and amend) or a duplicate
3. Determine the next IC number deterministically — run `python ../_lib/scripts/artifact_ops.py next-id ic` (surface stderr on non-zero exit)
4. If triggered from a Working Spec (`from WS-NNN`):
   - Read the spec to understand the boundary
   - Extract the parties, data exchanged, error conditions, and consistency requirements
5. If standalone:
   - Work from the engineer's description
6. Read all ADRs that govern this boundary (consult `dekspec/adr-index.md` for relevant ADRs)
7. Read relevant Architecture Elements for the components on each side
8. Identify the boundary type: HTTP API, Consistency contract, or In-process adapter — the structure of the Interface Definition section depends on this choice

## Phase 2: Draft

1. Draft the contract from the template, filling in all sections:
   - **Status:** DRAFT
   - **Created:** today's date
   - **Modified:** today's date
   - **Version:** 0.1.0
   - **Silent Failure Domain(s):** check all that apply; if two or more domains are checked, verify during Phase 4 that splitting the contract is not preferable
   - **Governing ADRs**
   - **Purpose** — why this contract exists as a separate document
   - **Parties** — who is on each side, their roles, process, device
   - **Relationship Pattern** — select one DDD context-mapping pattern (Open Host Service, Customer-Supplier, Anti-Corruption Layer, Conformist, Shared Kernel, Published Language) and state who adapts when the interface changes
   - **Shared Conventions** — conventions that apply across all operations (serialization, content types, error structure, tenant isolation)
   - **Interface Definition** — structure based on boundary type (HTTP API / Consistency / Adapter)
   - **Domain Constraints** (optional) — project-specific cross-cutting constraints that apply at the boundary (e.g., compute-device pinning, serialization format, precision/numeric thresholds, encoding/coordinate conventions, time/timezone discipline). Omit the section if not applicable to the contract or project.
   - **Error Semantics** — every error condition at the boundary, with behavior for both parties
   - **Consistency Guarantees** — what holds AND what does NOT hold
   - **Amendment Log** — empty on initial creation
2. Present draft for engineer review — engineer should verify parties, shared conventions, error semantics, and consistency guarantees

## Phase 3: ADR Check

For each governing ADR referenced in the contract:
1. Read the ADR and verify its Status and Supersession fields
   - If `Superseded by` names another ADR — read the superseding ADR instead
   - If PROPOSED — flag to the engineer if it governs a critical constraint
2. Verify the contract is consistent with all governing ADRs
3. If the contract reveals an undocumented decision, invoke `/write-adr` to create the ADR before completing the contract

## Phase 4: Conflict Detection

Before saving, check for conflicts:

1. **ADR vs. contract** — does any contract term contradict a governing ADR?
2. **Contract vs. existing contracts** — does this contract contradict or overlap with any existing contract in `dekspec/interface-contracts/`?
3. **Contract vs. Working Spec** — if triggered from a spec, does the contract contradict anything in the spec?

For each conflict:
- State the conflict explicitly
- Ask the engineer to resolve before proceeding
- Do NOT guess or save with the conflict unresolved

## Phase 5: Finalize

1. Set **Status** to PROPOSED
2. Update **Modified** to today's date
3. Save to `dekspec/interface-contracts/IC-NNN-[slug].md`
4. Update `dekspec/interface-contract-index.md` — add a row with ID, Title (linked), Status (PROPOSED), Created date, Modified date
5. If triggered from `/write-ws`, report back the contract path so the spec can reference it

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/interface-contracts/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Interface Contract depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `IC-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional IC <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/IC-provisional-<title-slug>.md` (the CLI prints the path).
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
- Every error condition must have a stated behavior for both parties
- "Silent degradation" is never a valid behavior
- Domain constraints at the boundary must be explicit — dtype, serialization format, device, precision
- The contract must be self-contained — a developer implementing either side should be able to do so correctly from this contract alone, without reading the other side's Working Spec
- All governing ADR decisions must be inlined into the contract (shared conventions, domain constraints), not just referenced
- The template (`dekspec/templates/interface-contract-template.md`) must be completely filled out. All mandatory sections: Status, Created, Modified, Version, Silent Failure Domains, Governing ADRs, Purpose, Parties, Shared Conventions, Interface Definition, Error Semantics. **Domain Constraints** is optional — populate when the contract has project-specific cross-cutting constraints to inline, otherwise omit the section. Consistency Guarantees is required unless the contract is stateless request-response with no shared state. Amendment Log is empty on creation. If information is missing for a mandatory section, ask the engineer before proceeding — do not guess or leave blanks.

## Output

- `dekspec/interface-contracts/IC-NNN-[slug].md` with status PROPOSED
- Updated `dekspec/interface-contract-index.md`
- Any ADRs flagged as needed during the process

## Approve Mode

`--approve` records a peer-review approval signature on an Interface Contract under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the IC's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <IC-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED` or `LOCKED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the IC may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Common Pitfalls

- Don't state an error condition with behavior for only one party — every error at the boundary needs the producer-side AND consumer-side reaction, or the contract is half-written.
- Don't write "silent degradation," "best effort," or "fails gracefully" as a behavior — name the concrete observable outcome (status code, raised type, default value) for each error.
- Don't merely reference a governing ADR — inline its decision (shared convention, domain constraint) into the contract body so an implementer can build either side from this document alone.
- Don't author or accept inline — Creation, `--accept`, and `--revise` are substantive paths that MUST dispatch a `dekspec:ic-author` subagent via Fan-Out Mode; the parent session only does the mechanical status walk.
- Don't classify a `--revise` change as interface-affecting without bumping the version and resetting an ACCEPTED/LOCKED contract back to PROPOSED.
- Don't leave the consistency guarantee one-sided — state what holds AND what explicitly does NOT hold; omit the section only for stateless request-response with no shared state.
- Don't claim a canonical `IC-NNN` ID when the work spans an incubation that hasn't reached ACCEPTED — use `--provisional <slug>` instead.

## Verification Checklist

- [ ] Every error condition in §Error Semantics names a behavior for BOTH parties (no one-sided rows, no "silent degradation").
- [ ] Consistency Guarantees states what holds and what does not hold (or the contract is genuinely stateless request-response).
- [ ] Every governing ADR decision is inlined into the contract body, not merely referenced; all ADR refs resolved through any `Superseded by` chain.
- [ ] Substantive modes (Creation / `--accept` / `--revise`) ran via a `dekspec:ic-author` fan-out subagent, not inline in the parent.
- [ ] `dekspec check validate <output-path>` exited 0 and `dekspec doctor --at .` was re-run post-write by the orchestrator.
- [ ] `dekspec/interface-contract-index.md` row reflects the final Status (PROPOSED / ACCEPTED) with the Title cell filled.
- [ ] For `--revise`: version bumped when interface-affecting, and an ACCEPTED/LOCKED contract reset to PROPOSED.
- [ ] `dekspec audit relink` ran against the repo root as the final action.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an Interface Contract — Creation, `--accept`, `--revise`, `--lock`, `--unlock`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
