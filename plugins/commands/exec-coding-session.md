---
description: Dispatch a parallel coding session — invokes the /exec-coding-session skill (renamed from /run-coding-session in INT-098). Orchestrates parallel sub-agents in isolated worktrees over an unblocked bead set.
allowed-tools: Skill
argument-hint: [<ib-path-or-id> | --package <sha-or-path> | --confirm-dispatch | --dry-run | --help] [optional engineer guidance]
disable-model-invocation: false
---

Invoke the `exec-coding-session` skill to orchestrate a parallel
coding session.

## Steps

1. Invoke the `exec-coding-session` skill via the Skill tool,
   forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill handles all
   dispatch logic (Phase 1–5: discover/claim, dispatch, collect,
   land-the-plane, newly-unblocked).

## Naming note

Renamed from `/run-coding-session` → `/exec-coding-session` in
INT-098 (v0.92.0+). The old slash command no longer exists; the
skill body is unchanged.
