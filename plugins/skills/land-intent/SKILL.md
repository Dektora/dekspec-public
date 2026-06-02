---
name: land-intent
description: Review-and-land phase-executor for an Intent (INT-NNN). Drives every IB-aggregate PR the Intent produced through the two-tier review pipeline to a landed state — fires the REVIEW_PR trigger, lets the REVIEW_PR_FAIL grep-loop run to a terminal verdict, and on GO presents the squash-merge for explicit operator confirmation. Never auto-merges (ADR-026 RECOMMEND-only). The review-side sibling of /exec-coding-session.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] <INT-NNN | path/ID of Intent>
related_skills: [review-pr, exec-coding-session, orchestrate-intent, spec-intent]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/...` reference the consumer-vendored layout. Pip-only installs resolve via `dekspec resource ...`. See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md).

Review-and-land phase-executor for an Intent. The review-side counterpart to `/exec-coding-session <intent>`: where that skill executes *all* of an Intent's beads, `land-intent` drives *all* of the Intent's IB-aggregate PRs through the review pipeline to a landed state, in dependency order, from one launch — reusing the existing trigger + `review-pr` + `REVIEW_PR_FAIL` machinery unchanged. It is a thin orchestrator: its only net-new behavior is the per-Intent PR enumeration/ordering and the operator-confirmed merge gate.

## Starter Prompt

```prompt
/dekspec:land-intent INT-129

Drive every open PR for INT-129 through review to a landed state. For each PR:
fire the review trigger, run the fix-loop to a terminal verdict, and on GO show
me the squash-merge to confirm. Stop and ask if any PR comes back NO-GO.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Land Mode**.

- **Help mode** — `--help` flag. See **Help Mode**.
- **Land mode** — default (an `INT-NNN` / path positional). Proceed to **Land Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:land-intent"
one_line:   "Drive all of an Intent's IB-aggregate PRs through review to operator-confirmed merge."
modes:
  - { flag: "", args: "<INT-NNN>", description: "Land mode — enumerate the Intent's PRs, review-and-land each in dependency order." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:land-intent INT-129"
  - "/dekspec:land-intent --help"
```

## Land Mode

### Phase 1 — Enumerate & order the Intent's PRs

Identify the target Intent `INT-NNN`. Build the ordered set of its open IB-aggregate PRs using only existing surfaces (no new tooling):

1. Resolve the Intent's beads/IBs and their PRs via the `Resolves IB-NNN` PR-body convention (ADR-025) + bead `external_ref` linkage — `gh pr list` for the open set, `git` for branch state.
2. Order the PRs by dependency using the `br` blocked-by topology — the same `br`-driven dependency walk `/exec-coding-session` Phase 1 performs.

### Phase 2 — Review-and-land each PR (in order)

For each PR, in dependency order:

1. **Trigger review** — `dekspec review trigger review-pr <PR-#>` (INT-124). This enters the `REVIEW_PR` state and auto-invokes `/dekspec:review-pr` (INT-107).
2. **Let the fix-loop run** — a NO-GO routes through the `REVIEW_PR_FAIL` action-handler (INT-115), which seeds `/code-review --comment`, fixes real findings, and re-fires `review-pr` until a terminal verdict. Do not hand-drive it.
3. **Act on the terminal verdict** at the **Merge Gate** below.

### Merge Gate

**MERGE GATE — never merge a PR without explicit operator confirmation.** This skill is RECOMMEND-only at landing per **ADR-026**; unattended merge-on-GO is the AUTO graduation tier, gated on the INT-117 calibration corpus, and is out of scope here.

- **GO** → present the squash-merge to the operator (`gh pr merge <PR-#> --squash --delete-branch`) and **wait for an explicit confirmation keystroke**. The skill **does not merge** until the operator confirms. After a confirmed merge, advance to the next PR.
- **NO-GO / INSUFFICIENT_EVIDENCE** → **stop on this PR** and hand control back to the human with the pipeline state intact; do **not** silently advance to the next PR.

### Phase 3 — Roll-up

When every PR is landed (or the operator halts), report a per-PR outcome roll-up for the Intent (landed / stopped-NO-GO / pending), and name the next action.

## Common Pitfalls

- Don't merge on a GO verdict automatically — always present the merge and wait for the operator's confirmation keystroke (ADR-026); this skill never merges on its own.
- Don't reimplement the review or fix-loop — `land-intent` only sequences `dekspec review trigger` + `review-pr` + the `REVIEW_PR_FAIL` handler, which already exist; adding a parallel loop drifts from the canonical pipeline.
- Don't advance past a NO-GO PR — stop and hand back; silently moving to the next PR buries an unresolved failure.
- Don't ignore dependency order — landing a dependent PR before its prerequisite breaks the branch graph; order by the `br` blocked-by topology.

## Verification Checklist

- [ ] Every open IB-aggregate PR for the Intent was enumerated (gh/git/br), none missed.
- [ ] PRs were processed in `br` dependency order.
- [ ] Each PR was driven via `dekspec review trigger review-pr` → `review-pr` → terminal verdict (no hand-rolled review).
- [ ] No PR was merged without an explicit operator confirmation keystroke (ADR-026).
- [ ] Every NO-GO / INSUFFICIENT_EVIDENCE PR stopped the run and was handed back, not skipped.
- [ ] A per-Intent outcome roll-up was reported at the end.

## Closing Step

After the run, `dekspec audit relink` against the repo root to restitch any backlinks touched by merges.
