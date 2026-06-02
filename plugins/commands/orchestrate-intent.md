---
description: Guided Intent lifecycle walker — invokes the /orchestrate-intent skill. Drives an Intent (INT-NNN) from its current status to LOCKED one transition at a time, asking the engineer to confirm each step ([accept] / [decompose] / [lock] / etc.). Engineer-in-the-loop by default; --auto walks the same lifecycle without prompts.
allowed-tools: Skill
argument-hint: [--help | --teaching | --auto | --status | --verify] [description or path/ID of Intent]
disable-model-invocation: false
---

Invoke the `orchestrate-intent` skill to walk an Intent through its lifecycle.

## Steps

1. Invoke the `orchestrate-intent` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill handles its own mode dispatch (`--auto`, `--status`, `--verify`, `--teaching`, `--help`, default interactive mode).
