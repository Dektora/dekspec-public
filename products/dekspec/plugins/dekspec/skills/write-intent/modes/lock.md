# Complete Mode (ACCEPTED → COMPLETE)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Marks a finished Intent `COMPLETE` through the engine's evidence gate (ADR-057). The `--lock` flag keeps its name for compatibility; Intents never lock (ADR-046).

An Intent is complete when every child IB — every IB whose `**Parent:**` is this Intent — is `COMPLETE` (each through `dekspec ib complete`) and the Intent's `## Verification` block has current passing evidence. Nothing else substitutes: not a merge, not closed tracker items, not a green run recorded elsewhere. Completion checks content, not the branch, so it may run at the delivery head before `dekspec delivery check` or on `main` after the merge.

### Step 1: Run the outcome verification

```
dekspec intent verify INT-NNN
```

It executes every Verification `cmd:` (the ADR-029 outcome test among them) against the current content and records evidence in `.dekspec/execution/INT-NNN/`. On a failure, surface the failing entries and stop; fixing the regression is ordinary work on the relevant IB (a failure is evidence, not a status — there are no TESTFAIL records). An entry marked `manual: true` is not executed; it must carry a `manual_rationale:` and is satisfied only by an independent verdict:

```
dekspec intent review INT-NNN --reviewer <reviewer> --actor <reviewer> --verdict pass --policy-revision <N> --notes "<what was checked>"
```

The attestation is the **`verifier`** role's ([`_lib/agent_roles.md`](../../_lib/agent_roles.md)): the attester works from `dekspec resource role verifier` and passes the policy revision shown in its header (`policy revision <N>`). The reviewer must not be an identity that built any child IB, and the acting identity (`--actor` or `DEKSPEC_ACTOR`) must be the named reviewer.

### Step 2: Complete

```
dekspec intent complete INT-NNN
```

It refuses unless the Intent is ACCEPTED, at least one IB names it as parent, every such IB is COMPLETE, and the outcome evidence (plus any manual verdict) is current for this exact content. On success it writes Status `COMPLETE` and the Amendment Log row itself — do not flip Status by hand (`artifact_ops.py transition` refuses Intent → COMPLETE). On refusal, surface the gate's unmet checks verbatim; `--check-only` evaluates the gate without writing.

### Step 3: Mission Append (if `mission:` is set)

1. Locate the Mission file at `dekspec/missions/MSN-NNN-*.md`. If it does not exist, log a non-blocking warning and skip.
2. Update this Intent's row in the Mission's Intent queue to `COMPLETE` (append `| INT-NNN | <title> | <type> | COMPLETE |` if it is missing). `dekspec intent complete` does not touch the Mission, so this step is not optional; run `/write-mission --review <Mission-path>` for richer queue updates. The Mission completes separately through `/write-mission --complete`.

### Step 4: Index

Move the Intent's row in `dekspec/intent-index.md` from the **Active queue** table to the **Archive** table (Intent / Title / Status / Superseded-By / Merged date / Mission / Notes): Status `COMPLETE`, the completion date in the date column, Superseded-By empty. (Cross-table move with a column-shape change — hand-authored; `dekspec regen-indexes` is the deterministic alternative.)

Surface a closing summary: the Intent is complete, its evidence record, and whether the Mission queue was updated.

**End of Complete Mode.**
