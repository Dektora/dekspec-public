# Grep-Loop Review-Fix Workflow (dekspec-owned)

> **Provenance.** Adapted from the `grep-loop-review-workflow` skill by David Ondrej / Michael Shimeles (interview notes), **MIT-licensed**. This is dekspec's own vendored copy — bundled in the plugin so consumers who `claude plugin install dekspec@dekspec` get it, and free to modify for the dekspec review pipeline. The generic discipline below is the MIT source; the **dekspec bindings** section wires it to the delivery review (`/dekspec:review-pr` → fix → re-verify → re-review).

## Overview

An auto-research-style loop for code review on a **small PR**:

1. Create / have a small PR.
2. A review tool, AI reviewer, or human inspects it.
3. Feed the review back to the coding agent.
4. The agent fixes the feedback.
5. Review again.
6. Repeat until the PR is clean and tests pass, or it is blocked by a decision that needs a human.

The loop works best when the PR is small and the success condition is clear. Do **not** run it on a massive PR or an unclear product decision — split first.

## The review-fix discipline (each rule guards a known failure mode of an over-eager agent)

1. **Read the PR diff first** — before editing anything. The fix targets the diff that exists, not a remembered one.
2. **Fix only real, relevant findings** — no unrelated rewrites. A finding that is a false positive or out of this PR's scope is **recorded and skipped**, not "fixed."
3. **Add or update a test for each bug fix** when feasible — the loop needs objective checks, not vibes.
4. **Run the relevant tests / typechecks** before landing the follow-up commits.
5. **End with a summary** listing the resolved review items (and any findings deliberately skipped, with the reason).
6. **Stop only when the PR is clean, or when blocked by a decision that needs a human.** Then re-review.

## Pre-flight

Before starting the loop, ask: *is this PR too large for a reliable review loop?* A large diff degrades both the reviewer and the fixing agent. If yes, split the PR first.

## Human guardrails

- Use the loop on **small** PRs.
- Reviewers produce false positives — rule 2 is what stops the agent acting on them.
- Agents over-fix and rewrite unrelated code — rules 1 + 2 bound the blast radius.
- A clean review is not proof the product is valuable; it only means this diff looks clean.

## Common pitfalls

1. **Thousands of lines in one PR** — reviewer + agent both lose accuracy.
2. **No tests** — the loop needs objective checks, not just vibes.
3. **Blindly accepting every review comment** — some are wrong or irrelevant.
4. **No stop condition** — define "done" before starting.

---

## dekspec bindings (delivery review, ADR-057 / ADR-058)

When `/dekspec:review-pr` records a `fail` verdict for an IB in a delivery (one branch / worktree / pull request), bind the generic discipline above to these specifics:

- **Seed with located findings.** Run `/code-review <effort> --comment <PR-#>` so line-anchored findings sit beside the review's vetoing lenses (the `fail` verdict's notes). Pick `<effort>` from `/dekspec:review-pr`'s size pre-flight: `medium` by default, `high`/`max` for a dense diff.
- **The builder fixes, inside a counted attempt.** Open `dekspec ib attempt <IB> start`, land the fix as follow-up commits on the delivery branch (add commits, don't replace them), and close with `dekspec ib attempt <IB> end --outcome passed` (or `failed`). A fix that needs a change outside Scope, to a protected surface, or to an acceptance condition is an escalation (ADR-055), not a fix: record it with `dekspec ib block <IB> --reason scope-expansion` (or `contract-conflict`, `acceptance-invalid`) and a `--detail`, and stop.
- **Re-verify, then re-review.** Every fix commit changes the head content, so prior evidence is stale: run `dekspec delivery verify`, then re-run `/dekspec:review-pr` for a fresh verdict (rule 6's "review again"). Verdicts on untouched IBs carry forward only if the fix touched none of their reviewed surfaces.
- **Bounded by the engine.** The loop's stop condition is the engine's attempt accounting (`execution:` limits in `.dekspec/config.yaml`): exhausted attempts, a stall or no progress leave the IB BLOCKED (exit 3) and completion refused until an operator records `dekspec ib unblock --decision …`. Do not reset or work around the count.
- **Never merges (ADR-026).** The loop ends at a `pass` verdict or a human decision; landing stays with `/dekspec:land-intent`'s operator-confirmed merge.

## Verification checklist

- [ ] PR is small enough to review reliably.
- [ ] Agent read the diff before editing.
- [ ] Agent fixed only relevant findings (false positives recorded + skipped).
- [ ] Tests / typechecks passed or blockers were stated.
- [ ] Final summary lists resolved + deliberately-skipped review items.
- [ ] (dekspec) each fix round ran inside a counted attempt, was re-verified with `dekspec delivery verify` and re-reviewed; nothing merged without the operator.
