---
name: write-mission
description: Author, review, audit, activate, complete, kill, or supersede a Mission (MSN-NNN) — the long-horizon container above Intents. Use when work plausibly decomposes into more than one Intent, or requires a feature flag, or shares an outcome / kill criterion / out-of-scope contract across Intents. Phase 2 + Phase 3 P3.5 deliverable.
mode: full
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--canonical] [--provisional <slug>] [--help | --teaching | --audit | --review | --approve | --activate | --complete | --kill | --supersede] [description or path to Mission]
related_skills: [write-intent, spec-intent, write-sv, write-ae]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

> **Scope of this skill (Phase 2).** A Mission (`MSN-NNN`) holds an ordered queue of Intents that share an outcome, a feature flag, a release boundary, or a kill criterion. Most work in Phase 1 did not need a Mission; single-Intent work skips this skill entirely. A Mission is created when *any* of: the work plausibly decomposes into more than one Intent at first sketch; a feature flag will guard partial state during rollout; multiple Intents need to share an outcome / out-of-scope contract / kill criterion; the work spans more than ~1 week of execution.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> A Mission is rigorous up-front on its near-immutable section and continuously revised on the live section. Prior conversation context can degrade the up-front rigor by anchoring on partial sketches before the outcome is settled.
>
> Inline reasoning only (see mode manifest); substantive fan-out skips this check. First message → proceed. Prior history → ask "context may affect Mission quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-mission stabilize WS-028 attachment processing across the 5 sub-Intents autonomy: medium flag: attachments_v2

The retry/backoff, dedup, and quarantine work all share the attachments_v2 flag and the same "no attachment is lost on transient failure" outcome — group them under one Mission so the flag-removal and kill criterion are shared, not duplicated per Intent.
```

## Session-Start Reminder (Provisional Awareness)

When entering Creation Mode or Review Mode on a Mission that is in `PROPOSED` or `ACTIVE` (pre-COMPLETE), surface this one-line banner before the first substantive action:

> 📝 While this Mission is in pre-terminal status, every change to canonical artifacts in any of its child Intents' `Components affected` scope should be auto-staged to `dekspec/provisional/<incubation-slug>/` via a `replaces:` frontmatter stamp (the CoW spec staging discipline from INT-082). The canonical spec graph is frozen for those paths until the relevant child Intent runs `/write-intent --accept`. Use `dekspec library new-provisional <KIND> <slug>` to stage a copy-on-write artifact. The `T-COW-CANONICAL-EDITED` audit rule (P2 mechanical) catches direct-edit bypasses of this guard.

Skip the banner in Audit / Help / Teaching / Kill / Supersede modes — those operate on already-locked-in artifacts and the CoW guard does not apply.

**Roles (ADR-061).** This skill plays DekSpec's Agent Role Specifications; the engineer never selects one. Authoring, revise and resync modes play the **`specifier`** role, audit modes the **`auditor`** role: run `dekspec resource role specifier` or `dekspec resource role auditor` at the start of the mode and follow it (a delegated `*-author` agent loads `specifier` itself). See [`_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) §The role each universal mode plays and [`_lib/agent_roles.md`](../_lib/agent_roles.md).

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode** (dispatches a fresh-context `dekspec:mission-author` subagent via the Agent tool per ds-di2).

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Review mode** — `--review` flag, expects a path to an existing Mission file. Skip to **Review Mode**.
- **Audit mode** — `--audit` flag, expects a path to an existing Mission file in any non-terminal status. Skip to **Audit Mode**.
- **Activate mode** — `--activate` flag, expects a path to an existing Mission file in `PROPOSED`. Skip to **Activate Mode**.
- **Complete mode** — `--complete` flag, expects a path to an existing Mission file in `ACTIVE`. Skip to **Complete Mode**.
- **Kill mode** — `--kill` flag, expects a path to an existing Mission file. Skip to **Kill Mode**.
- **Supersede mode** — `--supersede` flag, expects a path to an existing Mission file. Skip to **Supersede Mode**.
- **Approve mode** — `--approve` flag, expects a path to an existing Mission file. Skip to **Approve Mode**.
- **Creation mode** — no flag. Proceed to **Creation Mode (default authoring path)**. **Defaults to provisional** (ADR-030 hard default): with no opt-out the new Mission lands under `dekspec/provisional/` and no canonical `MSN-NNN` id is allocated. Passing **`--canonical`** opts into canonical-direct authoring (lands in `dekspec/missions/`, allocates an `MSN-NNN` id). The routing authority is the `dekspec library author-target --kind MSN [--canonical]` verb — Creation Mode calls it rather than asking the engineer or hardcoding the directory.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag)
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--activate`, `--complete`, `--kill`, `--supersede`

## Interview Rigor (default-on)

This skill **composes the [`interview-me`](../interview-me/SKILL.md) skill** (INT-167 / D13), which ships beside it in this plugin (ADR-064). It does not re-author the interview prose, and there is no `--grill` flag. When the engineer's input is fuzzy or underspecified, invoke it through the Skill tool (`/dekspec:interview-me <MSN-NNN | description>`) so the engineer is interviewed one decision-tree question at a time, with a recommended answer per question, repo-exploration for discoverable answers, glossary + governing ADR/AE citation with conflict-flagging, fuzzy-term sharpening, and scenario-based stress-testing of asserted relationships.

**Trigger (pinned, INT-167 Open Issues):**

- **Auto-engages** in **Creation** (no-flag) mode when the Mission framing is fuzzy/underspecified.
- **Auto-skips** on editorial/trivial passes (`--amend --editorial`-style) — these are not fuzzy-input authoring.
- **Escape:** the `--no-interview` modifier skips the interview on demand even on a fuzzy Creation pass.

At interview end, read the hand-off log `dekspec/.scratch/interview-me/<artifact-id>.md` and fold its resolved decisions into the Mission being authored. `interview-me` never writes the artifact itself — the host skill (this one) folds the decisions in.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-mission"
one_line:   "Author, review, activate, complete, kill, or supersede a Mission"
modes:
  - { flag: "", args: "<description>", description: "Create a new Mission from the engineer's description. Writes the near-immutable section (Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent) up-front. Status: PROPOSED. Adds entry to mission-index.md." }
  - { flag: "--review", args: "<Mission-path>", description: "Revise the live section (Intent queue, Discovered prerequisites, Burndown, Flag transitions, Notes). Refuses to edit near-immutable fields. Used after each child Intent transitions; surfaces anything that drifted into the live section that should be in a near-immutable field instead." }
  - { flag: "--audit", args: "<Mission-path>", description: "Read-only health check. Re-runs every check --activate / --complete would run (T17 completeness, L8 bidirectional Intent linkage, L9 Mission Verification cmd resolves, L11 stale-ACTIVE check), but mutates nothing. Reports findings and recommends the remedial action." }
  - { flag: "--activate", args: "<Mission-path>", description: "Promote PROPOSED → ACTIVE: the engineer authorizes the programme. Refuses unless the near-immutable section is complete (T17) and the First Intent is named. Engineer-only gate." }
  - { flag: "--complete", args: "<Mission-path>", description: "Promote ACTIVE → COMPLETE. Confirms every queued Intent is COMPLETE, the flag (if any) is on and the flag-removal Intent (if any) is COMPLETE, then runs the Mission Verification predicate (scripts/run_verification.py); refuses and stays ACTIVE if it fails. Moves the Mission row from Active queue to Archive in mission-index.md." }
  - { flag: "--kill", args: "<Mission-path>", description: "Mark Mission as KILLED. Requires a written reason (the kill criterion that triggered, or an engineer abandonment note). Records the rollback steps actually executed. Moves to Archive." }
  - { flag: "--supersede", args: "<Mission-path>", description: "Create a successor Mission that supersedes the given one. The successor copies the live Intent queue + carries its own near-immutable section (which the engineer revises). Marks the old Mission as SUPERSEDED." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing a Mission section-by-section. Distinct from --review and from no-flag creation. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-mission stabilize WS-028 attachment processing across the 5 sub-Intents"
  - "/write-mission --review dekspec/missions/MSN-001-ws028-stabilization.md"
  - "/write-mission --activate dekspec/missions/MSN-001-ws028-stabilization.md"
  - "/write-mission --complete dekspec/missions/MSN-001-ws028-stabilization.md"
  - "/write-mission --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: Mission (MSN-NNN)
- **template_path**: `templates/mission-template.md`
- **methodology_section**: §4 Mission of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/missions/MSN-001-constitution-l0.md` (Constitution L0 introduction)
- **required_sections**: near-immutable fields — [Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent]

Skill-specific structural checks to surface as Open Issues: T17 (near-immutable field missing), L8 (Intent queue references nonexistent Intents).

**Skill-unique two-section split:** Mission templates have a near-immutable section (pinned at PROPOSED, edited only with a rationale) and a live section (Intent queue, Discovered prerequisites, Burndown, Flag transitions, Notes). Teaching Mode walks the engineer through the **near-immutable** section only — fields per the manifest above. Briefly explain the live section's purpose but do NOT prompt the engineer to fill it during teaching; it is populated as child Intents land. The Mission is written to disk at PROPOSED status (a Mission has no DRAFT); the engineer activates it with `--activate` when authorizing the programme.

## Creation Mode (default authoring path)

Creation Mode is the substantive-work path that produces a new Mission file. Per the fan-out architectural pattern (bead `ds-di2`, 2026-05-19), this orchestrator does **not** author the Mission inline in the parent session's context. Instead it bundles all required context and dispatches a fresh-context `dekspec:mission-author` subagent via the `Agent` tool, then validates + saves what the subagent returns.

Rationale: context isolation (no parent-session contamination), indirect quality-test of bundled materials (gaps in the bundle surface as subagent failures, not silent quality drift), natural parallelism across Missions, and inheritance of the engineer-selected host model for every subagent.

### Step 1: Decision Gate + Context Bundle (orchestrator, parent context)

#### 1a. Decision Gate — is a Mission required?

A Mission is created when **any** of:

- Work plausibly decomposes into more than one Intent at first sketch (≥ 2 Intents)
- A feature flag will guard partial state during rollout
- Multiple Intents need to share an outcome, an out-of-scope contract, or a kill criterion
- Work spans more than ~1 week of execution
- **Convert-from-oversized entry:** an existing DRAFT Intent whose `--analyze` size assessment exceeded the caps (the P2 "re-split before acceptance" finding — OVERSIZED is no longer a status, ADR-057) has a natural decomposition that is an umbrella over N capability surfaces (CONVERT-TO-MISSION path per `_lib/oversized_splitting.md`). The Mission inherits the over-cap Intent's content; the Intent file is deleted (no SUPERSEDED shell). Recognized when the engineer's description begins with `from-oversized: <INT-NNN-path>` or when `/write-intent --analyze` dispatches the CONVERT-TO-MISSION branch directly.

If **none** of the above hold, refuse with: "Single-Intent work skips the Mission layer. Run `/write-intent <description>` directly. The Mission rigor is overhead for work that fits in one Intent."

#### 1a.0. Provisional-vs-canonical routing — the hard default (ADR-030)

> **Superseded by the hard default (ADR-030).** This section originally hosted an interactive commitment prompt added by **INT-128** (LOCKED 2026-05-30) after the MSN-011 eradication cost case. **INT-133 (ADR-030) replaced that live ask→route prompt with a deterministic hard default**: Creation mode defaults to provisional; `--canonical` is the opt-out. The INT-128 motivation (the MSN-011 eradication cost) still stands — it is now encoded in the default posture instead of a per-run question.

Before dispatching the `mission-author` subagent in §1c, resolve the author target via the single source of truth — **do not ask the engineer, do not hardcode the directory**:

```
dekspec library author-target --kind MSN          # default → provisional
dekspec library author-target --kind MSN --canonical   # opt-out → dekspec/missions/, allocate MSN-NNN
```

Pass `--canonical` iff the engineer passed `--canonical` to this skill. The verb returns JSON with `target_dir` and `allocate_canonical`:

- **Default (no `--canonical`):** `target_dir` under `dekspec/provisional/` and `allocate_canonical=false` — route through the `--provisional` codepath (same as if `--provisional <slug>` had been passed explicitly). Do NOT allocate a canonical `MSN-NNN`. This is the safe posture: `rm -rf dekspec/provisional/<slug>/` is the entire eradication path if the work doesn't graduate, versus the MSN-011 case (12 commits, ~30 minutes, 5 LOCKED-artifact unlock cycles — see `docs/dekspec-operating-guide.md` §Provisional vs. Canonical decision criteria).
- **Opt-out (`--canonical`):** `target_dir` is `dekspec/missions/` and `allocate_canonical=true` — author canonical under `dekspec/missions/MSN-NNN-<slug>.md`, allocating the next-free `MSN-NNN`.

The `T-MISSION-CANONICAL-WITHOUT-CHILD` (P3 advisory) audit rule (registered in `v1.yaml`) backstops this gate: any canonical Mission stale PROPOSED for ≥7 days without a declaring child Intent surfaces in `dekspec doctor` with the recommendation to demote-or-kill.

#### 1a.1. Convert-from-oversized handler (when triggered)

If the trigger is `from-oversized: <INT-NNN-path>`:

1. Read the over-cap Intent file at the given path. Confirm Status is `DRAFT` (an over-cap Intent never leaves DRAFT). Refuse on any other status.
2. **Extract substance** for the Mission's near-immutable section:
   - **Outcome** ← Intent's `Desired Outcome` (or `Mission decomposition plan` opening statement if more apt).
   - **Mission Verification** ← scaffold a predicate covering the Intent's full umbrella surface; the subagent populates `cmd:` entries per the standard pattern.
   - **Out-of-scope** ← Intent's explicit non-goals; otherwise scaffold placeholder.
   - **Flag strategy** ← derived from Intent's `Components affected` + risk; often `none` for design-substrate Missions.
   - **Rollback plan** ← reverse-merge-order child reverts.
   - **Kill criteria** ← scaffold placeholder if not specified.
   - **Autonomy ceiling** ← Intent's `Autonomy`.
   - **First Intent** ← named in the Intent's `Mission decomposition plan` or, lacking that, the highest-priority capability surface.
3. **Scaffold child Intents from the over-cap Intent's decomposition plan.** Read the source Intent's `## Mission decomposition plan` section (or `## Layer impact analysis` if no decomposition plan section exists; or `## Coverage report` per-IU rows as fallback). For each capability surface / child entry named there, scaffold one DRAFT child Intent. Concrete procedure:

   **3a. ID allocation (deterministic, sequential).** Run `python ../_lib/scripts/artifact_ops.py next-id intent` to obtain the next free INT-NNN. Allocate to the first child. Increment by 1 for each subsequent child (the script can be re-run between children since the index is updated as each child file lands; pre-compute the N consecutive IDs in one pass if simpler).

   **3b. Per-child Intent file content.** For each child Intent, write to `dekspec/intents/INT-NNN-<slug>.md` using `dekspec/templates/intent-template.md` as the structural template. Populate the following from the source Intent's content:

   | Section | Source |
   | :--- | :--- |
   | Title | Verb-first phrasing of the §Mission decomposition plan child entry (e.g., "Add the dekspec relink CLI verb..." for Child B of an over-cap Intent whose Child B is "the relink verb implementation") |
   | Status | `DRAFT` |
   | Intent type | Source Intent's `## Intent type` (typically `feature`; override per child if the decomposition plan specifies, e.g., `adr-driven` for ADR-consuming children) |
   | Autonomy | Source Intent's `## Autonomy` (must be ≤ this Mission's `Autonomy ceiling`) |
   | Risk Tier | Inherit from the source Intent unless child entry specifies differently |
   | Branch | `int/INT-NNN-<slug>` |
   | Mission | `MSN-XXX` (the new Mission being authored) |
   | Source | `Scaffolded as child of MSN-XXX from CONVERT-TO-MISSION absorption of over-cap Intent INT-OOO (deleted). Original child entry: <verbatim text of the decomposition-plan row>.` (Substitute INT-OOO with the actual deleted Intent's ID for historical traceability, even though the file is gone.) |
   | Superseded-By | `n/a` |
   | Created / Modified | today's date |
   | Linked Architecture Elements | Subset of source Intent's `## Linked Architecture Elements` that the child entry's scope touches. Read the source Intent's §Mission decomposition plan or §Layer impact analysis for the per-child AE mapping; if absent, default to ALL of the source Intent's Linked AEs and let `--analyze` narrow them. |
   | Motivation | The §Mission decomposition plan's per-child paragraph(s). If the decomposition plan is row-format, expand the row into 1-3 paragraphs covering the child's why + observable-problem statement. Defer measurable targets (move to WS) and decision rationale (move to ADR) per D19/D20. |
   | Desired Outcome | Derived from the §Mission decomposition plan's per-child entry — what is observably true after this child Intent is COMPLETE. |
   | Type-specific block | Populate per the Intent's type (e.g., `adr-driven` → ADR field set to the source Intent's governing ADR; `feature` → no extra block). |
   | Components affected | Subset of source Intent's `## Components affected` that the child entry's scope owns. Use the decomposition plan's per-child globs if present; else default to ALL parent globs and let `--analyze` narrow them. |
   | Verification | Type-default predicate from CLAUDE.md §Verification Predicate Library (the standard 5-cmd block: pytest-full / ruff / dekspec-doctor / bump-version-check / type-specific check). |
   | Scratch-pad sections (Coverage report, Size assessment, Layer impact analysis) | Template-empty shape (populated by `/write-intent --analyze` later). |
   | Open Issues | Carry forward any decomposition-plan-named per-child blocking concerns as DRAFT-source `P2`/`P3` entries. |
   | Amendment Log | Single `Create` row: `Scaffolded as child of MSN-XXX from CONVERT-TO-MISSION absorption of over-cap Intent INT-OOO (deleted) 2026-MM-DD. Original child entry: <verbatim>.` |

   **3c. Per-child index update.** Append a row to `dekspec/intent-index.md` Active queue for each scaffolded child: `| [INT-NNN](intents/INT-NNN-<slug>.md) | <Title> | <Type> | <Autonomy> | DRAFT | <Linked AEs> | <created> | <modified> |`.

   **3d. Per-child Mission queue row.** Append a row to the new Mission's `### Intent queue` (live section) for each scaffolded child: `| [INT-NNN](../intents/INT-NNN-<slug>.md) | <Title> | <Type> | DRAFT | Scaffolded from CONVERT-TO-MISSION of INT-OOO. <one-line focus statement>. |`.

   **3e. Branch creation (deferred).** Do NOT create branches or worktrees at scaffold time. The delivery worktree is created when the work starts (`/use-worktrees`; one PR = one worktree = one delivery unit, ADR-048 / ADR-058).

4. **Delete the source Intent file** post-extraction (`git rm <path>`). Remove its row from `dekspec/intent-index.md` (it was Active queue; should not enter Archive — never had a successor and never shipped).
5. **No SUPERSEDED shell.** The Intent's substance is absorbed; the artifact ceases to exist.
6. Update any cross-references to the deleted Intent in surviving artifacts where appropriate — replace `INT-OOO §section` citations with `MSN-XXX §section`; drop bare INT references where the content is fully absorbed.
7. Run `dekspec relink` to refresh derived AE backlinks (each new child Intent's Linked AEs contributes a backlink entry to the AE's `Related Intents` list).
8. **Report back to the engineer.** Surface a structured summary card:

   ```
   ================================================================================
   ✓ CONVERT-TO-MISSION COMPLETE
   ================================================================================
   New Mission: [MSN-XXX](file:///...) — <Mission Title> [PROPOSED]
   Absorbed substance from: INT-OOO (deleted)

   Scaffolded child Intents (DRAFT):
   1.  [INT-NNN](file:///...) — <Child A Title>
       Components: <globs> | AEs: <list>
   2.  [INT-MMM](file:///...) — <Child B Title>
       Components: <globs> | AEs: <list>
   3.  [INT-PPP](file:///...) — <Child C Title>
       Components: <globs> | AEs: <list>

   Next steps:
   *   Run /write-intent --analyze on each child Intent to populate Coverage Report
       + Size Assessment + Layer Impact Analysis, and promote DRAFT → PROPOSED.
   *   Run /write-mission --activate <MSN-XXX-path> once the engineer authorizes the programme.
   ================================================================================
   ```

#### 1b. Parse engineer input

Engineer's description: `$ARGUMENTS`.

Optional structured cues parsed from `$ARGUMENTS`:

- `flag: <flag-name>` or `flag: none` — feature flag for the Mission
- `autonomy: <manual|low|medium|high>` — Autonomy ceiling (default: `medium`, ADR-059; a lower ceiling restricts every Intent under the Mission, so record the decision it reserves)
- `owner: <name>` — owner identifier

#### 1c. Bundle context for the subagent

The subagent runs in a fresh context with **no access to this session's history**. Every input it needs must be in the prompt. Resolve the following before dispatch:

1. **Template path** — `dekspec/templates/mission-template.md` (must exist; halt with "vendor dekspec first" if absent).
2. **System Vision path** — `dekspec/system-vision.md` (the L0 root the Mission ultimately derives from).
3. **Related Mission paths** — scan `dekspec/missions/` and `dekspec/mission-index.md`:
   - The parent Mission (if `$ARGUMENTS` names one) and any sibling Missions sharing the parent.
   - The 1–2 most recently `ACTIVE` Missions as style/shape exemplars.
4. **Draft Intent queue paths** — any Intent files in `dekspec/intents/` whose `Mission:` field is unset but which `$ARGUMENTS` plausibly groups into this Mission, plus any explicit Intent IDs the engineer named. The subagent uses these to populate the live-section Intent queue and to ground the First Intent field.
5. **Constraints** — from CLAUDE.md, the Constitution (`dekspec/constitution.md` if present), `dekspec/architecture-elements-index.md` (AE corpus grounds what Mission Verification can assert), and `dekspec/dekspec-operating-guide.md` §Missions (lifecycle, Autonomy ceiling semantics, Mission-vs-Intent rigor distinction). Also include CLAUDE.md §Verification Predicate Library — Mission Verification is stronger than Intent Verification (behavioral assertion across the integrated system, not a per-component test sweep).
6. **Engineer guidance** — the raw `$ARGUMENTS` text verbatim; parsed structured cues go in separate fields.
7. **Next MSN-NNN** — run `python ../_lib/scripts/artifact_ops.py next-id mission` (surface stderr on non-zero exit).
8. **Expected output path** — `dekspec/missions/MSN-NNN-<slug>.md` (slug derived from the Outcome, not from team / project name).
9. **Validation command** — `dekspec validate dekspec/missions/MSN-NNN-<slug>.md`.

### Step 2: Dispatch via the Agent tool

Invoke the `Agent` tool with:

- `subagent_type`: `dekspec:mission-author`
- `description`: short label, e.g. `Author MSN-NNN`
- `prompt`: a single self-contained string. **The subagent will see only this prompt — not the parent conversation.** It MUST include, with absolute paths:

  ```
  TASK: Author a new DekSpec Mission at <expected-output-path> in Status PROPOSED.

  TEMPLATE (follow exactly):
    /home/dfxop/projects/dekspec/dekspec/templates/mission-template.md

  SYSTEM VISION (the L0 root this Mission derives from):
    /home/dfxop/projects/dekspec/dekspec/system-vision.md

  RELATED MISSIONS (parent + siblings + recent ACTIVE exemplars):
    <absolute paths, one per line>

  DRAFT INTENT QUEUE (Intents that plausibly belong to this Mission;
  use them to populate the live-section Intent queue and to ground
  the near-immutable First Intent field):
    <absolute paths, one per line, or "none">

  ENGINEER GUIDANCE (verbatim $ARGUMENTS + parsed structured cues):
    <description>
    flag: <flag-name | none>
    autonomy: <manual | low | medium | high>
    owner: <name>

  CONSTRAINTS:
    - Methodology: /home/dfxop/projects/dekspec/dekspec/dekspec-operating-guide.md
      §Missions (lifecycle, Autonomy ceiling semantics, Mission ≠ Intent rigor).
    - Verification predicate shape: per CLAUDE.md §Verification Predicate Library.
      Mission Verification is a behavioral assertion across the integrated
      system, not a per-component test sweep. At least one named cmd entry
      is required (audit-v2 T17-MSN-VERIFICATION).
    - AE corpus (what is verifiable):
      /home/dfxop/projects/dekspec/dekspec/architecture-elements-index.md
    - Constitution (if present): /home/dfxop/projects/dekspec/dekspec/constitution.md
    - Fill EVERY near-immutable field (Outcome, Mission Verification,
      Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy
      ceiling, First Intent). No placeholders. If the engineer guidance
      under-specifies a field, return an explicit "INSUFFICIENT_CONTEXT:
      <field> — <what's missing>" line instead of guessing.
    - Rollback plan (Mission IR v0.2.0, ds-zuy): `**Trigger:**` prose +
      fenced yaml `steps:` list of `{name, cmd}` entries parallel to
      Mission Verification. Use `_legacy_prose` sentinel +
      `echo SKIP_LEGACY_ROLLBACK` cmd only when rollback is intentionally
      human-attended.
    - Kill criteria (Mission IR v0.2.0, ds-zuy): fenced yaml list of
      `{name, cmd}` entries; each cmd exits non-zero when the kill
      condition is true. Use `_legacy_prose_N` sentinel +
      `echo SKIP_LEGACY_KILL` cmd only for intentionally subjective
      criteria.
    - Live section (Intent queue, Discovered prerequisites, Burndown,
      Flag transitions, Notes) is initialized empty / from the draft
      Intent queue; it is revised post-creation via `/write-mission --review`.
    - Status MUST be PROPOSED on first write.

  EXPECTED OUTPUT:
    Write the Mission file to <expected-output-path>.
    Do NOT update dekspec/mission-index.md — the orchestrator handles
    indexing after validation passes.
    Return a one-paragraph summary of the Outcome + the slug used + any
    INSUFFICIENT_CONTEXT lines encountered.

  VALIDATION (the orchestrator will run this after you return):
    dekspec validate <expected-output-path>
  ```

### Step 3: Validate + index + report (orchestrator, parent context)

When the subagent returns:

1. **Validate.** Validation contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md). Run `dekspec validate --kind mission dekspec/missions/MSN-NNN-<slug>.md`; on non-zero exit, surface verbatim and stop — do not silently retry. Mission-specific audit gate: this skill's §Audit Mode (read-only health check, see below).
2. **Index.** Add a row to `dekspec/mission-index.md` Active queue for the new Mission.
3. **Report.** Tell the engineer: the Mission is `PROPOSED` at the saved path; run `/write-mission --activate` to authorize it (`PROPOSED → ACTIVE`), then author the First Intent via `/write-intent`. Surface any `INSUFFICIENT_CONTEXT:` lines the subagent returned so the engineer can fill the gap via `--review` before activation.

**End of Creation Mode.**

## Review Mode

Revise the live section after each child Intent transitions. Refuses to edit near-immutable fields — those require `--supersede`.

### Steps

1. Read the Mission file. Refuse if Status is terminal (`COMPLETE`, `KILLED`, `SUPERSEDED`).
2. Walk the live section interactively:
   - **Intent queue:** add new Intents, update statuses, mark sketches as drafted.
   - **Discovered prerequisites:** any new gaps surfaced by child Intent `--analyze` runs.
   - **Burndown:** recompute COMPLETE / Estimated total / Sketches.
   - **Flag transitions:** record any flag flips since last review.
   - **Notes:** working notes, calibration findings.
3. If the engineer attempts to edit a near-immutable field, surface: "This is a near-immutable field. Routine edits live in the live section; substantive changes require `/write-mission --supersede` (creates a successor Mission)."
4. Save with updated Modified date.

**End of Review Mode.**

## Audit Mode (read-only health check)

_Plays the **`auditor`** role — run `dekspec resource role auditor` first and follow it: deterministic `dekspec validate` / `dekspec audit` output is primary evidence; report findings, change nothing._

Reads `<Mission-path>`. Re-runs every check the lifecycle modes enforce, but mutates nothing — no Status transitions, no Intent-queue edits, no Amendment Log entries.

### Step 1: Validate

1. File exists. Audit runs in any status except `SUPERSEDED` (the successor Mission is what should be audited).

### Step 2: Run the full check battery

The mechanical checks — **L8** (Mission↔Intent bidirectional linkage), **L9**
(Mission Verification cmd-resolve), **L11** (stale-ACTIVE ≥90 days) — are
scripted. Run `scripts/mission_audit.py <Mission-path>` (in this skill's
folder); surface its stderr on a non-zero exit (code 2 = at least one P1
finding). It emits JSON findings grouped by severity (P1 / P2 / P3) — the AI
presents them, judges them, and folds them into the Step 3 report alongside the
non-mechanical checks below. Then run each check in this order:

1. **Schema validation** — parse via `dekspec.constraint_compiler.parse_mission`. Surface parse warnings as findings.
2. **T17 completeness** — T17-MSN-VERIFICATION (`mission_verification` has ≥1 cmd entry), T17-MSN-OUTCOME (`Outcome` paragraph populated), T17-MSN-ROLLBACK (`Rollback plan` paragraph populated). Skipped for COMPLETE / KILLED Missions.
3. **L8 bidirectional Intent linkage** — from `mission_audit.py` (`LINK-MSN-INT-EXISTS` + `LINK-MSN-INT-MIRROR`). The autonomy-ceiling check (`LINK-INT-AUTONOMY-EXCEEDS`: each child Intent's `Autonomy:` ≤ this Mission's `Autonomy ceiling:`) is an AI judgment step — read each child Intent and compare.
4. **L9 Mission Verification cmd-resolve** — from `mission_audit.py` (`LINK-MSN-CMD-RESOLVE`; resolvability only — pytest via PATH, `scripts/*.sh` exists+executable, other tokens via `which`; no execution).
5. **L11 stale-ACTIVE** — from `mission_audit.py` (`LINK-MSN-STALE`; surfaced as P3 when Status is `ACTIVE` and `modified`/`created` is >90 days old) with recommendation to record progress + bump Modified, or run `--complete` / `--kill`.
6. **Status-coherence** — flag any state-machine inconsistency: e.g., status `ACTIVE` while every queued Intent is already `COMPLETE` (ready for `--complete`; `T-STATUS-LAG`); status `COMPLETE` while a queued Intent is not; status `COMPLETE` but the row is still in the Active queue of `mission-index.md`.

### Step 3: Report

Print a findings table grouped by severity (CRITICAL / IMPORTANT / MINOR), each row:

```
[severity] <rule code> <one-sentence finding>
  Fix: <recommended remedial action>
```

Examples:
- `[CRITICAL] LINK-INT-AUTONOMY-EXCEEDS: INT-007.autonomy=high exceeds Mission.autonomy_ceiling=medium. Fix: --review the Intent and lower its Autonomy, or --supersede this Mission with a higher ceiling.`
- `[IMPORTANT] T17-MSN-VERIFICATION: no Mission Verification cmd entries. Fix: edit the near-immutable section to add at least one named cmd check, or --supersede with a corrected Mission.`
- `[MINOR] LINK-MSN-STALE: ACTIVE for 127 days since last modification. Fix: --review to record progress + bump Modified, or --complete / --kill to advance.`

Print exit code `0` if no CRITICAL findings, `1` if any CRITICAL.

### Step 4: Recommend next mode

End with a one-line recommendation:

- All clean → "No findings. The Mission is well-formed at its current status."
- Findings present → "Run `/write-mission --review <path>` for editorial fixes, or `/write-mission --supersede <path>` if a near-immutable field needs to change."

No file is written. No Amendment Log entry is added. Audit is strictly read-only.

**End of Audit Mode.**

## Provisional Promotion Gate (INT-082)

Before any Status transition out of `PROPOSED`, check whether the Mission has a corresponding provisional incubation folder under `dekspec/provisional/`. If yes, render the promotion plan and require explicit engineer confirmation — the gate that turns ACTIVE / COMPLETE from incidental status walks into the deliberate "I commit to the canonical replacement" decision.

This gate fires from **Activate Mode** when transitioning a Mission that was provisional-staged. It also fires from **Complete Mode** if additional provisional artifacts were authored mid-Mission and have not yet promoted.

Steps:

1. **Detect incubation.** Look for a folder under `dekspec/provisional/` whose name matches this Mission's slug, or whose contents include a file referencing this Mission's ID (e.g., `**Mission:** MSN-NNN` or `replaces: MSN-NNN`).
2. **Plan the promotion by hand.** Walk the incubation folder's files; for each, identify whether it maps to a `replaces: <KIND-NNN>` REPLACE-mode row (preserve canonical ID, `git mv` into canonical path) or a NEW-mode row (allocate the next-free canonical ID). See [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow) for the renumber + `git mv` recipe. (The previous dry-run CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` — the hand-promote workflow is now canonical.)
3. **Render the plan** to the engineer as a scannable table separating REPLACE-mode rows from NEW-mode rows.
4. **Request explicit confirmation.** Ask: "Promotion of <N> provisional artifact(s) will accompany this transition. Confirm? [yes/no/show-diff <file>]". `yes` (or `confirm`) proceeds to the canonical Status transition. `no` aborts — the Mission stays at its current Status and no canonical changes happen.
5. **On confirmation**, execute the hand-promote workflow (renumber + `git mv` per Step 2's plan) atomically with the Status transition.

If no incubation folder is detected, proceed directly to the Status transition (this is the common case for canonical-only Missions).

## Activate Mode (PROPOSED → ACTIVE)

Promotes a Mission from `PROPOSED` to `ACTIVE` — the engineer's decision to authorize the programme (ADR-057: a status records a decision, not activity). Work under the Mission proceeds after activation; its progress is read from the child Intents and their IBs, never mirrored here. Before the transition, run the **Provisional Promotion Gate** above if a corresponding `dekspec/provisional/<slug>/` folder exists.

### Steps

1. Read the Mission file. Refuse if Status is not `PROPOSED`.
2. Run **Audit Mode** Step 2 checks 1–2 (schema + T17 completeness). Refuse on any near-immutable field that is missing or still a placeholder, and when `First Intent` is unnamed.
3. Confirm with the engineer that they authorize the programme (engineer-only gate — an agent never self-activates).
4. Flip Status to `ACTIVE`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Mission-path> --from PROPOSED --to ACTIVE --note "Activated: programme authorized." --engineer <name>` (surface stderr on non-zero exit and STOP).

**End of Activate Mode.**

## Complete Mode (ACTIVE → COMPLETE)

Promotes a Mission from `ACTIVE` to `COMPLETE` in one step: the verification runs inside this mode, so there is no intermediate status (ADR-057 retired `COMPLETING`). The promotion gate: every child Intent in the Intent queue is `COMPLETE`, the flag (if any) is on, and the Mission Verification predicate passes on current content. Run the **Provisional Promotion Gate** above first if any in-flight provisional artifact still references this Mission.

### Steps

1. Read the Mission file. Refuse if Status is not `ACTIVE`.
2. Read the Intent queue. Confirm every entry's Status is `COMPLETE` (an Intent completes through `dekspec intent complete` once its IBs completed through `dekspec ib complete`). If any is not, refuse and name the open Intents.
3. If `Flag strategy.Flag name` is non-`none`, confirm the flag is on (typically by checking a config-management WS or asking the engineer).
4. If `Flag strategy.Removal plan` names a flag-removal Intent, confirm that Intent is COMPLETE.
5. Run the Mission Verification predicate: `python scripts/run_verification.py <Mission-path>` (in this skill's folder). It executes each `cmd:` in the Mission Verification yaml block in order, fast-fails on the first non-zero exit, and emits a JSON record. On a non-zero exit (code 2 = a check failed) surface the `failing` record (check, cmd, exit code, captured stdout/stderr tail) and STOP — Status stays `ACTIVE`; nothing is written.
6. If the script exits 0 (`passed: true`), transition Status to `COMPLETE` — run `python ../_lib/scripts/artifact_ops.py transition <Mission-path> --from ACTIVE --to COMPLETE --note "All Mission Verification checks green; Mission complete." --engineer <name>` (surface stderr on non-zero exit and STOP).
7. Move the Mission's row from `mission-index.md` Active queue to Archive.

**End of Complete Mode.**

## Kill Mode (any non-terminal → KILLED)

Marks a Mission as `KILLED`. Used when a kill criterion has triggered or the engineer has decided to abandon.

### Steps

1. Read the Mission file. Refuse if Status is terminal (`COMPLETE`, `KILLED`, `SUPERSEDED`).
2. Ask for the kill reason — either a kill-criterion identifier (e.g., "kill-criterion-2: NFR latency regression > 10%") or a written abandonment note.
3. Ask for the rollback action taken — confirms the rollback plan was executed (or that the Mission state was such that no rollback was needed).
4. Flip Status to `KILLED` and append the Amendment Log row recording the kill reason + rollback action — run `python ../_lib/scripts/artifact_ops.py transition <Mission-path> --from <current-status> --to KILLED --note "<kill reason; rollback action taken>" --engineer <name>` (the `--from` is the Mission's current non-terminal status; surface stderr on non-zero exit and STOP). The kill reason / rollback wording is engineer-supplied AI judgment.
5. Move the Mission row from `mission-index.md` Active queue to Archive.

**End of Kill Mode.**

## Supersede Mode (any non-terminal → SUPERSEDED)

Creates a successor Mission. Used when a near-immutable field needs substantive change — Outcome shifted, Mission Verification needs re-shaping, kill criteria proved wrong.

### Steps

1. Read the source Mission. Refuse if Status is terminal.
2. Determine the successor's MSN-NNN (next available number).
3. Copy the source Mission's live Intent queue into a new file at `dekspec/missions/MSN-NNN-<successor-slug>.md`.
4. Walk the engineer through writing the successor's near-immutable section — what's changing, what's preserved.
5. Set successor Status to `PROPOSED`.
6. Set source Status to `SUPERSEDED`. Append Amendment Log entry on source: `Superseded by MSN-NNN — <reason>`.
7. Set successor's `Supersedes:` field (added near the top of the successor file): `MSN-NNN`.
8. Update `dekspec/mission-index.md` — move source row from Active to Archive (status SUPERSEDED), add successor row to Active.

**End of Supersede Mode.**

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/missions/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Mission depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `MSN-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional MSN <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/MSN-provisional-<title-slug>.md` (the CLI prints the path).
4. **Populate the skeleton with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here (Motivation, Linked AEs, Components affected, Verification, etc.). The PROVISIONAL banner at the top stays.
5. **Reject `--activate` / `--complete`** in combination with `--provisional`. Lifecycle transitions need linkage-walker visibility that provisional artifacts deliberately lack; they run on the canonical file after the hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).
6. **`--review` and `--audit`** remain available in provisional mode — they operate on the provisional file's content without requiring canonical-graph visibility.
7. Closing step: surface to the engineer the path of the provisional file, the branch (if created), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

### Cross-references

- `INT-079` — provisional folder substrate (parser-ignore, doctor advisory).
- `INT-082` — copy-on-write spec staging (`replaces:` frontmatter, sibling-collision audit).
- `INT-083` — atomic promotion (CLI verb retired 2026-05-25; the hand-promote workflow is canonical — see `_lib/cli_verbs.md`).
- `INT-084` — `dekspec library new-provisional` scaffold + auto-branch.

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** kind-dir — canonical artifacts under `dekspec/<kind-dir>/`.

## Rules

- **Files canonical (Decision D2 / v5 §21).** Missions live as markdown files at `dekspec/missions/MSN-NNN-<slug>.md`. External trackers may seed and (Phase 3+) mirror, but the file is canonical.
- **Single-Intent work skips Missions.** A bug fix, a small feature, an NFR pass that fits in one Intent — none of these require a Mission. Lazy Mission creation is treated as Mission-debt (Decision #20). Refuse Creation Mode if the work fits one Intent.
- **CONVERT-TO-MISSION absorbs over-cap Intents (no SUPERSEDED shell).** When a DRAFT Intent whose analysis exceeded the size caps has a natural decomposition that is an umbrella over N capability surfaces, Creation Mode's `from-oversized: <INT-NNN-path>` Decision Gate entry triggers Step 1a.1: extract the Intent's substance (Outcome, Verification scaffold, Out-of-scope, Flag strategy, Rollback, Kill criteria, Autonomy ceiling, First Intent) into this Mission's near-immutable section, scaffold child Intents for each capability surface, then **delete the source Intent file** and remove its row from `dekspec/intent-index.md` — it goes neither to the Active queue nor to Archive (never had a successor; never shipped). No SUPERSEDED status is set. The shared partition-shape decision tree lives in [`_lib/oversized_splitting.md`](../_lib/oversized_splitting.md); `/write-intent --analyze` dispatches the CONVERT branch when an Intent's `Mission decomposition plan` names ≥3 children, and `/dekspec:spec-intent` surfaces both PEEL-OFF (for natural-core-slice cases) and CONVERT-TO-MISSION (for umbrella cases) to the engineer in Step 3.
- **Near-immutable section is rigorous up-front, supersede-only after.** Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent — all written before any Intent leaves DRAFT. Routine edits to these fields are forbidden; substantive changes go through `--supersede`.
- **Live section is revised continuously.** Intent queue, prerequisites, burndown, flag transitions, notes — all updated via `--review` after every child Intent transitions.
- **Autonomy ceiling caps every child Intent.** When `/write-intent --analyze` or `--accept` runs against an Intent whose `Mission:` field references this Mission, audit-v2 L8 enforces `Intent.Autonomy ≤ Mission.Autonomy_ceiling`.
- **Serialization within a Mission (Decision #9, advisory per ADR-016).** Child Intents execute serially — one Intent reaching COMPLETE before the next leaves DRAFT. The autonomous orchestration brain that may eventually parallelize across Missions (never within a Mission) lives in `dekfactory`, not here — see `docs/architecture.md` §What does NOT live here.
- **Mission Verification is stronger than per-Intent Verification.** Per-Intent Verification proves "this change works"; Mission Verification proves "the integrated system delivers the outcome." Behavioral assertion, not a test-suite sweep.
- **Log corrections.** When this skill corrects a domain misinterpretation in the engineer's input, invoke `/write-corrections --log` with the correction details before proceeding.

### Worked Example 1 — Workflow-shaped

Pattern: "An engineer can produce artifact X via path Y in under Z minutes, end-to-end, without engineer intervention beyond the prompts the workflow itself surfaces."

Concrete Mission Verification predicate (as authored in the near-immutable section):

> An engineer can take a brownfield repository with no DekSpec artifacts and produce a LOCKED System Vision + 3 ACCEPTED Architecture Elements via the `/dekspec:ingest-docs` + `/dekspec:write-sv` + `/dekspec:write-ae` flow in under 90 minutes, with no engineer input beyond the prompts those skills themselves surface.

- **What this is NOT:** a pytest assertion that the three skills each return exit 0 — that is per-component testing, not Mission-level behavioral verification. The Mission-level assertion is about end-to-end engineer-observable outcome (artifacts on disk, in the correct status, inside a time budget), not about whether each skill's unit tests pass.

### Worked Example 2 — Safety-shaped

Pattern: "The system declines to do W when triggered by V, surfacing why."

Concrete Mission Verification predicate (as authored in the near-immutable section):

> When an engineer runs `dekspec intent complete` on an Intent whose child Implementation Briefs are not all COMPLETE, the command REFUSES to complete it and names the incomplete IBs in the surfaced refusal message.

- **What this is NOT:** a pytest assertion that `intent_evaluate()` returns a failing gate object — that is per-component testing, not Mission-level behavioral verification. The Mission-level assertion is about engineer-visible refusal behavior under the trigger condition (decline + name the blocker), not about an internal exception type.

## Output

- `dekspec/missions/MSN-NNN-<slug>.md` lifecycle transitions:
  - Creation: → PROPOSED
  - `--activate`: PROPOSED → ACTIVE
  - `--review`: live section revised (no status change)
  - `--complete`: ACTIVE → COMPLETE (verification runs inside the mode)
  - `--kill`: any non-terminal → KILLED
  - `--supersede`: any non-terminal → SUPERSEDED + new successor at MSN-NNN+1 in PROPOSED
- Updated `dekspec/mission-index.md` per state transition (Active queue ↔ Archive)
- Amendment Log entries on Activate, Review (substantive only), Complete, Kill, Supersede

## Approve Mode

`--approve` records a peer-review approval signature on a Mission under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the Mission's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <Mission-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACTIVE`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the Mission may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Common Pitfalls

- Don't author a Mission for work that fits one Intent — refuse Creation Mode and route to `/write-intent` directly; lazy Mission creation is Mission-debt (Decision #20).
- Don't write a Mission Verification predicate as "each child Intent's tests pass" or "pytest exits 0" — that is per-component testing; assert the integrated, engineer-observable outcome instead (see Worked Examples 1 & 2).
- Don't edit a near-immutable field (Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent) via `--review` — route substantive changes through `--supersede`; `--review` touches the live section only.
- Don't `--activate` with an incomplete near-immutable section, or `--complete` before every queued Intent is COMPLETE and the Mission Verification passes — the gates refuse, and forcing the status by hand leaves the Mission state-incoherent (L8 / T-STATUS-LAG findings).
- Don't reach for `--canonical` when the First Intent body isn't authored this session — Creation mode now **defaults provisional** (ADR-030 hard default, §1a.0); pass `--canonical` only for a same-session canonical landing. Canonical-without-child eradication cost is real (MSN-011 case, `T-MISSION-CANONICAL-WITHOUT-CHILD`).
- Don't leave a SUPERSEDED shell when absorbing an over-cap Intent via CONVERT-TO-MISSION — `git rm` the source Intent and drop its index row (neither Active nor Archive).

## Verification Checklist

- [ ] Decision Gate cleared: work satisfies ≥1 Mission trigger (≥2 Intents / flag / shared outcome-or-kill-criterion / ~1-week span); single-Intent work was refused.
- [ ] Provisional-vs-canonical routing went through `dekspec library author-target --kind MSN` (§1a.0 hard default) — provisional unless `--canonical` was explicitly passed.
- [ ] Every near-immutable field is populated with no placeholders and no unresolved `INSUFFICIENT_CONTEXT:` lines.
- [ ] Mission Verification has ≥1 named `cmd:` entry asserting an integrated-system behavior (not a per-component pytest sweep); Rollback plan and Kill criteria use yaml `{name, cmd}` shape or an explicit `_legacy_*` sentinel.
- [ ] Status is correct for the mode run (PROPOSED on creation; the exact target status for each lifecycle transition) and `dekspec/mission-index.md` Active↔Archive placement matches.
- [ ] `dekspec validate --kind mission <path>` exited 0 and any CONVERT-scaffolded child Intents landed in `dekspec/intents/` + `dekspec/intent-index.md`.
- [ ] `dekspec relink` was run as the final action and reported clean.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise a Mission — Creation, `--activate`, `--review`, `--complete`, `--kill`, `--supersede`). After the artifact file is saved and any index update is done, run:

```
dekspec relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
