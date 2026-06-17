# Unlock Mode (LOCKED → PROPOSED)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Walks a LOCKED Intent back to a mutable state so an **editorial** correction can be applied — a stale `Components affected:` glob, a broken cross-reference, a renamed-file path string. `--unlock` is the editorial precursor to `--lock` and exists to satisfy the CLAUDE.md guardrail ("LOCKED artifacts cannot be edited — unlock to PROPOSED first"). Substantive change to a LOCKED Intent is **not** an `--unlock` case: it still spawns a successor Intent and marks the original `SUPERSEDED` (see Rules and `--amend`).

Unlock Mode mirrors the canonical reason-gate contract in [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock; the status flip and the two-table index move are write-intent-specific (the inverse of Lock Mode).

### Step 1: Validate

File exists; current `Status` is `LOCKED`. If it is any other status, refuse in one sentence naming both the current status and the expected status (`LOCKED`). Do not proceed past this step on a mismatch.

### Step 2: Reason gate + downstream impact

Per [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock Step 2: ask the engineer "Why is this Intent being unlocked? (This will be recorded verbatim in the Amendment Log.)" and wait for a written reason. Reject empty replies, single-word replies (`"typo"`, `"fix"`), and bare punctuation — demand at least one full sentence naming what is changing and why now. Loop until a substantive reason is given, or abort without writing if the engineer declines.

Downstream impact scan: grep `dekspec/working-specs/`, `dekspec/interface-contracts/`, and `dekspec/implementation-briefs/` for references to this Intent's id; surface the affected artifacts and their statuses alongside the reason prompt so the engineer sees the blast radius before confirming.

### Step 3: Demote

Only after a valid reason is supplied:

1. Flip Status to `PROPOSED`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from LOCKED --to PROPOSED --note "<engineer's reason verbatim>" --engineer <engineer-or-agent>`. The reason text passed via `--note` MUST be the engineer's words verbatim — no paraphrasing, no summarizing, no cleanup; the engineer's words are the audit trail. Surface stderr on non-zero exit and STOP.
2. Move the Intent's row in `dekspec/intent-index.md` from the **Archive** table back to the **Active queue** table — the inverse of Lock Mode Step 2. The Active-queue row uses the wider column set; copy the title and mission from the Archive row and set Status `PROPOSED`. (Cross-table move with a column-shape change — hand-authored.)
3. If the Intent's `Mission:` field is populated and the Mission file exists, walk that Mission's Intent-queue row for this Intent back to `| INT-NNN | <title> | <type> | PROPOSED |` (the inverse of Lock Mode Step 2's append). If the Mission file does not exist, log a non-blocking warning and skip.

### Step 4: Validate and report

Re-run `dekspec check validate --kind intent <Intent-path>`. Surface any validation error and stop — the unlock has written but the artifact is structurally broken; the engineer must fix it. On success, surface a closing reminder: apply the editorial correction, then re-run `/write-intent --lock <path>` to re-freeze — ADR-017 Path B is the available re-lock path, since the Intent's downstream WS/IC/IBs are already `>= ACCEPTED`. The Intent is mutable until then.

**End of Unlock Mode.**
