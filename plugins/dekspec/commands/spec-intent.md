---
description: Specification phase-executor — invokes the /spec-intent skill. Drives an Intent (INT-NNN) from DRAFT to authorized-for-execution by sequencing /write-intent --analyze/--accept/--decompose, /write-ibs (and /write-ws, /write-ic only where they add something distinct) and `dekspec ib lint` / `dekspec ib propose` / `dekspec ib accept`, ending with the Intent ACCEPTED and each of its IBs ACCEPTED. Stops at the coding boundary; never starts execution. The specification-side sibling of /orchestrate-coding-session.
allowed-tools: Skill
argument-hint: [--help] <INT-NNN | path/ID of Intent>
disable-model-invocation: false
---

Invoke the `spec-intent` skill to drive an Intent from DRAFT to authorized-for-execution.

## Steps

1. Invoke the `spec-intent` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill sequences the existing authoring skills and the `dekspec ib` authorization verbs, and stops at the coding boundary — it never starts execution. The Intent's `--accept` and each IB's `dekspec ib accept` stay engineer-gated.
