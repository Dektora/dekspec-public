---
purpose: The shared flow for handling an Intent that fails the OVERSIZED size/cap check. Both `/write-intent --analyze` and `/dekspec:orchestrate-intent` reach this flow when an Intent breaches Components / IUs / AEs / WSes / ICs caps.
audience: Skill authors referencing this flow from a parent SKILL.md.
referenced-from:
  - plugins/dekspec/skills/write-intent/SKILL.md (Analyze Mode Step 5)
  - plugins/dekspec/skills/orchestrate-intent/SKILL.md (Orchestrate Mode Status A)
  - plugins/dekspec/skills/write-mission/SKILL.md (Create Mode "convert from OVERSIZED Intent" entry point)
---

## Oversized Splitting & Mission Scaffolding Flow

### Status policy (load-bearing)

`SUPERSEDED` means **this artifact was overridden or deprecated** — it shipped (LOCKED), and a successor replaced it. Provisional artifacts (DRAFT / OVERSIZED / PROPOSED / ACCEPTED) that *never shipped* cannot be SUPERSEDED, because nothing replaced anything. Marking provisional state SUPERSEDED creates an orphan shell — a file that exists only as an exploration record — which bloats the corpus and gives the wrong audit-trail signal.

Two non-SUPERSEDE paths cover every OVERSIZED case:

1. **PEEL-OFF** (default for size violations with a natural core slice) — keep the parent's identity, narrow its scope in place, scaffold N-1 sibling Intents under the same Mission.
2. **CONVERT-TO-MISSION** (default when the natural decomposition is broader than one parent + sibling — i.e., the Intent's scope is genuinely an umbrella design surface for a Mission's worth of work) — turn the OVERSIZED Intent INTO a Mission. The Intent file is replaced (deleted + the Mission file inherits the substantive content); the Mission's Intent queue carries the child Intents that decompose the umbrella.

SUPERSEDE+N is **NOT** a default. It is reserved for the genuine override case (a LOCKED Intent that needs substantive replacement) — and even then, the convention is to spawn a successor Intent and mark the original SUPERSEDED. Provisional state never produces a SUPERSEDED shell.

### 1. Identify the partition shape

Read the oversized Intent's `Motivation`, `Desired Outcome`, `Components affected`, and `Layer impact analysis`. Decide which of the two non-SUPERSEDE shapes fits:

- **Use PEEL-OFF when:** the Intent has a clear core slice (the parent's identity maps cleanly to one slice) AND the remainder fits in 1-2 sibling Intents under the same Mission. Typical signal: 3-5 components, 2-3 IUs, one cohesive Motivation that narrows naturally.
- **Use CONVERT-TO-MISSION when:** the Intent's scope is a genuine umbrella over N capability surfaces, each warranting its own Intent. Typical signal: ≥5 components, ≥4 IUs, the Motivation reads as "this is the design substrate for an entire feature area," or the Intent's `Mission decomposition plan` section already names 3+ children with distinct concerns.

If unsure, peel off one slice and see what's left. If the remainder is still OVERSIZED → escalate to CONVERT-TO-MISSION.

### 2. Determine the Mission container

- **Case A (already under a Mission):** Preserve that Mission. PEEL-OFF siblings join its queue; CONVERT-TO-MISSION is rare here (the Intent is already framed under a Mission and shouldn't reframe to a different Mission — recommend PEEL-OFF instead).
- **Case B (`Mission: none`):** PEEL-OFF authors a new Mission to coordinate parent + siblings; CONVERT-TO-MISSION reframes the OVERSIZED Intent's content directly into the new Mission's near-immutable section.

### 3. Interactive Split Plan & Approval

Present the proposed shape to the engineer in a structured card. Default the surfaced plan to PEEL-OFF or CONVERT-TO-MISSION per Step 1; surface the other option as a switchable choice; mention SUPERSEDE+N only if the engineer asks (it is rarely correct).

```markdown
================================================================================
⚠️ OVERSIZED INTENT DETECTED — PARTITION PLAN
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
  *   [NEW] [MSN-XXX](file:///...) — <Mission Title (inherits the OVERSIZED Intent's umbrella scope)>
      *Outcome:* <derived from the OVERSIZED Intent's Desired Outcome>
      *Near-immutable section:* (Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent) populated from the OVERSIZED Intent's body
  Child Intents (DRAFT):
  1.  [NEW] [INT-MMM](file:///...) — <Child A>
  2.  [NEW] [INT-OOO](file:///...) — <Child B>
  3.  [NEW] [INT-PPP](file:///...) — <Child C (optional)>
  Disposition of the OVERSIZED Intent file: **DELETE** (its substance moves to the Mission; no SUPERSEDED shell is created).

================================================================================
How would you like to proceed?
*   **[approve]** Apply the recommended path.
*   **[switch]** Switch to the other non-SUPERSEDE path.
*   **[adjust]** Customize the partition.
*   **[cancel]** Cancel and return to the main loop.
```

### 4. Auto-Scaffolding Execution

#### PEEL-OFF path:

1. If Case B, generate the new parent Mission file at `dekspec/missions/MSN-XXX-<slug>.md`.
2. Narrow the parent Intent in place — update Motivation, Desired Outcome, Components affected, Layer impact analysis. Append an Amendment Log entry. Re-run `--analyze`; transition DRAFT/OVERSIZED → PROPOSED if caps pass.
3. Generate peeled-off sibling Intent(s) at `dekspec/intents/INT-MMM-*.md` (status DRAFT, `Mission: MSN-XXX`). Register in `dekspec/intent-index.md`.
4. Parent keeps its INT-NNN slot. **No SUPERSEDE entry created.**

#### CONVERT-TO-MISSION path:

1. Generate the new Mission file at `dekspec/missions/MSN-XXX-<slug>.md`. The near-immutable section is populated by extracting from the OVERSIZED Intent:
   - **Outcome** = Intent's Desired Outcome (or its `Mission decomposition plan` opening statement).
   - **Mission Verification** = predicate covering the Intent's full umbrella surface (run `dekspec:mission-author` style).
   - **Out-of-scope** = Intent's explicit non-goals if any; otherwise scaffolded placeholder.
   - **Flag strategy** = derived from Intent's `Components affected` + risk analysis; often `none` for design-substrate Missions.
   - **Rollback plan** = reverse-merge-order child reverts.
   - **Kill criteria** = scaffolded placeholder if not specified.
   - **Autonomy ceiling** = Intent's Autonomy (typically `manual` for design parents; `medium` if the child surfaces are mechanical).
   - **First Intent** = the highest-priority child.
2. Generate child Intents (status DRAFT, `Mission: MSN-XXX`) for each capability surface named in the Intent's `Mission decomposition plan` section. Per-child scaffolding contract — title, Linked AEs subset, Components subset, Motivation from the decomposition row, Verification from the type-default library, Mission backlink, deterministic INT-NNN allocation via `artifact_ops.py next-id intent`, Source line preserving historical INT-OOO reference, single Amendment Log Create row — is defined in `plugins/dekspec/skills/write-mission/SKILL.md` §1a.1 Step 3b (single source of truth). Register each scaffolded child in `dekspec/intent-index.md` Active queue + the new Mission's `### Intent queue` live section.
3. Register the Mission in `dekspec/mission-index.md`.
4. **Delete** the OVERSIZED Intent file (`git rm dekspec/intents/INT-NNN-*.md`). Remove its row from `dekspec/intent-index.md` (it was in the Active queue, not Archive — and it should not enter Archive since it never had a successor). **No SUPERSEDED shell is created.**
5. Update any cross-references to the deleted Intent in surviving artifacts (LOCKED Intents, IBs, AEs, ADRs) — replace `INT-NNN §section` citations with `MSN-XXX §section` where the content has moved; drop bare INT references where the content is fully absorbed.
6. Run `dekspec audit relink` to refresh derived backlinks.

### 5. Redirect Focus & Resume Orchestration

- **PEEL-OFF path:** parent is now PROPOSED; propose continuing its lifecycle, then surface siblings for subsequent work.
- **CONVERT-TO-MISSION path:** Mission is TODO; propose `/write-mission --activate` once the first child Intent reaches LOCKED, or proceed directly to orchestrating the first child Intent.

```
> Which target should I orchestrate next?
> *   **[1]** MSN-XXX — <Mission Title> [TODO]                  ← convert default
> *   **[2]** INT-MMM — <Child A Title> [DRAFT]
```

Upon the engineer's choice, redirect orchestrator focus to that target.

### Retroactive cleanup pattern

If an OVERSIZED → SUPERSEDED Intent shell already exists in the corpus (legacy of the old SUPERSEDE+N flow), and its substance has already migrated to a Mission, treat it as a CONVERT-TO-MISSION case post-hoc:

- Delete the orphan Intent file.
- Remove its Archive row from `dekspec/intent-index.md`.
- Run `dekspec audit relink` to refresh AE backlinks.
- Leave dangling prose citations in surviving artifacts as historical residue (audit does not check prose-text references); they can be cleaned up opportunistically.
