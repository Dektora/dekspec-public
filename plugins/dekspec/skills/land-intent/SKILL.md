---
name: land-intent
description: Land a delivery (one branch / worktree / pull request per ADR-058 — a single IB, an Intent's IBs, or a Mission cluster). Sequences `dekspec delivery verify` → /dekspec:review-pr (one verdict per IB) → `dekspec ib complete` per IB → `dekspec delivery check` at the exact head → operator-confirmed merge (ADR-026: never auto-merges) → post-merge `dekspec intent verify` + `dekspec intent complete` for a parent Intent whose IBs are all complete. The landing-side sibling of /orchestrate-coding-session.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] <INT-NNN | IB-NNN | branch | PR-#>
related_skills: [review-pr, orchestrate-coding-session, implement, spec-intent, pr-branch, use-worktrees]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/...` reference the consumer-vendored layout. Pip-only installs resolve via `dekspec resource ...`. See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md).

Land a delivery. A delivery is what one branch, worktree and pull request carries (ADR-048, ADR-058); acceptance stays per IB, and verification and review cover the final integrated head. This skill is a thin sequencer over engine verbs and `review-pr` — the gates are the engine's, not prose.

## Starter Prompt

```prompt
/dekspec:land-intent INT-129

Land INT-129's delivery: verify it at the head, review every IB, complete
them, run the landing gate, and show me the merge to confirm. Stop and hand
back if any IB fails review or the gate does not pass.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Land Mode**.

- **Help mode** — `--help` flag. See **Help Mode**.
- **Land mode** — default (an `INT-NNN`, `IB-NNN`, branch or PR positional). Proceed to **Land Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:land-intent"
one_line:   "Verify, review, complete and land one delivery; merge only on operator confirmation."
modes:
  - { flag: "", args: "<INT-NNN | IB-NNN | branch | PR-#>", description: "Land mode — delivery verify → review-pr → ib complete → delivery check → operator-confirmed merge → Intent completion." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:land-intent INT-129"
  - "/dekspec:land-intent int/INT-129-land-intent"
  - "/dekspec:land-intent --help"
```

## Land Mode

> This is the **manual** landing path: the operator confirms every merge. `/dekspec:implement` performs the same verify → review → complete → check sequence and integrates on its own when the engineer asked for that work to be implemented (ADR-059).

Work on the delivery branch (its worktree, if it has one). For an Intent, the delivery is the branch carrying its IBs — normally `int/<slug>` (`/dekspec:use-worktrees`). Every IB in it must use the `delegated` authority policy; a `legacy` IB cannot complete until adopted (ADR-055).

1. **Verify at the head.** `dekspec delivery verify` — re-runs every included IB's acceptance and the integration command against this head and records the evidence. Commit the execution records it writes (`.dekspec/execution/`). A failure here is fixed before review; the builder fixes inside counted attempts (`dekspec ib attempt <IB> start`, then `dekspec ib attempt <IB> end --outcome passed` or `failed`).
2. **Review each IB.** `/dekspec:review-pr <branch-or-PR>` records one verdict per IB (`dekspec ib review`), from a reviewer who is not a builder of that IB.
3. **Act on the verdicts.**
   - Any **FAIL** → the delivery holds (ADR-058). Run the fix loop in [`_lib/grep_loop_review_workflow.md`](../_lib/grep_loop_review_workflow.md): fix → `dekspec delivery verify` → re-review. The engine's attempt limits bound it; a BLOCKED IB (exit 3) stops the run until an operator records `dekspec ib unblock --decision …`.
   - Any **INSUFFICIENT_EVIDENCE** (no verdict recorded) → stop and hand back.
   - All **PASS** → continue.
4. **Complete each IB.** `dekspec ib complete <IB>` for every IB, on the delivery branch (add `--base <base>` when the delivery is not based on `main` — a stacked or release-branch PR — and pass the same `--base` to `delivery verify` and `delivery check`). It refuses unless evidence and verdict are current, integrity and scope pass, and no blocker is open — do not work around a refusal; fix what it names. Commit the IB status changes and execution records.
5. **Landing gate.** `dekspec delivery check` must pass at the exact head you will merge: the branch is current with its base and every IB is satisfied there. If the base has moved, update the branch, then re-run steps 1–5 (a rebase changes the head content; evidence goes stale). If you rewrite commits (`/dekspec:pr-branch`), run the check again on the rewritten head. CI runs `dekspec delivery check --rerun` independently.
6. **Merge gate.** See **Merge Gate** below.
7. **Complete the parent Intent (post-merge).** On the base branch after the merge, for a parent Intent whose child IBs (`**Parent:** INT-NNN`) are now all COMPLETE: `dekspec intent verify INT-NNN` (runs its Verification commands and records outcome evidence), if it has manual verification entries, an independent attestation in the **`verifier`** role ([`_lib/agent_roles.md`](../_lib/agent_roles.md) — `dekspec resource role verifier`, by someone who built none of its IBs) recorded as `dekspec intent review INT-NNN --reviewer <name> --actor <name> --verdict pass --policy-revision <N>` (or `--verdict fail`), then `dekspec intent complete INT-NNN`. If child IBs remain in other deliveries, report that and leave the Intent ACCEPTED.

### Merge Gate

**MERGE GATE — never merge without explicit operator confirmation (ADR-026).** Recording verdicts and completing IBs never merges anything.

- Gate passed → present the merge (e.g. `gh pr merge <PR-#> --squash --delete-branch`, or the repo's equivalent) and **wait for the operator's explicit confirmation**. This skill does not merge until the operator confirms. A squash merge keeps the content, so the evidence fingerprint is unchanged.
- Gate not passed, a FAIL verdict, or INSUFFICIENT_EVIDENCE → **stop and hand back** with the gate output; do not merge and do not skip to the next delivery.

### Roll-up

Report per IB: verdict, completion, and the `dekspec delivery check` result; then the merge outcome, the Intent's state, and the next action (e.g. `/dekspec:use-worktrees --cleanup` after the merge).

## Common Pitfalls

- Don't merge on your own — present the merge and wait for the operator (ADR-026).
- Don't hand-edit a status to COMPLETE — only `dekspec ib complete` and `dekspec intent complete` write it (the audit catches a COMPLETE IB without a completion record).
- Don't trust evidence across a commit — any content change after `dekspec delivery verify` stales it; re-verify, and re-review when a reviewed surface changed.
- Don't advance past a FAIL or a blocked IB — a review failure on one IB holds the whole delivery.

## Verification Checklist

- [ ] `dekspec delivery verify` passed at the final head and its records are committed.
- [ ] Every IB has a `pass` verdict from a non-builder, recorded at that head (or carried forward across unreviewed surfaces only).
- [ ] `dekspec ib complete` succeeded for every IB in the delivery.
- [ ] `dekspec delivery check` passed at the exact head that was merged.
- [ ] The merge happened only after explicit operator confirmation.
- [ ] A parent Intent with all child IBs COMPLETE was verified and completed with `dekspec intent complete`.

## Closing Step

After the run, `dekspec relink` against the repo root to restitch any backlinks touched by the merge.
