# Lock Mode (→ LOCKED)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Runs from the `main` branch. Three sufficient paths reach `LOCKED` (ADR-017); Step 1 accepts **any one**.

### Step 1: Validate

Current branch must be `main`. Then **Path A, Path B, or Path C** must hold — any one alone is sufficient.

**Path A — forward lifecycle flow:**
1. Status is `MERGED` (engineer-set after merging the Intent branch into `main`).
2. The most recent Verification record matches the most recent `--testpass` Amendment Log entry; if the Verification block was edited since `--testpass`, refuse — the predicate has changed and must be re-run.
3. The Intent file on `main` is identical to the file as it existed when `--testpass` last ran (diff the Verification block; if changed, refuse).

**Path B — downstream artifacts accepted (ADR-017):**
1. Every downstream artifact the Intent produced — the Working Specs, Interface Contracts, and Implementation Briefs named in the Intent's Layer impact analysis — is at status `ACCEPTED` or higher (`ACCEPTED` or `LOCKED`).
2. If any is below `ACCEPTED`, refuse and name the blocking artifact(s).
3. Path B does **not** require `Status: MERGED`, a `--testpass` record, or a branch diff — it is the path for Intents whose work shipped outside the Intent lifecycle via downstream artifacts (Working Specs / Interface Contracts / Implementation Briefs). Beads (L4) are not part of the Path B gate.

**Path C — retroactive post-merge lock (direct-bead Intents):**
1. Status is `MERGED` (engineer-set after the Intent's work merged to `main`).
2. The Intent owns **zero** downstream Implementation Briefs — Path C is the direct-bead sibling of Path B (an Intent *with* downstream WS/IC/IBs uses Path B). If the Intent has downstream IBs, use Path B instead.
3. Every bead in the Intent's `## Layer impact analysis` is `closed`. Run the deterministic gate — `python ../_lib/scripts/artifact_ops.py check-retro-lock <Intent-path>` (surface stderr and refuse on non-zero exit; it names any open bead). This is the real evidence the work landed; it replaces the live-branch `--testpass` that a merged direct-bead Intent can no longer run.
4. The Intent's Verification predicate (every non-`manual` `cmd:`) re-passes when run now from `main`. Run each `cmd:` from the repo root; on any non-zero exit, refuse and surface the failing check.

Path C exists because a zero-downstream direct-bead Intent whose work merged before `--testpass` ran can reach neither Path A (no live `int/` branch) nor Path B (no downstream artifacts), and hand-editing Status to `LOCKED` is guardrail-forbidden.

If no path holds, refuse, naming what each path still needs. The Intent lock-coherence audit rule (L13, AE-003) is a one-sided guard: it fires only when it can positively show Path B is unsatisfied (a LOCKED Intent with a downstream IB below `ACCEPTED`), and stays silent on a zero-downstream LOCKED Intent — so a Path-A or Path-C lock leaves no spurious finding (INT-036 OI-3). The engine and this skill agree.

### Step 2: Mission Append (if `mission:` is set)

If the Intent's `Mission:` field is populated:

1. Locate the Mission file at `dekspec/missions/MSN-NNN-*.md`.
2. If the Mission file does not exist, log a non-blocking warning identifying the missing file path and skip the append. Do **not** refuse.
3. If the Mission file exists, append a row to the Mission's Intent queue section: `| INT-NNN | <title> | <type> | LOCKED |`. The Mission's own `/write-mission --review` handles richer queue updates; this is a one-line append.

### Step 3: Promote

1. Flip Status to `LOCKED`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from <current-status> --to LOCKED --note "<note>" --engineer <engineer-or-agent>`, where `<current-status>` is the Intent's status before this step (`MERGED` under Path A or Path C; `TESTPASS` / `ACCEPTED` / `IMPLEMENTING` under Path B) and `<note>` records the path taken — Path A: `"Merged to main; MERGED to LOCKED via /write-intent --lock"`; Path B: `"Locked via ADR-017 Path B — all downstream WS/IC/IBs >= ACCEPTED"`; Path C: `"Locked via Path C retroactive post-merge — MERGED, zero downstream IBs, all Layer-impact beads closed (check-retro-lock), Verification re-passed from main"`. Surface stderr on non-zero exit and STOP.
2. Move the Intent's row in `dekspec/intent-index.md` from the **Active queue** table to the **Archive** table. The Archive row uses the smaller column set (Intent / Title / Status / Superseded-By / Merged date / Mission / Notes); copy the title and mission from the Active row, set Status `LOCKED`, set Merged date to today's date, leave Superseded-By empty. (Cross-table move with a column-shape change — hand-authored.)
3. Surface a closing summary: the Intent is locked; its file remains the executed-record. If the Intent had a Mission, mention the Mission's Intent queue was updated.

**End of Lock Mode.**
