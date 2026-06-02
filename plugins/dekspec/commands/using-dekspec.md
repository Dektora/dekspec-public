---
description: Onboarding entry point for DekSpec — invokes the /using-dekspec skill. Scaffolds the artifact tree, toggles the No Specless Edits guardrail, and renders the skill catalog. Merges the legacy /spec-mode, /dekspec-skills, and /dekspec-init surfaces (INT-096).
allowed-tools: Skill
argument-hint: [--init [--at PATH] [--force] [--methodology lite|team|full] [--profile lite|full]] [--spec-mode --on|--off|--status] [--catalog] [--help]
disable-model-invocation: false
---

Invoke the `using-dekspec` skill to onboard, scaffold, or list the skill catalog.

## Steps

1. Invoke the `using-dekspec` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill handles its own mode dispatch (`--init`, `--spec-mode`, `--catalog`, `--help`, default onboarding mode).
