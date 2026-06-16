---
name: orchestrate-intent
description: Guided, interactive lifecycle walker for Intents (INT-NNN). Drives an Intent from its current status to LOCKED one transition at a time, asking the engineer to confirm each step ([accept] / [decompose] / [lock] / etc.). Engineer-in-the-loop by default; an opt-in `--auto` mode walks the same lifecycle without prompts, refusing on first unmet pre-condition per ADR-021. Orchestrates the surrounding artifacts (AE/WS/IC/IB) and post-merge cleanup as it walks.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help | --teaching | --auto | --status | --verify] [description or path/ID of Intent]
---

> **Scope of this skill.** A guided, interactive lifecycle walker for an Intent (`INT-NNN`). The skill drives transitions from `TODO`/`DRAFT` all the way to `LOCKED` one step at a time, asking the engineer to confirm each transition (`[accept]` / `[decompose]` / `[lock]` / etc.). Along the way it coordinates the creation and status updates of all downstream spec artifacts (Architecture Elements, Working Specs, Interface Contracts, Implementation Briefs), generates scannable "What & Why" summary cards, hosts architectural interviews, and propagates final locks. **Engineer-in-the-loop by default.** An opt-in `--auto` flag walks the same lifecycle without per-step prompts, refusing on the first unmet pre-condition; see [Auto Mode](#auto-mode---auto) below and [ADR-021](../../../../dekspec/adrs/ADR-021-orchestrate-intent-auto-safety-contract.md) for the safety contract.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode.

## Mode Detection

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Auto mode** — `--auto` flag. Skip to **Auto Mode (`--auto`)**. Walks PROPOSED → ACCEPTED → DECOMPOSE → IMPLEMENTING → TESTPASS → LOCK without engineer prompts; refuses on first unmet pre-condition; never unlocks; never bypasses `--testpass`. See [ADR-021](../../../../dekspec/adrs/ADR-021-orchestrate-intent-auto-safety-contract.md).
- **Status mode** — `--status` flag. Skip to **Status Mode (`--status`)**. Read-only: report the target's current status + list every downstream child spec. Mutates nothing.
- **Verify mode** — `--verify` flag. Skip to **Verify Mode (`--verify`)**. Read-only: assert every downstream child spec sits in a terminal status (`LOCKED`/`ACCEPTED`) post-merge. Mutates nothing.
- **Orchestrate mode** — default mode (no recognized flag; an ID/path with no flag enters here). Proceed to **Orchestrate Mode**.

> [!IMPORTANT]
> `--status` and `--verify` are **read-only** and MUST short-circuit here *before* Orchestrate Mode's catch-all. An ID/path alone (no flag) is the only thing that enters the stateful Orchestrate walk — a recognized flag always wins. Never start the interactive lifecycle walk for a `--status`/`--verify` invocation.

---

## Orchestrate Mode

### Step 1: Target Identification & State Detection

Identify the target Intent passed in `$ARGUMENTS` — **canonical or provisional** (ds-jtfn). Per the provisional-first default (INT-133) most freshly-authored Intents start in a provisional incubation (`dekspec/provisional/<slug>/`, no canonical `INT-NNN` allocated yet); the conductor drives the WHOLE walk, including the provisional→canonical promotion.

1. **Resolve the target** with the shared resolver, which accepts a canonical `INT-NNN`, a canonical/provisional Intent path, or a provisional incubation slug:
   ```
   python ../_lib/scripts/resolve_intent_target.py "<arg-from-$ARGUMENTS>"
   ```
   It emits JSON `{kind, path, intent_id, status, is_provisional}`. On exit 1 (unresolved / ambiguous incubation), surface its stderr and STOP — for an ambiguous multi-Intent incubation, ask the engineer for the explicit Intent file path.
2. Read the resolved file's status (the resolver's `status`, or re-parse `## Status`) and the linked AEs / WSes / ICs / IBs from `## Linked Architecture Elements` + `## Layer impact analysis`.
3. **If `is_provisional`** — note that the canonical `INT-NNN` is **not allocated yet**; it is assigned at the accept gate's INT-082 Provisional Promotion step. The walk is unchanged otherwise: `analyze` (→ PROPOSED) → `accept` (which promotes the incubation to canonical via the hand-promote / `git mv`, atomically with PROPOSED→ACCEPTED) → `decompose` → … → LOCK. No separate promotion gate exists — promotion rides the existing accept gate, which `--auto` already governs (`analyze-complete` then `accept-clean`, ADR-021).

Present a premium state-detection overview card to the engineer:
```markdown
================================================================================
🚀 DEKSPEC INTENT LIFECYCLE ORCHESTRATOR
================================================================================
Intent ID:   [INT-NNN](file:///...)   (or: PROVISIONAL — canonical id allocated at accept)
Title:       <Intent Title>
Branch:      <Target Branch>
Current Status:  [STATUS]
Incubation:  <none (canonical) | dekspec/provisional/<slug>/ — promotes at accept>
================================================================================
```

When the target is provisional, pass the resolved provisional **path** (not a not-yet-existing `INT-NNN`) to the dispatched phase-executor in Gate 1 — `/dekspec:spec-intent <provisional-path>`. The executor's `--analyze` operates on the provisional content; its `--accept` runs the INT-082 promotion. From the post-promotion canonical artifact onward the walk is identical to the canonical-entry case.

---

### Step 2: The Conductor Loop (phase-executor dispatch)

`orchestrate-intent` is a **thin conductor**: at each lifecycle gate it **delegates** the phase to a fresh-context, independently-launchable phase-executor and owns only the sequencing plus the final lock/propagation. It carries **no inline specification-driving body** — the analyze / accept / decompose work now lives in `/dekspec:spec-intent`. Delegation (not absorption) is deliberate: the coding executor and the review pipeline depend on context isolation (ADR-026 solver-cannot-verify-self), which an inline conductor body would defeat.

Engineer-in-the-loop by default (confirm each gate); `--auto` walks the same delegated sequence without prompts (see Auto Mode). Based on the detected status, dispatch the corresponding executor.

---

#### Gate 1 — Specification → dispatch `/dekspec:spec-intent`

> [!NOTE]
> Covers `TODO` / `DRAFT` / `OVERSIZED` / `PROPOSED` / `ACCEPTED` → `IMPLEMENTING`.

1. Prompt the engineer:
   > "Drive this Intent through specification to ready-for-coding?
   > *   **[spec]** Run the specification phase-executor.
   > *   **[skip]** Manage it manually."
2. **Action** — on `spec`, dispatch:
   ```
   /dekspec:spec-intent <INT-NNN>
   ```
   The executor runs analyze → (engineer-gated) accept → decompose → drive-child-specs and the architectural-interview prompts, surfaces `OVERSIZED` into the split flow (`_lib/oversized_splitting.md`, ADR-028 PEEL-OFF default), and leaves the parent Intent at `IMPLEMENTING` with its child AE/WS/IC/IB at `ACCEPTED`/`LOCKED`. The conductor does **not** run these transitions itself; `--accept` stays engineer-gated inside the executor.

---

#### Gate 2 — Implement → dispatch `/exec-coding-session`

> [!NOTE]
> Status `IMPLEMENTING`. Optionally review the specs before dispatching construction.

Render a scannable pre-implementation summary the engineer can confirm at a glance:

```markdown
### 📝 Pre-Implementation Artifact Change Summary

| Artifact ID & Path | Status | Impact / Role | What Changed | Why / Rationale |
| :--- | :--- | :--- | :--- | :--- |
| [AE-NNN](file:///...) | `ACCEPTED` | AE Revision | *e.g., Extended core boundary for ...* | *e.g., Accommodate new API layout.* |
| [WS-NNN](file:///...) | `ACCEPTED` | Working Spec | *e.g., Added failure behavior for ...* | *e.g., Prevent silent device crashes.* |
| [IC-NNN](file:///...) | `ACCEPTED` | New Boundary | *e.g., Created typed endpoint for ...* | *e.g., Secure cross-component pipeline.* |
```

Then prompt:
> "How would you like to proceed?
> *   **[implement]** Dispatch the coding session.
> *   **[interview]** Chat with me (System Architect) about the specs, tradeoffs, or design decisions.
> *   **[review]** Inspect the raw artifact files directly."

* **[review]** — provide file links and print content on request.
* **[interview]** — act as Lead System Architect; answer questions on tradeoffs, component boundaries, failure behavior, linkage/ADR compliance. Loop until the engineer types `done` / `skip` / chooses `[implement]`.
* **[implement]** — dispatch the construction phase-executor:
  ```
  /exec-coding-session <INT-NNN>
  ```
  It dispatches the ready bead set in parallel isolated worktrees and lands the IB-aggregate PR(s). The conductor does not run the coding itself.

---

#### Gate 3 — Land → dispatch `/dekspec:land-intent`

> [!NOTE]
> Beads CLOSED, IB-branch CI green, PR(s) open. Replaces the prior assume-already-merged step.

1. Prompt the engineer:
   > "Drive the Intent's PR(s) through review to a landed state?
   > *   **[land]** Run the review-and-land phase-executor."
2. **Action** — on `land`, dispatch:
   ```
   /dekspec:land-intent <INT-NNN>
   ```
   The executor enumerates every IB-aggregate PR in dependency order, drives each through `/dekspec:review-pr` + the `REVIEW_PR_FAIL` grep-loop to a terminal verdict, and presents each squash-merge for explicit operator confirmation. It never auto-merges (ADR-026 RECOMMEND-only). On a persistent NO-GO it stops and hands back; the conductor does not proceed to lock until the PRs are landed.

---

#### Gate 4 — Lock & Propagation (`MERGED` / `TESTPASS` → `LOCKED`)

Once the Intent's PR(s) are landed on `main`:

1. Prompt the engineer:
   > "The work has landed. Ready to lock the Intent?
   > *   **[lock]** Freeze the Intent and propagate terminal status downstream."
2. **Action** — on `lock`, execute (this is the conductor's own ownership, not delegated):
   ```
   /write-intent --lock dekspec/intents/INT-NNN-<slug>.md
   ```
3. Confirm the transition to `LOCKED`.
4. **LOCK Propagation Ceremony**:
   - Scan the Intent's `## Layer impact analysis` + related index files; gather all associated AEs/WSes/ICs/IBs.
   - Promote any related artifact still in `PROPOSED`/`DRAFT` to its terminal status via `artifact_ops.py transition` (or the artifact's lock skill); leave nothing lingering in `TODO`/`DRAFT`/`PROPOSED`. Log every promotion.
5. **Graph Synchronization**:
   - `python plugins/dekspec/skills/_lib/scripts/artifact_ops.py update-index ...`
   - `dekspec audit relink` to restitch the link graph.
   - Verify health using `dekspec doctor --at .`.

---

## Auto Mode (`--auto`)

Walks the same lifecycle as Orchestrate Mode (PROPOSED → ACCEPTED → DECOMPOSE → IMPLEMENTING → TESTPASS → LOCK) without engineer prompts. The engineer-in-the-loop confirmation gate is replaced by a strict pre-condition check at every transition.

**Safety contract.** See [`dekspec/adrs/ADR-021-orchestrate-intent-auto-safety-contract.md`](../../../../dekspec/adrs/ADR-021-orchestrate-intent-auto-safety-contract.md). The contract is load-bearing — the walker MUST honor every clause verbatim:

1. **Refuse on first unmet pre-condition** with a named-gate error. The Intent stays in its starting state; no canonical changes are written.
2. **Never unlock any LOCKable artifact** (Intent, WS, IC, IB, AE, ADR, MSN, SP). Unlocking is reason-gated and engineer-driven via the per-artifact `--unlock` flag; `--auto` is an ergonomic surface over the forward-only happy path, not a replacement for the unlock ceremony.
3. **Never bypass `--testpass`.** The Verification block runs at every `--auto` invocation that reaches the `IMPLEMENTING → TESTPASS` transition; first non-zero exit halts the walk in `IMPLEMENTING` and records a `TESTFAIL` log row in the Intent's `## TESTFAIL records` table. Status does not flip to `TESTFAIL` (the `TESTFAIL` Status was retired 2026-05-25 — see CHANGELOG and ADR-021 §Open Issues for the doc-drift flag against the ADR body's stale prose).

### Step 1: Pre-flight gate check (all transitions, all pre-conditions)

Before walking any transition, enumerate every gate the walker will encounter from the Intent's current Status to `LOCKED`:

| Transition | Named gate | Pre-condition |
|---|---|---|
| `DRAFT` → `PROPOSED` | `analyze-complete` | `/dekspec:spec-intent`'s analyze step has run; coverage gaps closed or acknowledged in `## Open Issues`; size caps PASS. |
| `PROPOSED` → `ACCEPTED` | `accept-clean` | No `P0`/`P1`/`P2` blocking findings from the audit; no Open Issues with `P0`/`P1` severity unresolved. |
| `ACCEPTED` → `IMPLEMENTING` | `decompose-emitted` | `/dekspec:spec-intent`'s decompose step has emitted IBs (or taken the no-IB direct-bead shortcut for WS-fan-in = 0 IUs); every downstream child artifact (AE, WS, IC, IB) reachable from `## Layer impact analysis` is at `ACCEPTED` or higher. |
| `IMPLEMENTING` → `TESTPASS` | `verification-green` + `beads-closed` | Every child bead listed in the Intent's decomposition trail is `CLOSED`; every `verification[*].cmd` exits 0 (the diff-confinement gate + per-predicate scripts). |
| `TESTPASS` → `MERGED` | `branch-merged-to-main` | The Intent's `## Branch` is merged into `main` per git log; out-of-band engineer-driven check (`--auto` does not perform the merge). |
| `MERGED` → `LOCKED` | `post-merge-no-drift` | No post-merge drift findings in `dekspec audit doctor --at .`; all child artifacts have been promoted to their terminal status. |

For each gate, the walker verifies the pre-condition by reading the same `artifact_ops.py status-guard` surface the explicit-prompt mode consumes. The walker does not infer pre-conditions; it reads them.

If the Intent is at `LOCKED` on entry, refuse immediately — there is nothing for `--auto` to do, and the walker MUST NOT call `--unlock`.

If ANY gate from the Intent's current Status to `LOCKED` has an unmet pre-condition at flag-invocation time, REFUSE with:

```
REFUSED: --auto cannot advance — <stage> pre-condition '<gate-name>' unmet (detail: <gate-detail>). Intent stays at <current-status>. Run /write-intent --<flag> manually to surface the full diagnostic.
```

Concrete examples:

```
REFUSED: --auto cannot advance — ACCEPTED → IMPLEMENTING pre-condition 'decompose-emitted' unmet (detail: IB-042 is DRAFT, not ACCEPTED). Intent stays at ACCEPTED. Run /dekspec:spec-intent INT-088 manually to surface the full diagnostic.
```

```
REFUSED: --auto cannot advance — entry pre-condition 'never-unlock-locked' unmet (detail: Intent is already LOCKED; --auto does not unlock). Intent stays at LOCKED. Run /write-intent --unlock dekspec/intents/INT-088-...md manually if a substantive edit is intended.
```

The walker has not modified any artifact when this error is emitted. Drop back to default Orchestrate Mode (no `--auto`) for the remainder of this Intent's lifecycle, then re-invoke `--auto` once the gate clears.

### Step 2: Walk transitions in order

For each transition the pre-flight cleared:

1. **Re-verify the pre-condition** at the moment of execution (it could have changed between pre-flight and walk — concurrent edits, file moves, branch updates).
2. **Execute the transition** via the corresponding `/write-intent --<mode>` invocation (or direct `artifact_ops.py transition` call). The walker does NOT re-implement the per-mode logic; it drives the existing skill modes:
   - `PROPOSED → ACCEPTED`: `/dekspec:spec-intent <path>` (delegated; the executor's engineer-gated accept step)
   - `ACCEPTED → IMPLEMENTING`: `/dekspec:spec-intent <path>` (delegated; runs decompose + drives child artifacts, then transitions to `IMPLEMENTING`)
   - `IMPLEMENTING → TESTPASS`: `/write-intent --testpass <path>` (MUST run; never bypass)
   - `MERGED → LOCKED`: `/write-intent --lock <path>`
3. **Append a row to the running summary card** (in-memory).
4. **Continue to the next transition.** If the underlying `/write-intent --<flag>` invocation returns a non-zero exit, STOP — the underlying skill refused for a reason `--auto`'s pre-condition scan did not catch. Surface the verbatim error and halt the walk; the Intent stays at whatever Status the failed transition left it.

If a re-check at Step 2.1 fails, REFUSE per Step 1's contract — but the running summary card is preserved and presented as part of the refusal output (the partial walk's accomplishments are still informational).

**Test-failure halt.** At the `IMPLEMENTING → TESTPASS` transition, if any `verification[*].cmd` exits non-zero, halt the walk in `IMPLEMENTING` and record a row in the Intent's `## TESTFAIL records` table per the post-2026-05-25 semantics (TESTFAIL is a captured-failure log row, not a Status). Surface the failed predicate name + the underlying command's stderr. Do not retry. The engineer fixes the failure, then re-invokes `--auto` to resume.

### Step 3: Render the final summary card

After the walk completes (reached `LOCKED` OR refused mid-walk OR halted on a test-failure), emit a markdown card:

```
================================================================================
/orchestrate-intent --auto INT-NNN — walk summary
================================================================================
Started at: <starting-status>
Ended at:   <ending-status>
Transitions executed: <N>

| Transition | Outcome | Artifact | Notes |
|---|---|---|---|
| ...one row per transition, including the refusal/halt row if applicable... |

Amendment Log rows appended: <K>
Beads closed: <bead-IDs>
Verification predicates: <pass-count> passed / <fail-count> failed
================================================================================
```

The card is **informational, NOT gating** — the walk has already terminated when the card renders. The card is rendered to stdout per ADR-021 §Open Issues item 2 (file-persistence is deferred).

### Anti-patterns (the walker MUST NOT do these)

- **MUST NOT** invoke `/write-intent --unlock` under any path. If a downstream artifact requires unlock to advance, REFUSE — the engineer drops back to default Orchestrate Mode for that step.
- **MUST NOT** skip `/write-intent --testpass`. The Verification block is unconditional.
- **MUST NOT** silently auto-relock artifacts. Lock propagation happens through `/write-intent --lock`'s existing LOCK Propagation Ceremony (default Orchestrate Mode §E), not through `--auto` reaching around it.
- **MUST NOT** partial-advance and then ask the engineer mid-walk. The walker either runs the full pre-flighted sequence or refuses up-front; there is no hybrid mode.

---

## Status Mode (`--status`)

Read-only. Reports the target Intent's current status and enumerates every downstream child spec. **Mutates nothing** — no transitions, no unlocks, no index writes.

1. Resolve the target with the shared resolver (canonical `INT-NNN`, canonical/provisional path, or provisional incubation slug):
   ```
   python ../_lib/scripts/resolve_intent_target.py "<arg-from-$ARGUMENTS>"
   ```
   It emits JSON `{kind, path, intent_id, status, is_provisional}`. On exit 1 (unresolved / ambiguous), surface its stderr and STOP.
2. Read the resolved file's `## Status` and gather all linked AEs/WSes/ICs/IBs from `## Linked Architecture Elements` + `## Layer impact analysis`.
3. Render a read-only card and STOP — do not enter the conductor loop:
   ```markdown
   ================================================================================
   📊 INTENT STATUS — [INT-NNN](file:///...)   (or: PROVISIONAL slug <slug>)
   ================================================================================
   Title:           <Intent Title>
   Current Status:  [STATUS]
   Incubation:      <none (canonical) | dekspec/provisional/<slug>/>
   --------------------------------------------------------------------------------
   Downstream child specs:
     AE:  <AE-NNN [status], …  | none>
     WS:  <WS-NNN [status], …  | none>
     IC:  <IC-NNN [status], …  | none>
     IB:  <IB-NNN [status], …  | none>
   ================================================================================
   ```

---

## Verify Mode (`--verify`)

Read-only. Asserts every downstream child spec sits in a terminal status (`LOCKED` or `ACCEPTED`) — the post-merge completeness check. **Mutates nothing.**

1. Resolve the target with `resolve_intent_target.py` (as in Status Mode).
2. Gather all downstream AEs/WSes/ICs/IBs from `## Layer impact analysis` + the index files.
3. For each child, read its status. PASS if every child is `LOCKED` or `ACCEPTED`; FAIL otherwise.
4. Render a verdict card and STOP — do not enter the conductor loop or attempt any promotion:
   ```markdown
   ================================================================================
   ✅/❌ INTENT VERIFY — [INT-NNN](file:///...)
   ================================================================================
   Verdict: <PASS — all downstream specs terminal | FAIL — N lingering>
   --------------------------------------------------------------------------------
   | Child | Status | Terminal? |
   |---|---|---|
   | AE-NNN | LOCKED | ✅ |
   | IB-NNN | DRAFT  | ❌ |
   ================================================================================
   ```
   On FAIL, name each non-terminal child and the lock skill that would advance it (`/write-<kind> --lock …`); do not run it — `--verify` only reports.

---

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:orchestrate-intent"
one_line:   "Orchestrate an Intent lifecycle from TODO/DRAFT all the way to LOCKED."
modes:
  - { flag: "",          args: "<INT-NNN>",        description: "Detect the target Intent's current status and guide it forward through analysis, acceptance, decomposition, pre-coding reviews, chat interviews, and lock propagation." }
  - { flag: "--auto",    args: "<INT-NNN>",        description: "Walk the Intent's lifecycle to LOCKED without engineer prompts. Refuses on first unmet pre-condition; never unlocks; never bypasses --testpass. See ADR-021." }
  - { flag: "--status",  args: "<INT-NNN | provisional-slug | path>", description: "Check current status and list all downstream child specs (AEs, WSes, ICs, IBs). Accepts a provisional incubation slug/path too (resolved via _lib/scripts/resolve_intent_target.py)." }
  - { flag: "--verify",  args: "<INT-NNN | provisional-slug | path>", description: "Verify that all downstream specs are in terminal LOCKED or ACCEPTED statuses post-merge. Accepts a provisional incubation slug/path too." }
  - { flag: "--teaching", args: "",                 description: "Walk through an interactive tutorial on the lifecycle of DekSpec Intents." }
  - { flag: "--help",    args: "",                  description: "Show this help message." }
examples:
  - "/dekspec:orchestrate-intent INT-078"
  - "/dekspec:orchestrate-intent --auto INT-078"
  - "/dekspec:orchestrate-intent --status INT-036"
  - "/dekspec:orchestrate-intent --verify INT-079"
  - "/dekspec:orchestrate-intent my-incubation-slug   # provisional entry — promotes to canonical at the accept gate"
  - "/dekspec:orchestrate-intent --teaching"
  - "/dekspec:orchestrate-intent --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

---

## Teaching Mode

Present the 4-step ritual of Intent lifecycles:
1. **Creation & Alignment (L1)**: Outlining intent scope and architectural decisions.
2. **Decomposition & Specification (L2/L3)**: Authors contracts, working specs, and implementation briefs.
3. **Implementation & Verification (L4)**: Coding sessions and green test suites under diff confinement.
4. **Merge & Freeze (LOCKED)**: Archiving commitments and locking all specifications into the spec graph.
