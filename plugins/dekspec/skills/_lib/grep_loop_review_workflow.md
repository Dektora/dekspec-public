# Grep-Loop Review-Fix Workflow (dekspec-owned)

> **Provenance.** Adapted from the `grep-loop-review-workflow` skill by David Ondrej / Michael Shimeles (interview notes), **MIT-licensed**. This is dekspec's own vendored copy — bundled in the plugin so consumers who `claude plugin install dekspec@dekspec` get it, and free to modify for the dekspec review pipeline. The generic discipline below is the MIT source; the **dekspec bindings** section wires it to the REVIEW_PR pipeline.

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

## dekspec bindings (REVIEW_PR pipeline)

When this loop runs inside the dekspec two-tier review pipeline (the `REVIEW_PR_FAIL` handler driving an IB-aggregate PR; INT-107 / INT-108), bind the generic discipline above to these dekspec specifics:

- **Seed the PR with located findings first.** Run `/code-review <effort> --comment <PR-#>` so findings post as **inline PR comments** (line-anchored feedback, not just the prose verdict). The REVIEW_PR **sidecar** (`context.sidecar_review_path`) supplies the lens verdict + surfaced (≥80) findings; `/code-review --comment` supplies the line-level diff findings — the fixer addresses both. Pick `<effort>` from the pre-flight PR-size signal (`/dekspec:review-pr`'s "PR too large?" check): `medium` default, `high`/`max` for a dense diff.
- **Land follow-up commits on `context.ib_branch`** (rule 4's "land" target) — the IB branch already carries the implementation; addressing review means **adding commits on top**, not replacing.
- **Re-fire `/dekspec:review-pr <PR-#>`** after the fix round (rule 6's "review again").
- **RECOMMEND-only at landing (ADR-026).** The handler **stages** the fix plan + follow-up commits and the operator drives the commits + re-fire; the loop never auto-merges. The same discipline is what an AUTO-mode dispatch would follow once thresholds are committed.

## Verification checklist

- [ ] PR is small enough to review reliably.
- [ ] Agent read the diff before editing.
- [ ] Agent fixed only relevant findings (false positives recorded + skipped).
- [ ] Tests / typechecks passed or blockers were stated.
- [ ] Final summary lists resolved + deliberately-skipped review items.
- [ ] (dekspec) follow-up commits landed on `context.ib_branch`; landing stayed RECOMMEND-only.
