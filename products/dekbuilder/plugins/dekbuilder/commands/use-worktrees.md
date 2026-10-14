---
description: Create/enter/clean up a delivery-scoped git worktree (int/<slug> for an Intent, msn/<slug> for a Mission) per ADR-048 — invokes the /use-worktrees skill. Bootstraps the worktree, writes the statusline active_worktree hint, and removes it on land. The delivery mechanic for PR-per-Intent / Mission-batch work.
allowed-tools: Bash(bash:*), Read
argument-hint: [--help] [--scope intent|mission] [--slug <slug>] [--cleanup]
disable-model-invocation: false
---

Invoke the `use-worktrees` skill to manage a delivery-scoped git worktree.

## Steps

1. Invoke the `use-worktrees` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. The skill parses `--scope` / `--slug` / `--cleanup` / `--help`, runs `scripts/setup-worktree.sh`, and surfaces the worktree path, branch, statusline-hint path, and the DekSpec-adapted bootstrap checklist.
