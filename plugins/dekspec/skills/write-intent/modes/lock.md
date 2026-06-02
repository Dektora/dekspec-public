# Lock Mode (→ LOCKED)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Runs from the `main` branch. Two sufficient paths reach `LOCKED` (ADR-017); Step 1 accepts **either**.

### Step 1: Validate

Current branch must be `main`. Then **either Path A or Path B** must hold — either alone is sufficient.

**Path A — forward lifecycle flow:**
1. Status is `MERGED` (engineer-set after merging the Intent branch into `main`).
2. The most recent Verification record matches the most recent `--testpass` Amendment Log entry; if the Verification block was edited since `--testpass`, refuse — the predicate has changed and must be re-run.
3. The Intent file on `main` is identical to the file as it existed when `--testpass` last ran (diff the Verification block; if changed, refuse).

**Path B — downstream artifacts accepted (ADR-017):**
1. Every downstream artifact the Intent produced — the Working Specs, Interface Contracts, and Implementation Briefs named in the Intent's Layer impact analysis — is at status `ACCEPTED` or higher (`ACCEPTED` or `LOCKED`).
2. If any is below `ACCEPTED`, refuse and name the blocking artifact(s).
3. Path B does **not** require `Status: MERGED`, a `--testpass` record, or a branch diff — it is the path for Intents whose work shipped outside the Intent lifecycle (direct beads, mega-integration branches). Beads (L4) are not part of the Path B gate.

If neither path holds, refuse, naming what each path still needs. The Intent lock-coherence audit rule (L13, AE-003) encodes both paths so the engine and this skill agree.

### Step 2: Mission Append (if `mission:` is set)

If the Intent's `Mission:` field is populated:

1. Locate the Mission file at `dekspec/missions/MSN-NNN-*.md`.
2. If the Mission file does not exist, log a non-blocking warning identifying the missing file path and skip the append. Do **not** refuse.
3. If the Mission file exists, append a row to the Mission's Intent queue section: `| INT-NNN | <title> | <type> | LOCKED |`. The Mission's own `/write-mission --review` handles richer queue updates; this is a one-line append.

### Step 3: Promote

1. Flip Status to `LOCKED`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from <current-status> --to LOCKED --note "<note>" --engineer <engineer-or-agent>`, where `<current-status>` is the Intent's status before this step (`MERGED` under Path A; `TESTPASS` / `ACCEPTED` / `IMPLEMENTING` under Path B) and `<note>` records the path taken — Path A: `"Merged to main; MERGED to LOCKED via /write-intent --lock"`; Path B: `"Locked via ADR-017 Path B — all downstream WS/IC/IBs >= ACCEPTED"`. Surface stderr on non-zero exit and STOP.
2. Move the Intent's row in `dekspec/intent-index.md` from the **Active queue** table to the **Archive** table. The Archive row uses the smaller column set (Intent / Title / Status / Superseded-By / Merged date / Mission / Notes); copy the title and mission from the Active row, set Status `LOCKED`, set Merged date to today's date, leave Superseded-By empty. (Cross-table move with a column-shape change — hand-authored.)
3. Surface a closing summary: the Intent is locked; its file remains the executed-record. If the Intent had a Mission, mention the Mission's Intent queue was updated.

**End of Lock Mode.**
