# Complete Mode (→ COMPLETE)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Runs from the `main` branch. Marks a finished Intent `COMPLETE`.

> **ADR-046.** Intents terminate at `COMPLETE`, not `LOCKED` — a finished Intent is a historical record, not a frozen decision. The former ADR-017 three-path lock gate (Path A/B/C) and its L13 audit rule are **retired**: the pre-freeze audit they ran is redundant with `MERGED` (an Intent only reaches its terminal after its branch merged, which already passed CI + PR review). The `--lock` flag is retained for compatibility; it now completes the Intent.

### Step 1: Validate

1. Current branch must be `main`.
2. Status is `MERGED` (engineer-set after the Intent's work merged to `main`). If it is any other status, refuse, naming the current status and the expected `MERGED`.
3. *Direct-bead Intents only (no live `int/` branch to merge):* if the work landed via direct beads rather than a branch merge, confirm every bead in `## Layer impact analysis` is `closed` — run `python ../_lib/scripts/artifact_ops.py check-retro-lock <Intent-path>` (surface stderr and refuse on non-zero exit; it names any open bead). This is the evidence the work landed for an Intent that never carried a live branch.

### Step 2: Mission Append (if `mission:` is set)

If the Intent's `Mission:` field is populated:

1. Locate the Mission file at `dekspec/missions/MSN-NNN-*.md`.
2. If the Mission file does not exist, log a non-blocking warning identifying the missing file path and skip the append. Do **not** refuse.
3. If the Mission file exists, append a row to the Mission's Intent queue section: `| INT-NNN | <title> | <type> | COMPLETE |`. The Mission's own `/write-mission --review` handles richer queue updates; this is a one-line append. (A Mission activates once its first child Intent is `COMPLETE`.)

### Step 3: Promote

1. Flip Status to `COMPLETE`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from MERGED --to COMPLETE --note "Merged to main; completed via /write-intent --lock (ADR-046)." --engineer <engineer-or-agent>`. Surface stderr on non-zero exit and STOP.
2. Move the Intent's row in `dekspec/intent-index.md` from the **Active queue** table to the **Archive** table. The Archive row uses the smaller column set (Intent / Title / Status / Superseded-By / Merged date / Mission / Notes); copy the title and mission from the Active row, set Status `COMPLETE`, set Merged date to today's date, leave Superseded-By empty. (Cross-table move with a column-shape change — hand-authored.)
3. Surface a closing summary: the Intent is complete; its file remains the executed record. If the Intent had a Mission, mention the Mission's Intent queue was updated.

**End of Complete Mode.**
