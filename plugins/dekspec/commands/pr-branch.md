---
description: Build a clean PR branch by filtering out spec-only commits (Intent/WS/IB/ADR/IC/AE status bumps, index reconciliation, pm STATE/LEDGER) so code reviewers see only the implementation diff — invokes the /pr-branch skill. Mixed code+spec commits are cherry-picked with the spec-only paths stripped. Pure git; emits `<branch>-pr` ready to push.
allowed-tools: Skill
argument-hint: [--help] [target-branch]
disable-model-invocation: false
---

Invoke the `pr-branch` skill to build a clean PR branch — classifying each
commit ahead of the target (default `main`), dropping spec-only commits,
stripping spec-only files out of mixed commits, and leaving a `<branch>-pr`
branch with zero DekSpec artifact churn in the diff.

## Steps

1. Invoke the `pr-branch` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill is pure git: it never
   modifies the original branch, classifies each commit ahead of the target as
   CODE / SPEC_ONLY / MIXED, builds `<branch>-pr` from the target, cherry-picks
   CODE commits and the code half of MIXED commits (stripping the spec-only
   paths), verifies the resulting diff carries no transient-spec paths, and
   reports the commit/file counts plus the next step (`git push` + `gh pr create`).
   On any cherry-pick conflict it aborts and reports — never forces.
