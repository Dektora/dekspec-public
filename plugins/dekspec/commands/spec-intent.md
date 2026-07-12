---
description: Specification phase-executor — invokes the /spec-intent skill. Drives an Intent (INT-NNN) from DRAFT to ready-for-coding by sequencing /write-intent --analyze/--accept/--decompose + /write-ws, /write-ic, /write-ibs and the architectural-interview prompts, leaving the Intent at IMPLEMENTING. Stops at the coding boundary; never dispatches a coding session. The specification-side sibling of /orchestrate-coding-session.
allowed-tools: Skill
argument-hint: [--help] <INT-NNN | path/ID of Intent>
disable-model-invocation: false
---

Invoke the `spec-intent` skill to drive an Intent from DRAFT to ready-for-coding.

## Steps

1. Invoke the `spec-intent` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill sequences the existing authoring skills (`/write-intent --analyze/--accept/--decompose`, `/write-ws`, `/write-ic`, `/write-ibs`) and stops at the coding boundary — it never dispatches `/orchestrate-coding-session`. `--accept` stays engineer-gated.
