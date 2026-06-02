---
description: Drive the brownfield-ingest workflow — invokes the /brownfield-ingest skill. Runs `dekspec dev ingest` on an inherited markdown document, reviews the confidence-scored classification report, and triages which draft artifacts to promote via the /dekspec:write-* skills.
allowed-tools: Skill
argument-hint: [--help] [--teaching] PATH
disable-model-invocation: false
---

Invoke the `brownfield-ingest` skill to drive the brownfield-ingest workflow.

## Steps

1. Invoke the `brownfield-ingest` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill handles its own mode dispatch (`--teaching`, `--help`, default workflow mode).
