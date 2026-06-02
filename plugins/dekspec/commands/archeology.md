---
description: Drive the brownfield spec-gap recovery workflow — invokes the /archeology skill. Scans an orphaned code surface, finds files no LOCKED Intent claims, drafts a retroactive Intent skeleton, cross-references a symbol to its likely contract surface, and routes ratification through /dekspec:write-intent.
allowed-tools: Skill
argument-hint: [--help] [--teaching] [--scan PATH] [--propose-intent PATH] [--coverage-gap-report] [--ratify DRAFT_PATH --as INT_ID] [--cross-ref SYMBOL]
disable-model-invocation: false
---

Invoke the `archeology` skill to drive the brownfield spec-gap recovery workflow.

## Steps

1. Invoke the `archeology` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill handles its own mode dispatch (`--scan`, `--propose-intent`, `--coverage-gap-report`, `--ratify`, `--cross-ref`, `--teaching`, `--help`).
