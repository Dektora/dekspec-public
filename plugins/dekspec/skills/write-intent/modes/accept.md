# Accept Mode (PROPOSED → ACCEPTED)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Refuses if Status is not `PROPOSED`.

Passing the `--accept` flag counts as deliberate engineer approval — no additional confirmation is asked. The mode runs the linkage / shape / drift checks one last time before promoting.

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `dekspec:intent-author` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract**; on return, the orchestrator runs `dekspec validate --kind intent <path>` and confirms Status flipped PROPOSED → ACCEPTED with the Amendment Log entry appended.

### Step 1: Validate

1. File exists; Status is `PROPOSED`.
2. All required template fields are populated (re-run T13 / T14 / T15 / T16 from Analyze Step 1 + Step 2).
3. Open Issues has no unresolved `P1` entry and no unresolved over-cap ("re-split before acceptance") `P2` finding from `--analyze`. Other `P2`/`P3` entries persist.
4. Size Assessment shows all caps PASS.
5. Linked Architecture Elements: every AE-NNN entry resolves to an existing AE file (audit-v2 L7).
6. Components affected: every glob resolves to at least one path that exists (audit-v2 L7).
7. Verification: every `cmd:` entry resolves. Cmds referencing TBD scripts produce a WARNING but do not block Accept (audit-v2 L9). Cmds with unresolved placeholders refuse, except `<reproduction-test-path-from-IB-1>`, which `--decompose` fills.

If any check fails, refuse with the explicit list. Do not promote.

### Step 2: Drift Re-Check

Re-run **D19 (no measurable targets)** and **D20 (no decision rationale)** against the current file (engineer may have edited since Analyze). Refuse on any new finding.

### Step 3: Provisional Promotion Gate (INT-082)

Before the canonical Status transition, check whether the Intent has a corresponding provisional incubation folder under `dekspec/provisional/`. If yes, render the promotion plan and require explicit engineer confirmation — the gate that turns ACCEPTED from an incidental status walk into the deliberate "I commit to the canonical replacement" decision.

1. **Detect incubation.** Look for a folder under `dekspec/provisional/` whose name matches this Intent's slug, or whose contents include a file referencing this Intent's ID (e.g., `replaces: INT-NNN` for a CoW-staged sibling artifact).
2. **Plan the promotion by hand.** Walk the incubation folder's files; for each, identify whether it maps to a `replaces: <KIND-NNN>` REPLACE-mode row (preserve canonical ID, `git mv` into canonical path) or a NEW-mode row (allocate the next-free canonical ID). See [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow) for the renumber + `git mv` recipe. (The previous dry-run CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` — the hand-promote workflow is now canonical.)
3. **Render the plan to the engineer.** Format as a scannable table separating REPLACE-mode rows (preserve canonical ID) from NEW-mode rows (next-free canonical ID).
4. **Request explicit confirmation.** Ask: "Promotion of <N> provisional artifact(s) will accompany this ACCEPTED transition. Confirm? [yes/no/show-diff <file>]". `yes` (or `confirm`) proceeds to Step 4. `no` aborts the entire `--accept` — the Intent stays at `PROPOSED` and no canonical changes happen. `show-diff <file>` previews the substantive content delta before deciding (loop back to the prompt).
5. **On confirmation**, execute the hand-promote workflow (renumber + `git mv` per Step 2's plan) atomically with the Status transition in Step 4.

If no incubation folder is detected, skip directly to Step 4 (this is the common case for canonical-only Intents).

### Step 4: Promote

1. Flip Status to `ACCEPTED`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from PROPOSED --to ACCEPTED --note "Promoted PROPOSED to ACCEPTED via /write-intent --accept" --engineer <engineer-or-agent>` (surface stderr on non-zero exit and STOP).
2. Update `dekspec/intent-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/intent-index.md --id INT-NNN --status ACCEPTED` (surface stderr on non-zero exit). Or run `dekspec regen-indexes` for the full deterministic refresh (MSN-015 path).
3. Surface the next-step message: run `--decompose` to author the child IBs (Status stays ACCEPTED while they execute). For a `type: bug` Intent the first IB's acceptance includes the failing reproduction test — the Intent's ADR-029 Outcome Verification test, written red-first.

**End of Accept Mode.**
