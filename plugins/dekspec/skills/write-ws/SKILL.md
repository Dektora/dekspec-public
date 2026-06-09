---
name: write-ws
description: Write a Working Spec with full expertise audit and serialized role passes. Use when a feature or subsystem needs behavioral contracts before implementation.
mode: full
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --accept | --approve | --lock | --unlock | --revise] [description or path to spec] [notes]
related_skills: [write-intent, write-ae, write-adr, write-ic, write-ibs]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Write, lock, or unlock a Working Spec.

## Starter Prompt

```prompt
/dekspec:write-ws the salt synthesis pipeline from ingest to mind map node creation

Write the behavioral contract for the salt pipeline under INT-042. Cover the
ingest → moment-stack → embedding-scoring → mind-map-node-creation stages, the
failure mode when the moment stack is empty, and the CUDA-device constraint on
embedding scoring. It consumes the timeline store (AE-011) and produces graph nodes.
```

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill requires deep reasoning across multiple expert role passes and ADR reconciliation. Prior conversation context can degrade quality by introducing bias and attention dilution.
>
> First message → proceed. Prior history → ask "context may affect WS quality, recommend /clear, continue? (y/n)" + wait.

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
- **Creation mode** — no flag. Proceed to **Input**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--audit`, `--review`, `--lock`, `--unlock`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:ws-author`
- **substantive_modes**: [Creation (default), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`, `--review`, `--lock`, `--unlock`]
- **bundle_list** (Step 1 context):
  1. Template path — `dekspec/templates/working-spec-template.md`.
  2. Methodology references — `docs/dekspec-methodology.md` §4 Layer 2 (Working Specs); `dekspec/dekspec-operating-guide.md` §Working Specs (if present).
  3. Parent Intent path — if `$ARGUMENTS` (or, for `--accept` / `--revise`, the target spec's front-matter) references an Intent (`INT-NNN`), resolve to `dekspec/intents/INT-NNN-<slug>.md`. Omit if no parent Intent applies.
  4. Related artifacts from the spec graph (paths only — subagent reads what it needs): `dekspec/architecture-elements-index.md` (for `Related Architecture Elements:` population); run `python ../_lib/scripts/bundle_related.py --keywords "<spec-domain-keywords>" --include ae,adr,ic` to get candidate provider/consumer AE paths, related IC paths (the IC dir is `dekspec/interface-contracts/`), and ADR paths whose linkage sections touch this spec's boundary — judge which AEs are providers vs consumers and which ICs/ADRs are relevant, then bundle those; resolve each referenced ADR via `python ../_lib/scripts/resolve_supersession.py <ADR-ID>` so supersession chains are followed deterministically; for `--accept` / `--revise` — run `python ../_lib/scripts/bundle_related.py --for <target-spec-path> --include ae,adr,ic,ib --backlinks` to also surface IBs referencing this spec, plus the target spec path + (for `--revise`) engineer's notes (inline or file path); `dekspec/domain-glossary.md`; `dekspec/working-spec-index.md` (next-WS-NNN for Creation; status row for Accept / Revise).
  5. Expertise-audit role list (pass verbatim — subagent runs Phase 2 + Phase 3 in fresh context): Writer (Phase 1); ML Expert (injection / position IDs / KV cache); Quantization Expert (quantization / precision / serialization); CUDA Expert (CUDA device / process isolation); Graph Expert (mind map / shadow graph / multi-store / timeline / topic segmentation / decay / shadow timeline / quantization tier); Embedding Geometer (embedding scoring / compression); Pipeline Analyst (pipeline stage ordering); Options Architect (architectural alternatives — Phase 4; may invoke `/write-adr`); Critic (Phase 6 + conditional Phase 7 on changed sections only). Role prompts file: `dekspec/project-context.md` (subagent loads each triggered role's prompt).
  6. Engineer guidance — `$ARGUMENTS` verbatim (Creation: the description; `--accept`: the spec path; `--revise`: spec path + notes).
  7. Constraints — the Rules block at the bottom of this skill (1-2 pages max; every business rule testable; every failure mode has stated behavior; serialized role passes; template fully populated; self-contained spec — no cross-WS references; cascade awareness for IBs; corrections logged via `/write-ggc --log`).
- **expected_output_path**: `dekspec/working-specs/WS-NNN-<slug>.md` (Creation) or the input path (`--accept` / `--revise`; subagent edits in place).
- **validation**: `dekspec check validate <output-path>`. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry. Mode-specific post-checks: Creation — Status PROPOSED + index row added + Expertise Audit Record present; `--accept` — Status ACCEPTED + index updated + no Amendment Log entry (reserved for post-LOCK changes); `--revise` — Modified updated + reset to PROPOSED if previously ACCEPTED/LOCKED + new ambiguities under `## Open Issues` + IB cascade reminder surfaced if IBs exist.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-ws"
one_line:   "Create, audit, review, revise, accept, lock, or unlock Working Specs"
modes:
  - { flag: "", args: "<description>", description: "Create a new Working Spec with expertise audit and serialized role passes." }
  - { flag: "--audit", args: "<WS-path>", description: "Read-only quality check: template completeness, ADR consistency, domain constraints, failure modes, expertise audit record, and open issues." }
  - { flag: "--review", args: "<WS-path>", description: "Walk through open issues interactively. Present each issue with context and a recommendation. Engineer resolves, defers, or dismisses each." }
  - { flag: "--revise", args: "<WS-path> <notes>", description: "Incorporate engineer review notes. Re-runs affected expertise audit passes and critic review on changed sections. Notes: inline text or path to notes file." }
  - { flag: "--accept", args: "<WS-path>", description: "Promote a PROPOSED Working Spec to ACCEPTED (PROPOSED → ACCEPTED). Runs final audit; refuses if any check fails. Passing the flag counts as deliberate engineer approval — no additional confirmation is asked." }
  - { flag: "--lock", args: "<WS-path>", description: "Lock an ACCEPTED Working Spec (ACCEPTED → LOCKED). Runs pre-lock audit. Rejects if any check fails." }
  - { flag: "--unlock", args: "<WS-path>", description: "Unlock a LOCKED Working Spec (LOCKED → PROPOSED). Runs downstream impact assessment. Requires a reason." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing a Working Spec section-by-section. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-ws the salt synthesis pipeline from ingest to mind map node creation"
  - "/write-ws --audit dekspec/working-specs/WS-001-salt-pipeline.md"
  - "/write-ws --review dekspec/working-specs/WS-001-salt-pipeline.md"
  - "/write-ws --revise WS-001-salt-pipeline.md \"failure mode for empty moment stack is missing, add CUDA device constraint for embedding scoring\""
  - "/write-ws --accept dekspec/working-specs/WS-001-salt-pipeline.md"
  - "/write-ws --lock dekspec/working-specs/WS-001-salt-pipeline.md"
  - "/write-ws --unlock dekspec/working-specs/WS-001-salt-pipeline.md"
  - "/write-ws --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: WS (Working Spec)
- **template_path**: `templates/working-spec-template.md`
- **methodology_section**: §4 Layer 2 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/working-specs/WS-001-audit-rule-semantics.md` (audit-rule semantics), `dekspec/working-specs/WS-003-executor-swap-contract.md` (executor-swap contract)
- **required_sections**: [Status, Silent Failure Domains, Related Architecture Elements, Business Rules, Failure Behavior, Acceptance Criteria, Domain Constraints, Open Issues]

Skill-specific structural checks to surface as Open Issues: T20-WS-BUSINESS-RULES, T21-WS-FAILURE-BEHAVIOR, L3-WS-AE.

**Skill-unique prompts and scope:** for Silent Failure Domains, walk the engineer through the project-specific enum and which apply before accepting input. Teaching Mode walks a single WS section-by-section; the default no-flag creation mode triggers a full expertise-audit + serialized role-passes workflow that Teaching Mode deliberately skips for new authors.

## Audit Mode

Read-only quality check on an existing Working Spec.

1. Read the spec at the provided path
2. Check:
   - [ ] All template sections are populated — no placeholders, no TODOs in the body
   - [ ] All Domain Constraints populated (no unexplained n/a)
   - [ ] All required contract sections present (based on active silent failure domains)
   - [ ] Zero `P1` open issues remain — count every blocking-family alias that normalizes to `P1` per ADR-013: canonical `P1`, plus the legacy aliases `blocking_pre_ib` / `blocking (pre-IB)` and bare `blocking`. (This is exactly what audit rule `L12-WS-BLOCKING-PRE-IB-CLEAN` enforces on any ACCEPTED+ WS; `blocking (pre-code)` / `blocking_pre_code` normalizes to `P2` and is not part of this gate.)
   - [ ] All business rules are testable
   - [ ] All failure modes have stated behavior
   - [ ] No contradictions with governing ADRs (read each and verify consistency)
   - [ ] Expertise Audit Record is complete (all triggered roles show evidence)
   - [ ] Spec fits 1-2 pages
   - [ ] Created and Modified dates are set
   - [ ] If IBs exist for this spec, check consistency between spec and IB content
3. Report:

```
AUDIT: [path]
Status: [current status]

Passed: [N/total]
Failed:
  - [description of each failure]

IB consistency: [no IBs / consistent / N inconsistencies found]
```

Read-only — no changes made.

**End of Audit Mode.**

## Review Mode

Walk through open issues interactively — present each issue with context and a recommendation, resolve with the engineer one at a time.

Arguments: the spec path.

### Steps

1. Read the spec at the provided path
2. Parse the `## Open Issues` section. Collect all unchecked items (`- [ ]`).
3. If no unchecked items exist: "No open issues in [path]. Nothing to review." **End of Review Mode.**
4. Read the artifact's Specification, Domain Constraints, and failure mode sections for context.
5. Read governing ADRs and related architecture elements to check for cross-artifact relevance.
6. Present a summary:
   ```
   REVIEW SESSION: [path]
   Status: [current status]
   Open issues: [N] ([M] blocking (pre-IB), [K] blocking (pre-code), [J] non-blocking)
   
   Starting guided review...
   ```
6.5. **Spec-Reviewer dispatch** (shared `reviewer_mode` path — see [`_lib/reviewer_mode.md`](../_lib/reviewer_mode.md)). This ADDS an adversarial Spec-Reviewer pass alongside the open-issue loop; it does NOT replace it. Perform the shared four-step dispatch:
   a. Load the `spec-reviewer` ContextSpec: `from dekspec.constraint_compiler.parser import parse_context_spec; context_spec = parse_context_spec("dekspec/context-specs/role-spec-reviewer.md")` (`context_spec["role_identity"] == "spec-reviewer"`).
   b. Take the `ReviewerWS` artifact this `--review` mode already holds (the WS at the provided path; the caller owns this IO, the dispatcher is IO-free).
   c. Dispatch through the shared surface: `from dekspec.spec_review.reviewer import Reviewer; findings = Reviewer().dispatch(context_spec, artifact)` (`-> list[Finding]`, per IC-016).
   d. Present each returned `Finding` to the engineer at its severity (default `P2` — approval-blocking, not auto-merge) as additional review items alongside the open issues below. Do not reshape the records; they route into the AE-003 surface via the `SPEC-REVIEW` audit-rule family (`dekspec.spec_review.reviewer` → `spec_review_rules`).
7. For each unchecked issue, in order:
   a. Present the issue:
      ```
      ───────────────────────────────────────
      ISSUE [N/total]: [issue description]
      Source: [source]
      Severity: [blocking (pre-IB) / blocking (pre-code) / non-blocking]
      ───────────────────────────────────────
      ```
   b. Analyze the issue against the current spec content:
      - Has this issue already been addressed by changes to the spec since it was logged?
      - Is the issue still valid given the current state of governing ADRs and related artifacts?
      - What would resolving this issue require — a text change to this spec, a structural change, or an upstream change (new ADR, architecture element revision)?
   c. Present a recommendation:
      ```
      RECOMMENDATION: [resolve / revise spec / defer / dismiss]
      
      [Specific explanation — what to change and why, or why to defer/dismiss]
      
      [If resolve or revise: show the proposed text change]
      ```
   d. Wait for the engineer's response.
   e. Based on response:
      - **Resolve** — check off the issue, append resolution: `- [x] [Issue] — **Source:** ... — **Severity:** ... — **Resolved:** [today] [resolution summary]`
      - **Revise** — apply the agreed change to the spec body, then check off the issue with resolution note
      - **Defer** — leave unchecked, optionally update the issue description with new context
      - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`
8. Update **Modified** date.
9. If any spec body changes were made and IBs exist for this spec, warn: "IBs exist for this spec. After review changes are finalized, run `/write-ibs --resync` on affected IBs."
10. Present summary:
    ```
    REVIEW COMPLETE: [path]
    
    Resolved: [N]
    Dismissed: [N]
    Deferred: [N]
    
    [If blocking (pre-IB) issues remain]: ⚠️  [N] blocking (pre-IB) issues remain — cannot run /write-ibs.
    [If blocking (pre-code) issues remain]: ⚠️  [N] blocking (pre-code) issues remain — IBs can be written but beads cannot start.
    [If no blocking issues remain]: ✅ No blocking issues remain — spec is clear for status advancement and IB generation.
    ```

**End of Review Mode.**

## Revise Mode

Incorporate engineer review notes into a Working Spec.

Arguments after the path are the engineer's notes — inline text or a path to a `.md`/`.txt` file.

1. Read the spec
2. Read the engineer's notes (inline or from file)
3. Classify each note as:
   - **Business rule change** — affects the Specification section
   - **Domain constraint change** — affects Domain Constraints or silent failure domains
   - **Failure mode change** — affects stated failure behaviors
   - **Scope change** — affects what the spec covers
   - **Structural issue** — suggests splitting or merging specs
4. Present a revision plan with proposed changes per section
5. Wait for engineer approval. Structural issues always require explicit direction.
6. Apply approved changes. Update **Modified** date.
7. If the revision introduces ambiguity, contradictions, or concerns that cannot be fully resolved during this revision, log them as new entries in the `## Open Issues` section with **Source:** `review` and appropriate severity. Inform the engineer: "New open issues were logged. Run `--review` to walk through them."
8. Re-run affected expertise audit passes — if the change touches a domain that triggered an expert role, re-run that role's pass on the changed sections only
9. Re-run one critic pass on the changed sections
10. If status was ACCEPTED or LOCKED, reset to PROPOSED.
11. If IBs exist for this spec, warn: "IBs exist for this spec. After revisions are finalized, run `/write-ibs --resync` on affected IBs."

**End of Revise Mode.**

## Accept Mode (PROPOSED → ACCEPTED)

Promotes a PROPOSED Working Spec to ACCEPTED after every quality check passes. Passing the `--accept` flag is itself the deliberate engineer action of approval — no additional confirmation prompt is raised. The skill refuses to accept if any check fails; no partial acceptance exists.

### Step 1: Validate

1. Read the spec at the provided path
2. Verify current status is PROPOSED. If not, STOP:
   - TODO, DRAFT → "This spec is still [status]. It must be revised to PROPOSED before it can be accepted."
   - ACCEPTED → "This spec is already ACCEPTED."
   - LOCKED → "This spec is LOCKED. Unlock first with `--unlock` if changes are needed."

### Step 2: Final Audit

Run the complete Audit Mode check list — every check must pass, including IB consistency if any IBs exist.

- [ ] All template sections are populated — no placeholders, no TODOs in the body
- [ ] All Domain Constraints populated (no unexplained n/a)
- [ ] All required contract sections present (based on active silent failure domains)
- [ ] Zero `P1` open issues remain — count every blocking-family alias that normalizes to `P1` per ADR-013: canonical `P1`, plus the legacy aliases `blocking_pre_ib` / `blocking (pre-IB)` and bare `blocking`. This gate must match audit rule `L12-WS-BLOCKING-PRE-IB-CLEAN` exactly — it fires P1 on ANY `P1` open issue once a WS is ACCEPTED+, so a narrower gate here lets a WS pass `--accept` then immediately fail `dekspec doctor`. (`blocking (pre-code)` / `blocking_pre_code` normalizes to `P2` and is NOT part of this gate.)
- [ ] All business rules are testable
- [ ] All failure modes have stated behavior
- [ ] No contradictions with governing ADRs (read each and verify consistency)
- [ ] Expertise Audit Record is complete (all triggered roles show evidence)
- [ ] Spec fits 1-2 pages
- [ ] Created and Modified dates are set
- [ ] If IBs exist for this spec, spec content is consistent with IB content

### Step 3: Report

```
FINAL AUDIT: [path]

Passed: [N/total]
Failed:
  - [description of each failure]

IB consistency: [no IBs / consistent / N inconsistencies found]

[If all passed and IB consistency is clean]: All checks pass. Promoting PROPOSED → ACCEPTED.
[If any failed or IB inconsistency found]: Cannot accept — resolve failures first. No changes made.
```

If any check fails or IB inconsistency is found, STOP — do not change status, do not update the index, do not make any other changes.

### Step 4: Accept

Only executed if Step 3 reported zero failures and IB consistency clean.

1. Flip Status PROPOSED → ACCEPTED and bump Modified — run `python ../_lib/scripts/artifact_ops.py transition <WS-path> --from PROPOSED --to ACCEPTED` (no `--note`: no Amendment Log entry on accept). Surface stderr on non-zero exit and STOP.
2. Update `dekspec/working-spec-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/working-spec-index.md --id WS-NNN --status ACCEPTED` (surface stderr on non-zero exit).

No Amendment Log entry is written — the log is reserved for changes made after LOCKED status, or when unlocking back to PROPOSED.

**End of Accept Mode.**

## Lock Mode (ACCEPTED → LOCKED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Lock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: Working Spec
- **pre_lock_audit_ref**: §Audit Mode of this skill, extended with the WS-specific checks below
- **status_before**: ACCEPTED
- **status_after**: LOCKED
- **artifact_index_path**: `dekspec/working-spec-index.md`

WS-specific pre-lock audit extensions (added on top of the substrate's audit run):
- All active silent failure domains have at least one business rule
- All failure modes have stated behavior
- All business rules are testable
- Expertise Audit Record is complete (all triggered roles show evidence of their pass)
- If Implementation Briefs exist for this spec, verify they are consistent with current spec content
- Zero `P1` open issues remain — count every blocking-family alias that normalizes to `P1` per ADR-013: canonical `P1`, plus the legacy aliases `blocking_pre_ib` / `blocking (pre-IB)` and bare `blocking`. This gate must match audit rule `L12-WS-BLOCKING-PRE-IB-CLEAN` exactly (it fires P1 on ANY `P1` open issue on a LOCKED WS). `blocking (pre-code)` / `blocking_pre_code` normalizes to `P2` and is NOT part of this gate.

## Unlock Mode (LOCKED → PROPOSED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: Working Spec
- **status_before**: LOCKED
- **status_after**: PROPOSED
- **artifact_index_path**: `dekspec/working-spec-index.md`

Downstream impact scan (run during Step 2 alongside the reason gate): check `dekspec/impl-briefs/` for IBs referencing this spec, then `.beads/beads.jsonl` for beads referencing those IBs; surface the impact list to the engineer before recording the reason. If any beads are `in_progress` or `closed`, surface an extra warning ("active or completed beads exist downstream; unlocking and changing this spec may invalidate completed work") before continuing. Cascade reminder to surface in Step 4: affected IBs need `/write-ibs --resync <affected IBs>` then `/write-ibs --accept <IBs>`, affected beads need `/write-beads <IB>`, and the spec must be re-locked via `/write-ws --lock <path>` when the substantive change settles.

## Input

Engineer's description: $ARGUMENTS

## Phase 1: Writer Draft

1. Read the Writer role from `dekspec/project-context.md`
2. Read `dekspec/domain-glossary.md` for canonical domain terminology
3. Read the template from `dekspec/templates/working-spec-template.md`
4. Determine the next WS number deterministically — run `python ../_lib/scripts/artifact_ops.py next-id ws` (surface stderr on non-zero exit)
5. Draft the spec from the engineer's description, filling in all template sections
5. Set **Status** to `DRAFT`, **Created** to today's date, **Modified** to today's date
6. Present for engineer review of scope and intent

## Phase 2: Expertise Audit

Run the audit checklist against the draft:

```
Spec touches injection, position IDs, KV cache?          → ML Expert
Spec touches quantization, precision, serialization?      → Quantization Expert
Spec touches CUDA device or process isolation?            → CUDA Expert
Spec touches mind map, shadow graph, multi-store?         → Graph Expert
Spec touches timeline, topic segmentation, decay,
  shadow timeline, or quantization tier assignment?       → Graph Expert (timeline scope)
Spec touches embedding scoring or compression?            → Embedding Geometer
Spec touches pipeline stage ordering?                     → Pipeline Analyst
Spec depends on an undocumented decision?                 → write ADR first via /write-adr
```

Present the audit results. Engineer confirms which roles are triggered.

## Phase 3: Knowledge Expert Passes (STRICTLY serialized — no parallel execution)

Each triggered role runs one at a time, in order. Each pass reads the spec AS UPDATED by all previous passes. Do NOT run multiple expert passes in parallel — each expert must build on the previous expert's improvements to avoid conflicts and maintain coherence.

For each triggered role:
1. Read the role prompt from `dekspec/project-context.md`
2. Apply the role lens to the CURRENT spec (including all prior expert updates)
3. Produce findings
4. Apply findings to the spec immediately
5. Confirm the spec is consistent after updates
6. Save the updated spec before proceeding to the next role

Order (strict sequence): ML Expert → save → Quantization Expert → save → CUDA Expert → save → Graph Expert → save → Embedding Geometer → save → Pipeline Analyst → save

## Phase 4: Options Architect (conditional)

If genuine architectural alternatives exist:
1. Read the Options Architect role from `dekspec/project-context.md`
2. Surface options with tradeoffs
3. Engineer decides
4. Write ADRs for each decision via `/write-adr`

## Phase 5: Interface Contracts (conditional)

If the spec defines a cross-component boundary where both sides could be implemented independently, invoke `/write-ic` with context about which boundary and this spec's number. The interface contract skill handles drafting, ADR verification, conflict detection, and saving. It will report back the contract path for inclusion in this spec's output.

**Write a formal contract when:**
- The interface is consumed by a different component built independently
- The interface is external-facing
- Error semantics are complex enough that prose is ambiguous

**Prose in the Working Spec is sufficient when:**
- Same team builds both sides in the same session or closely coordinated work

## Phase 6: Critic Pass 1

1. Read the Critic role from `dekspec/project-context.md`
2. Review the full spec — completeness, consistency, implementability
3. Verify the expertise audit: check trigger rules against the spec's Interfaces and Domain Constraints — if the spec touches a domain but shows no evidence of that role's pass, flag it
4. Present findings for engineer resolution

## Phase 7: Critic Pass 2 (conditional)

If non-trivial changes were made after Critic Pass 1:
1. Review only the changed sections
2. Never run a third pass — split the spec instead

## Phase 8: Finalize

1. Set **Status** to `PROPOSED`
2. Update **Modified** to today's date
3. Save to `dekspec/working-specs/WS-NNN-[slug].md`
4. Update `dekspec/working-spec-index.md` — add a row with ID, Title, Status (PROPOSED), Created date, Modified date

## Finalization Checklist

Before declaring the spec complete, verify:
- [ ] Status is PROPOSED
- [ ] Created and Modified dates are set
- [ ] All Domain Constraints populated (no unexplained n/a)
- [ ] All required contract sections present (Model, Graph, Timeline, Quantization — based on active silent failure domains)
- [ ] Zero `P1` open issues remain — count canonical `P1` plus the blocking-family aliases `blocking_pre_ib` / `blocking (pre-IB)` and bare `blocking` (all normalize to `P1` per ADR-013, matching audit rule `L12-WS-BLOCKING-PRE-IB-CLEAN`)
- [ ] Spec fits 1-2 pages
- [ ] All business rules testable
- [ ] All failure modes have stated behavior
- [ ] No contradictions with governing ADRs

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/working-specs/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Working Spec depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `WS-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional WS <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/WS-provisional-<title-slug>.md` (the CLI prints the path).
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
- 1-2 pages maximum — if more is needed, split the spec
- Every business rule must be testable
- Every failure mode must have a stated behavior
- Open issues are stated explicitly, never buried in vague prose
- Serialize role passes — each reads what the previous one added
- The template (`dekspec/templates/working-spec-template.md`) must be completely filled out. Every section, every placeholder. If information is missing, ask the engineer before proceeding — do not guess or leave blanks.
- **Working specs must be independent and self-contained.** A spec must stand alone — a coding agent reading only that spec and the ADRs/architecture elements it references must be able to implement the component correctly. Do NOT reference other working specs. If this spec's component has an interface with another component, describe the interface contract from THIS component's perspective (what it produces, what it consumes, what guarantees it requires). Do not say "see WS-NNN for details" — instead, state the contract directly. Working specs may reference ADRs and architecture elements, which are shared architectural context.
- **Cascade awareness:** If this spec changes after Implementation Briefs exist, all affected IBs must be regenerated via `/write-ibs` and all affected beads recreated via `/write-beads`.

## Output

- `dekspec/working-specs/WS-NNN-[slug].md`
- Updated `dekspec/working-spec-index.md`
- Any ADRs produced during the process
- Any interface contracts produced during the process

## Approve Mode

`--approve` records a peer-review approval signature on a Working Spec under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the WS's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <WS-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED` or `LOCKED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the WS may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Common Pitfalls

- Don't reference another Working Spec (`see WS-NNN for details`) — restate the interface contract from THIS component's perspective so the spec stays self-contained for a coding agent reading only it plus its ADRs/AEs.
- Don't run the Phase 3 expert passes in parallel — serialize them strictly (ML → Quantization → CUDA → Graph → Embedding → Pipeline), saving after each, so every expert builds on the prior one's edits.
- Don't pass `--accept` / `--lock` with any `P1` open issue still open — count the blocking-family aliases (`blocking_pre_ib` / `blocking (pre-IB)` / bare `blocking`) that normalize to `P1` per ADR-013, or the WS clears the skill gate then immediately fails `L12-WS-BLOCKING-PRE-IB-CLEAN` under `dekspec doctor`.
- Don't combine `--lock` with `--provisional` — LOCKED requires linkage-walker visibility that provisional artifacts lack; route to LOCKED through the hand-promote workflow instead.
- Don't `Edit`/`Write` a claimed canonical artifact without first running `dekspec library cow-stage <path>` — redirect to the printed provisional sibling when it exits 0, or `T-COW-CANONICAL-EDITED` fires advisory on the next linkage run.
- Don't silently correct a domain misinterpretation — invoke `/write-ggc --log` with the correction before proceeding so the glossary-promotion pipeline sees it.
- Don't skip `dekspec audit relink` at the end of a substantive run — the backlinks are not optional and must not be deferred with a "backfill later" note.

## Verification Checklist

- [ ] Status reflects the mode's terminal state — PROPOSED after Creation, ACCEPTED after `--accept`, LOCKED after `--lock`, PROPOSED after `--unlock`/`--revise` (reset from ACCEPTED/LOCKED).
- [ ] `dekspec check validate <output-path>` exits 0 (surfaced verbatim, not silently retried).
- [ ] `dekspec/working-spec-index.md` has the matching row with the current Status; Created and Modified dates are set.
- [ ] Every triggered expertise-audit role shows evidence in the Expertise Audit Record; spec fits 1-2 pages.
- [ ] Zero `P1` open issues remain (canonical `P1` + all blocking-family aliases per ADR-013) for any ACCEPTED+ WS.
- [ ] No `see WS-NNN` cross-references in the body; all interfaces are restated from this component's perspective.
- [ ] IB cascade reminder surfaced if Implementation Briefs reference this spec and the body changed.
- [ ] `dekspec audit relink` was run against the repo root as the final action.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise a Working Spec — Creation, `--accept`, `--revise`, `--lock`, `--unlock`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
