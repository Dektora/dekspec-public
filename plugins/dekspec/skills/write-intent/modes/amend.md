# Amend Mode (structured mid-flight change with invariant re-check)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Use when the Intent's scope, components, AEs, type-specific fields, or verification needs a substantive change after `--analyze` / `--accept` / `--decompose` has already run. `--amend` cascades: applies the change, re-runs the invariants, transitions Status back if a hard cap is now violated.

### `--editorial` modifier (INT-088 IU-1, ds-uxpy)

`--amend --editorial` records a surface-only correction in the Amendment Log **without** flipping Status and **without** triggering the PROPOSED→DRAFT or ACCEPTED→DRAFT cascade. Use this for typo fixes, prose clarifications inside `## Motivation` / `## Desired Outcome`, link-text adjustments, and other narrative-only changes that do not alter the Intent's behavioral surface.

**Refusal contract.** `--editorial` REFUSES (with a named-field error) if the in-flight diff touches ANY of:

- §Verification block
- §Components affected
- §Acceptance Criteria (when present)
- §Implementation Units (the IU list under `## Layer impact analysis`)

The refusal error names the offending field. The exact message format is:

```
--editorial refused: diff touches behavioral field '<field-name>'. Use --amend (without --editorial) for behavioral revisions; that walk will cascade PROPOSED→DRAFT or ACCEPTED→DRAFT as designed.
```

**How to run.** After applying the editorial edit to the Intent file in place (Edit tool — narrative sections only), invoke the shared helper to classify the diff against the git-HEAD baseline and append the `editorial` Amendment Log row:

```bash
python plugins/dekspec/skills/_lib/scripts/artifact_ops.py editorial-amend \
  <Intent-path> \
  --note "<one-line summary of the editorial change>" \
  [--engineer <email>] \
  [--baseline <path-to-prior-version>]
```

The helper:

1. Reads the on-disk Intent text and its git-HEAD baseline (or `--baseline <path>` when passed explicitly).
2. Runs the diff classifier (`classify_intent_diff`) to enumerate behavioral fields touched.
3. If the touched-list is non-empty, exits non-zero with the refusal message above and writes nothing.
4. If the touched-list is empty, appends a row of the form `| YYYY-MM-DD | editorial | <note> | <engineer> |` to `## Amendment Log`, bumps `Modified`, and exits 0.

The Intent's `Status` field is **untouched** on the success path. The Intent stays in PROPOSED / ACCEPTED / IMPLEMENTING / wherever it already was.

When `--editorial` is NOT passed, the rest of this mode body (Steps 1–6 below) runs as before — that codepath is the substantive-change cascade and applies to behavioral-field edits.

### Step 1: Validate

1. File exists; Status is `DRAFT`, `PROPOSED`, `ACCEPTED`, `IMPLEMENTING`, or `OVERSIZED`. Refuse on TESTPASS, MERGED, LOCKED, SUPERSEDED — amendments to passed/merged/locked Intents are not allowed at this scale. Locked Intents that need a substantive change spawn a successor Intent and mark this one SUPERSEDED.

### Step 2: Capture the proposed change

Prompt the engineer for:

1. **Field** being amended — one of: `linked_architecture_elements`, `components_affected`, `verification`, `motivation`, `desired_outcome`, `type_specific.<key>`, `autonomy`, `intent_type`, or `mission`.
2. **Change kind** — `add`, `remove`, `replace`, or `revise`.
3. **Old value** (for `remove` / `replace` / `revise`) — exact text or ID to be modified.
4. **New value** (for `add` / `replace` / `revise`) — exact text or ID to be set.

Capture before applying — never silently mutate.

### Step 3: Apply the edit

Use the Edit tool to modify the Intent file in-place per the captured change.

### Step 4: Re-run invariants

After the edit:

1. **Schema validation** — `parse_intent(<path>)` must succeed. If it fails, revert the edit and abort with the schema error.
2. **Size caps** — recompute the five hard caps. If any cap is now violated, transition Status to `OVERSIZED` and abort the Amend with a message naming the violated cap and the change that caused it. Engineer must split or re-scope.
3. **Linkage** — re-run L7a / L7b / T13–T16 / L9 as in `--audit` Step 2. CRITICAL findings here abort with a revert-or-fix prompt.
4. **Drift** — re-run D19 / D20 against the new prose. CRITICAL findings abort with a revert prompt.
5. **Mission linkage (L8)** — if `mission:` changed, re-verify the Intent's Autonomy ≤ the new Mission's Autonomy ceiling.

### Step 5: Cascade Status if needed

The amendment may invalidate prior state:

- If the Intent was PROPOSED and the amended Linked AEs or Components shifted, you should drop it back to DRAFT and re-run `--analyze`. Default behavior: revert Status to DRAFT and tell the engineer to re-run `--analyze`. Mention this is intentional — the Coverage report and Size assessment cached at PROPOSED no longer match.
- If the Intent was ACCEPTED and the amendment touched anything `--accept` validated (linkage, components, verification, drift), revert Status to DRAFT and tell the engineer to re-run `--analyze` then `--accept`. The acceptance is no longer current.
- If the Intent was IMPLEMENTING and the amendment touched `Components affected` such that the existing diff is now out-of-scope vs the new globs, surface the conflict — engineer must either revert the diff or revise globs further.
- If the Intent was OVERSIZED, an amendment is the typical remedy; transition to DRAFT after the change and re-run `--analyze`. (The pre-2026-05-25 enum had a `TESTFAIL` Status here too — retired per E3 audit.)

### Step 6: Log and exit

1. Update Modified date.
2. Append an Amendment Log entry: `| <date> | Substantive | Amended <field> via /write-intent --amend: <one-line summary of change>. Status transition: <old> → <new>. | <engineer-or-agent> |`
3. Save.
4. Surface the next-step message naming the recommended next mode (typically `--analyze` after Status cascade back to DRAFT; `--testpass` if the amendment was applied at IMPLEMENTING and Status holds).

> Editorial branch reminder: the Step-6 row above uses `Substantive` in the Type column. The `--editorial` modifier (see the section at the top of this file) instead writes `Type=editorial` and does NOT cascade Status. The schema enum at `tooling/dekspec/schemas/intent.schema.yaml::amendment_log.items.properties.type.enum` is `[editorial, unlock, substantive]`; both rows are valid.

**End of Amend Mode.**
