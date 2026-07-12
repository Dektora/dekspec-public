---
description: Review-and-land phase-executor — invokes the /land-intent skill. Drives every IB-aggregate PR an Intent produced through the two-tier review pipeline to a landed state (fire REVIEW_PR trigger → review-pr → REVIEW_PR_FAIL grep-loop → operator-confirmed squash-merge). Never auto-merges (ADR-026). The review-side sibling of /orchestrate-coding-session.
allowed-tools: Skill
argument-hint: [--help] <INT-NNN | path/ID of Intent>
disable-model-invocation: false
---

Invoke the `land-intent` skill to review-and-land all of an Intent's PRs.

## Steps

1. Invoke the `land-intent` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill enumerates the Intent's IB-aggregate PRs in dependency order, drives each through `review-pr` + the `REVIEW_PR_FAIL` grep-loop to a terminal verdict, and on GO presents the squash-merge for explicit operator confirmation — it never merges on its own (ADR-026 RECOMMEND-only).
