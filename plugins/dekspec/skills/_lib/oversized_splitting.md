---
purpose: The shared flow for handling an Intent whose size assessment exceeds a cap. Both `/write-intent --analyze` and `/dekspec:spec-intent` reach this flow when an Intent breaches the Components / IBs / AEs / WSes / ICs caps.
audience: Skill authors referencing this flow from a parent SKILL.md.
referenced-from:
  - plugins/dekspec/skills/write-intent/SKILL.md (Analyze Mode Step 5)
  - plugins/dekspec/skills/spec-intent/SKILL.md (Phase 1 — Analyze)
  - plugins/dekspec/skills/write-mission/SKILL.md (Create Mode "convert from an over-cap Intent" entry point)
---

## Oversized Splitting & Mission Scaffolding Flow

### Status policy (load-bearing)

Over-cap is an **analysis finding, not a status** (ADR-057). `--analyze` records it as a `P2` Open Issue — *"re-split before acceptance"* — with **Source:** `analyze`, and the Intent **stays `DRAFT`**. The finding blocks acceptance until the Intent is re-split and re-analyzed. (`OVERSIZED` was a status until ADR-057; `dekspec migrate` maps it to `DRAFT`, and `artifact_ops.py transition` refuses it.)

`SUPERSEDED` means **this artifact was overridden or deprecated** — it shipped (`COMPLETE`), and a successor replaced it. An Intent that never shipped (DRAFT / PROPOSED / ACCEPTED) is not superseded by being split — nothing replaced anything — and a SUPERSEDED shell for it is an orphan that bloats the corpus and gives the wrong audit-trail signal.

Two non-SUPERSEDE paths cover every over-cap case:

1. **PEEL-OFF** (default when there is a natural core slice) — keep the parent's identity, narrow its scope in place, scaffold N-1 sibling Intents under the same Mission.
2. **CONVERT-TO-MISSION** (default when the scope is genuinely an umbrella over several capability surfaces) — turn the Intent INTO a Mission. The Intent file is deleted and the Mission inherits its substantive content; the Mission's Intent queue carries the child Intents.

SUPERSEDE+N is **not** a default. It is reserved for a genuine override of a shipped (`COMPLETE`) Intent — spawn a successor and mark the original SUPERSEDED.

### 1. Identify the partition shape

Read the Intent's `Motivation`, `Desired Outcome`, `Components affected`, and `Layer impact analysis`, then pick:

- **PEEL-OFF when:** the parent's identity maps cleanly to one core slice AND the remainder fits in 1-2 sibling Intents. Typical signal: 3-5 components, 2-3 IBs, one cohesive Motivation that narrows naturally.
- **CONVERT-TO-MISSION when:** the scope is an umbrella over N capability surfaces, each warranting its own Intent. Typical signal: ≥5 components, ≥4 IBs, a Motivation that reads as "the design substrate for a feature area", or a `Mission decomposition plan` already naming 3+ children with distinct concerns.

If unsure, peel off one slice and re-analyze what is left. If the remainder is still over cap → CONVERT-TO-MISSION.

### 2. Determine the Mission container

- **Case A (already under a Mission):** keep that Mission. PEEL-OFF siblings join its queue; CONVERT-TO-MISSION is rare here (recommend PEEL-OFF).
- **Case B (`Mission: none`):** PEEL-OFF authors a new Mission to coordinate parent + siblings; CONVERT-TO-MISSION moves the Intent's content into the new Mission's near-immutable section.

### 3. Interactive Split Plan & Approval

Present the proposed shape; default to the path chosen in Step 1, offer the other as a switch, and mention SUPERSEDE+N only if the engineer asks.

```markdown
================================================================================
⚠️ INTENT OVER SIZE CAP — PARTITION PLAN
================================================================================
Recommended path: [PEEL-OFF | CONVERT-TO-MISSION]

If PEEL-OFF:
  Mission Container:
  *   [EXISTING / NEW] [MSN-NNN](file:///...) — <Title>
  Parent (narrowed):
  *   [INT-NNN](file:///...) — <Parent Title (kept)>
      *Narrowed scope:* <core slice>
      *Components:* <reduced globs>
  Peeled-Off Sibling(s):
  1.  [NEW] [INT-MMM](file:///...) — <Sibling A>
  2.  [NEW] [INT-OOO](file:///...) — <Sibling B (optional)>

If CONVERT-TO-MISSION:
  New Mission:
  *   [NEW] [MSN-XXX](file:///...) — <Mission Title (inherits the Intent's umbrella scope)>
      *Outcome:* <derived from the Intent's Desired Outcome>
      *Near-immutable section:* (Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent) populated from the Intent's body
  Child Intents (DRAFT):
  1.  [NEW] [INT-MMM](file:///...) — <Child A>
  2.  [NEW] [INT-OOO](file:///...) — <Child B>
  3.  [NEW] [INT-PPP](file:///...) — <Child C (optional)>
  Disposition of the over-cap Intent file: **DELETE** (its substance moves to the Mission; no SUPERSEDED shell).

================================================================================
How would you like to proceed?
*   **[approve]** Apply the recommended path.
*   **[switch]** Switch to the other non-SUPERSEDE path.
*   **[adjust]** Customize the partition.
*   **[cancel]** Cancel and return to the main loop.
```

### 4. Auto-Scaffolding Execution

#### PEEL-OFF path:

1. If Case B, generate the new Mission at `dekspec/missions/MSN-XXX-<slug>.md` (status `PROPOSED`).
2. Narrow the parent Intent in place — Motivation, Desired Outcome, Components affected, Layer impact analysis — and append an Amendment Log entry. Re-run `--analyze`: when caps pass, resolve the `P2` "re-split before acceptance" issue and promote DRAFT → PROPOSED.
3. Generate the sibling Intent(s) at `dekspec/intents/INT-MMM-*.md` (status DRAFT, `Mission: MSN-XXX`). Register them in `dekspec/intent-index.md`.
4. The parent keeps its INT-NNN slot. **No SUPERSEDE entry is created.**

#### CONVERT-TO-MISSION path:

1. Generate the Mission at `dekspec/missions/MSN-XXX-<slug>.md` (status `PROPOSED`), populating the near-immutable section from the Intent:
   - **Outcome** = the Intent's Desired Outcome (or its `Mission decomposition plan` opening statement).
   - **Mission Verification** = a predicate covering the full umbrella surface.
   - **Out-of-scope** = the Intent's Non-Goals if any; otherwise a scaffolded placeholder.
   - **Flag strategy** = derived from `Components affected` + risk; often `none` for design-substrate Missions.
   - **Rollback plan** = reverse-merge-order child reverts.
   - **Kill criteria** = scaffolded placeholder if not specified.
   - **Autonomy ceiling** = the Intent's Autonomy.
   - **First Intent** = the highest-priority child.
2. Generate child Intents (status DRAFT, `Mission: MSN-XXX`) for each capability surface. The per-child scaffolding contract (title, AE subset, Components subset, Motivation, Verification from the type-default library, Mission backlink, `artifact_ops.py next-id intent` allocation, Source line keeping the historical INT reference, one Amendment Log Create row) is defined once in `plugins/dekspec/skills/write-mission/SKILL.md` §1a.1 Step 3b. Register each child in `dekspec/intent-index.md` and in the Mission's `### Intent queue`.
3. Register the Mission in `dekspec/mission-index.md`.
4. **Delete** the over-cap Intent file (`git rm dekspec/intents/INT-NNN-*.md`) and remove its `dekspec/intent-index.md` row (it never had a successor, so it does not enter the Archive). **No SUPERSEDED shell is created.**
5. Update cross-references to the deleted Intent in surviving artifacts — replace `INT-NNN §section` citations with `MSN-XXX §section` where the content moved; drop bare references where it is fully absorbed.
6. Run `dekspec relink` to refresh derived backlinks.

### 5. Redirect Focus & Resume Orchestration

- **PEEL-OFF:** the parent is now PROPOSED; continue its lifecycle, then surface the siblings.
- **CONVERT-TO-MISSION:** the Mission is PROPOSED; propose `/write-mission --activate` to authorize the programme, or go straight to the first child Intent.

```
> Which target should I orchestrate next?
> *   **[1]** MSN-XXX — <Mission Title> [PROPOSED]              ← convert default
> *   **[2]** INT-MMM — <Child A Title> [DRAFT]
```

Upon the engineer's choice, redirect orchestrator focus to that target.

### Retroactive cleanup pattern

If a SUPERSEDED shell of a never-shipped Intent already exists (legacy of the old SUPERSEDE+N flow) and its substance already lives in a Mission, treat it as a CONVERT-TO-MISSION case post-hoc: delete the orphan Intent file, remove its Archive row from `dekspec/intent-index.md`, and run `dekspec relink`. Prose citations in surviving artifacts may stay as historical residue.
