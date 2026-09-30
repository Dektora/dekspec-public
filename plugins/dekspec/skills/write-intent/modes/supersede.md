# Supersede Mode (not-yet-complete → SUPERSEDED, ADR-035)

[← back to dispatcher](../SKILL.md)

Transitions a not-yet-complete Intent to `SUPERSEDED` when its committed direction has been absorbed by a **named successor artifact** (an `INT-NNN` or `MSN-NNN`). Doctrine: **ADR-035** (the non-LOCKED absorption carve-out alongside ADR-028's LOCKED-override case). The canonical absorption example is a coordination Intent wholly absorbed by a completed Mission.

Arguments: `--supersede <Intent-path> --by <INT-NNN-or-MSN-NNN>`. If `--by` is missing, ask the engineer which successor artifact absorbed the Intent's direction before proceeding — a free-text reason is NOT acceptable; ADR-035's distinguishing test is a named successor.

### Step 1: Validate

1. File exists; read Status.
2. **Allowed set (ADR-035):** `DRAFT`, `PROPOSED`, `ACCEPTED`. Refusals:
   - `COMPLETE` — a finished Intent is overridden by a successor Intent (ADR-028), not absorbed. Surface that path and stop.
   - `SUPERSEDED` — already terminal. Stop.
   - A retired status (OVERSIZED, IMPLEMENTING, TESTPASS, MERGED) — run `dekspec migrate` first.
3. **Child IBs.** If IBs name this Intent as `**Parent:**`, list them with their status. The engineer decides each one's fate before proceeding — re-parent it to the successor, supersede or deprecate it (`/write-ibs`), or let a COMPLETE IB stand as history. Do not leave an ACCEPTED IB pointing at a superseded parent silently.
4. The successor referenced by `--by` exists in the spec graph (an Intent under `dekspec/intents/` or a Mission under `dekspec/missions/` — or, for a cross-repo absorption, the engineer confirms the successor lives in the consumer repo). If it cannot be found and the engineer does not confirm a cross-repo successor, refuse.

### Step 2: Transition

Run the deterministic helper (it re-checks every Step 1 status gate and refuses with a typed error on violation — surface stderr verbatim on non-zero exit and STOP):

```
python ../_lib/scripts/artifact_ops.py supersede <Intent-path> --by <INT-NNN-or-MSN-NNN> --engineer <engineer-or-agent>
```

This flips Status to `SUPERSEDED`, rewrites the `## Superseded-By` section to the successor id, bumps Modified, and appends the Amendment Log row.

### Step 3: Index Archive Move

1. Update the Status cell: `python ../_lib/scripts/artifact_ops.py update-index dekspec/intent-index.md --id INT-NNN --status SUPERSEDED`.
2. Move the Intent's row in `dekspec/intent-index.md` from the **Active queue** table to the **Archive** table. The Archive row uses the smaller column set (Intent / Title / Status / Superseded-By / Merged date / Mission / Notes); copy the title and mission from the Active row, set Status `SUPERSEDED`, set Superseded-By to the successor id, leave Merged date empty (the Intent never shipped). (Cross-table move with a column-shape change — hand-authored, mirroring Lock Mode's archive move.)

### Step 4: Closing

1. If the successor is in this repo, confirm it references the absorbed Intent (e.g. the Mission's Intent queue or the successor Intent's Source/Links). If it does not, surface a one-line suggestion to add the back-reference — do not edit the successor unprompted.
2. Run `dekspec relink` so backlinks re-derive.
3. Surface the result: the Intent's new terminal state, the successor recorded, and the index move.

**End of Supersede Mode.**
