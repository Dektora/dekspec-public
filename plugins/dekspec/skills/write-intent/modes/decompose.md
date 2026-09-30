# Decompose Mode (author the child IBs; Status stays ACCEPTED)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Refuses if Status is not `ACCEPTED`. Produces the Intent's Implementation Briefs — delegated IBs whose `**Parent:**` is this Intent (ADR-056). It produces nothing else: no code beads, no direct work items, no status change. An Intent completes from its IBs (ADR-057), so the IBs are the whole decomposition.

> **Inline execution.** This mode runs in the parent context so it can invoke `/write-ibs` directly.

### Step 1: Validate

1. File exists; Status is `ACCEPTED`.
2. Open Issues has no unresolved `P1` entry and no unresolved over-cap `P2` finding.
3. For `type: bug`: the `Reproduction:` block (or the Non-Reproducible Waiver) is populated and concrete.

No branch or worktree is required to decompose. Authoring IBs is a spec change; the delivery worktree (ADR-048 / ADR-058, `/dekspec:use-worktrees`) is set up when execution starts.

### Step 2: Author the IBs

Take the candidate-IB list `--analyze` recorded under **Layer impact analysis** as a starting point, not a contract — re-cut it if the code says otherwise. For each IB, invoke `/write-ibs` with this Intent as input (it authors delegated IBs from an Intent, sets `**Parent:** INT-NNN`, references obligations rather than copying them, and writes the `## Acceptance` block). A single mechanical IB may instead be scaffolded with `dekspec ib new <slug> --parent INT-NNN` and filled per the IB template.

Obligations on the set:

- **Scope inside the Intent.** Every IB's Scope globs lie within the Intent's `Components affected:`. A needed path outside it is an `--amend` on the Intent first.
- **Outcome covered.** Together the IBs' acceptance conditions deliver the Intent's Desired Outcome; the Intent's Verification (run later by `dekspec intent verify`) is the cross-IB proof.
- **Bug reproduction.** For `type: bug`, one IB's acceptance names the failing reproduction test — the Intent's ADR-029 Outcome Verification test, written by `/write-tests` before authorization with a `Basis:` for its expected result and genuinely red on `dekspec ib floor`, then oracle-reviewed by `/dekspec:review-ib` before `dekspec ib accept` protects it (ADR-062). Substitute that test path for the `<reproduction-test-path-from-IB-1>` placeholder in the Verification block and in `## Outcome Verification`.
- **Shared shapes pinned once (ADR-054 as revised by ADR-056).** A type or contract several IBs need lives in one home — an IC, a WS section, or one IB's local obligation that the others reference as `IB-NNN §O-n` — and reaches each IB through `dekspec ib context`.

### Step 3: Size Re-Check

Count the IBs produced and the components they actually touch. If either exceeds its cap (≤ 3 IBs, ≤ 3 components), the decomposition shows the Intent is over-cap: record the P2 "re-split before acceptance" open issue, run `--amend` (Status cascades to DRAFT), and resolve it via [`_lib/oversized_splitting.md`](../../_lib/oversized_splitting.md). Leave the drafted IBs at DRAFT so the split can re-parent or discard them.

### Step 4: Record

1. Replace the L3 row of **Layer impact analysis** with the list of child IBs (`IB-NNN — <title>`); the authoritative relation is each IB's `**Parent:**` field, which `dekspec intent complete` reads.
2. Bump Modified and append an Amendment Log row: `| <date> | Substantive | Decomposed into N IBs (IB-…); Status holds ACCEPTED. | <engineer-or-agent> |`.
3. Surface the next step, per IB in the one authoring order (ADR-062): write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/dekspec:write-tests` (mandatory for every `pytest:` condition; genuine red on `dekspec ib floor`) → `/dekspec:review-ib` (the oracle review; a passing floor review is a `Floor reviewed:` Amendment Log row) → `dekspec ib accept` (`/write-ibs --accept`). A pre-start change to the tests repeats the review before `dekspec ib baseline`. Then execute them (`/dekspec:implement`, or `dekspec ib ready` + `/dekspec:orchestrate-coding-session`). When every child IB is COMPLETE, run `/write-intent --lock` to complete the Intent.

**End of Decompose Mode.**
