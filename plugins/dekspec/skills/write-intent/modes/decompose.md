# Decompose Mode (ACCEPTED → IMPLEMENTING)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Refuses if Status is not `ACCEPTED`. Branches by IB-need (Decision #12) and scaffolds beads.

> **Inline execution.** This mode runs directly in the parent context so it has access to the `Skill` tool and can invoke the sister skills `/write-ibs` and `/write-beads` directly.

### Step 1: Validate

1. File exists; Status is `ACCEPTED`.
2. Open Issues table has zero blocking entries (analyze must have closed them).
3. Size Assessment shows all caps PASS.
4. Layer impact analysis has a populated WS-fan-in mapping per IU (recorded by `--analyze` Step 7).
5. For `type: bug`: the `Reproduction:` block is populated and concrete (not just "TBD").
6. The current branch is `int/INT-NNN-<slug>` matching the Intent's `Branch` field. If the engineer is on a different branch, refuse with the correct branch named.

### Step 2: Bug-Type Reproduction Scaffold (type: bug only)

For `type: bug`, the first IB / bead is the failing test that proves the Reproduction. Invoke `/write-beads --bug-reproduction <Intent-path>`. The sister skill (P1.7) consumes the Intent's `Reproduction:` block and produces a single bead whose acceptance criterion is "the test runs, asserts the documented failing behavior, and fails on the current code." Capture the bead's path and its eventual test path; substitute the test path into the Intent's Verification block, replacing the `<reproduction-test-path-from-IB-1>` placeholder with the concrete file path. Save.

For non-bug types, skip Step 2.

### Step 3: Per-IU Branch by WS Fan-In

For each Implementation Unit recorded in the Layer impact analysis (excluding IB-1 if `type: bug`):

- **WS fan-in = 1** (single-WS IU). Invoke `/write-beads <Intent-path>` directly with a per-IU scope marker. The bead reads the WS content from the named WS without an intermediate IB.
- **WS fan-in ≥ 2** (multi-WS IU). Invoke `/write-ibs <Intent-path>` first to author IB-NNN with the reconciled spec content. Then invoke `/write-beads <IB-path>` to scaffold the bead(s) under that IB. The IB's parent is the Intent; the bead's parent is the IB.

The skill awaits the sister-skill calls; both are interactive enough that the engineer reviews each IB / bead before it lands. Record each IB-NNN and bead-XXXX produced in the Intent's Layer impact analysis as a verification trail.

### Step 4: Post-Decomposition Cap Re-Check

Sum:

- IUs decomposed (IBs + direct-bead IUs)
- Components actually touched by the produced beads (cross-checked against `Components affected:`)

If either exceeds its hard cap (≤3 IUs, ≤3 components), the decomposition is wrong-shaped. Discard the new IBs / beads (mark them ABANDONED via the sister skills' rollback paths or, failing that, surface them for manual cleanup), set the Intent's Status back to `OVERSIZED`, log the cap violation in Open Issues, and refuse to transition to `IMPLEMENTING`. Immediately trigger the **Automated Oversized Splitting & Mission Scaffolding Flow** (detailed in Analyze Mode, Step 5) to partition the scope and redirect the focus of orchestration.

### Step 5: Promote

If all checks pass:

1. Flip Status to `IMPLEMENTING`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from ACCEPTED --to IMPLEMENTING --note "Decomposed into N IUs (M IBs, K direct beads); transitioned ACCEPTED to IMPLEMENTING via /write-intent --decompose" --engineer <engineer-or-agent>` (fill in N/M/K from the decomposition; surface stderr on non-zero exit and STOP).
2. Update `dekspec/intent-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/intent-index.md --id INT-NNN --status IMPLEMENTING` (surface stderr on non-zero exit), then update the row's IUs column by hand.
3. Surface the next-step message: bead execution proceeds via `/exec-coding-session` per bead. When all beads have closed, run `/write-intent --testpass` to verify diff confinement and run the Verification predicate.

**End of Decompose Mode.**
