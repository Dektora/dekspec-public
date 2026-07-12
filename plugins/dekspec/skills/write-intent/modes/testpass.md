# Testpass Mode (IMPLEMENTING → TESTPASS)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Refuses if Status is not `IMPLEMENTING`.

*Note: the `TESTFAIL` Status flip retired 2026-05-25 (E3 audit — neither the status nor the round-trip back to IMPLEMENTING ever fired across 99 Intents). The TESTFAIL records section remains as a captured-failure log; on a failed `--testpass` run we append a record and leave Status at `IMPLEMENTING` so the engineer's fix-then-rerun loop is naturally captured.*

### Step 1: Validate

1. File exists; Status is `IMPLEMENTING`.
2. Every bead listed in the Intent's Layer impact analysis is `closed` per `br show <bead-id>`. If any bead is still open or in-progress, refuse with the open bead IDs surfaced.
3. The current branch is `int/INT-NNN-<slug>` matching the Intent's `Branch` field.

### Step 2: Diff Confinement

Compute the union of files changed on the Intent branch since it diverged from its base (typically `main`):

```
git diff --name-only $(git merge-base HEAD main) HEAD
```

For each changed file, check that at least one glob in `Components affected:` matches it. Resolve named components via the CLAUDE.md §Component → File-Glob Map. Inline globs are matched directly.

**Implicit lifecycle admit-set.** A file is also admitted (no TESTFAIL) if it matches any glob in:

```
IMPLICIT_LIFECYCLE_GLOBS = [
  "dekspec/**",   # spec-graph mutations driven by the Intent lifecycle itself (Intent file, IB, indexes, AE backlinks via dekspec relink)
  ".beads/**",    # bead-tracker housekeeping (br claim/close emits jsonl writes)
  ".dekspec/**",  # consumer-side cache + lifecycle DB
]
```

These paths are mutated as necessary side-effects of running the Intent lifecycle itself and never represent behavioral scope. Expanding `Components affected:` to declare them would blow the size cap and add ceremony, not safety. Diff confinement admits the file if it matches ANY of: (a) a glob in `Components affected:`, OR (b) a glob in `IMPLICIT_LIFECYCLE_GLOBS`. The canonical implementation is `tooling/dekspec/diff_confinement.py::check_diff_confinement` — mirror its semantics. (This mirrors the convention dekfactory's drift gate already implements server-side.)

If any file is out-of-scope:

1. Append a TESTFAIL record with `Failed check: diff-confinement`, `Detail: <list of out-of-scope files>`, today's date.
2. Status stays at `IMPLEMENTING` (the `TESTFAIL` Status flip retired 2026-05-25). The TESTFAIL record above is the persisted captured-failure log.
3. Surface the offending files and stop. The engineer either (a) reverts the out-of-scope edits or (b) revises `Components affected:` to legitimately include them and re-runs `--analyze` (which will re-validate against the size cap), then re-runs `--testpass`.
4. **Run `/dekspec:debug-testfail` to investigate.** The TESTFAIL record above seeds the persistent debug-state file at `dekspec/debug/<slug>.md`; the debug skill runs Agans' nine rules on the captured symptom with observation/theory/disproved audit-trail discipline and survives a context reset via `/dekspec:debug-testfail continue <slug>`.

If diff confinement passes, proceed to Step 3.

### Step 3: Verification Predicate Evaluation

For each named check in the Verification block:

0. **Manual checks (ds-cjqi).** If the check carries `manual: true`, do **NOT** execute its `cmd:`. Require a non-empty `manual_rationale:` on the check — if missing, refuse and stop (surface the check name; the engineer adds the rationale or removes `manual:`). The canonical enforcement lives in `tooling/dekspec/constraint_compiler/parser.py::_extract_intent_verification`, which raises on `manual: true` without a rationale — mirror its semantics. For a valid manual check, record a per-check result row of `MANUAL-TESTPASS` carrying the rationale (instead of exit-code/duration), then continue to the next check. Manual checks never fail and never trigger the fast-fail below; they are attested, not executed. Use for predicates needing infrastructure the local box lacks (e.g. a GPU smoke stack on a CPU dev box).
1. Run the `cmd:` from the repo root.
2. Capture exit code + first 50 lines of stdout + first 50 lines of stderr.
3. Record `name`, `cmd`, `exit-code`, `duration` in a per-check result row (kept in memory; written to the Verification block only on completion).

If **any** check exits non-zero, stop on first failure (do not run subsequent checks; fast-fail is the correct semantics — a regression on the test suite makes downstream NFR checks meaningless):

1. Append a TESTFAIL record with `Failed check: <name>`, `Detail: <exit code, last few lines of stderr>`, today's date.
2. Status stays at `IMPLEMENTING` (the `TESTFAIL` Status flip retired 2026-05-25). The TESTFAIL record above is the persisted captured-failure log.
3. Surface the failing check + captured stderr. The engineer fixes via the existing bead chain (existing or new beads), then re-runs `--testpass`.
4. **Run `/dekspec:debug-testfail` to investigate.** The TESTFAIL record above seeds the persistent debug-state file at `dekspec/debug/<slug>.md`; the debug skill runs Agans' nine rules on the captured symptom with observation/theory/disproved audit-trail discipline and survives a context reset via `/dekspec:debug-testfail continue <slug>`.

If **all** executable checks exit zero:

1. For each check, append a per-check pass entry into the Verification block (the engineer can verify the run record). Manual checks appear as `MANUAL-TESTPASS: <manual_rationale>` rows.
2. Flip Status to `TESTPASS`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from IMPLEMENTING --to TESTPASS --note "All Verification checks green; diff confinement clean; transitioned IMPLEMENTING to TESTPASS via /write-intent --testpass" --engineer <engineer-or-agent>` (surface stderr on non-zero exit and STOP).
3. Update `dekspec/intent-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/intent-index.md --id INT-NNN --status TESTPASS` (surface stderr on non-zero exit).
4. Surface the next-step message: merge `int/INT-NNN-<slug>` into `main` and then run `/write-intent --lock <path>`.

**End of Testpass Mode.**
