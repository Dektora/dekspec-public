---
description: Write a verifiable goal contract for a long-running autonomous Claude Code run — invokes the /write-goal-loop-contract skill. Turns a fuzzy "go do this for a while" into a 4-part contract (Objective / Constraints / Validate command / verifiable Stop condition) with reward-hacking + scope-creep guards, then names the right driver (/loop, background agent, /schedule, or orchestrate-coding-session). A spec with a stop condition, not a run-forever button.
allowed-tools: Skill
argument-hint: [--help] [task or intent to turn into a goal contract]
disable-model-invocation: false
---

Invoke the `write-goal-loop-contract` skill to turn a task into a verifiable goal contract for a
long-running autonomous run.

## Steps

1. Invoke the `write-goal-loop-contract` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill emits a 4-part contract
   (Objective / Constraints / Validate command / verifiable Stop condition) with
   explicit reward-hacking + scope-creep forbiddance, names what to read first,
   and recommends the driver (`/loop`, a background agent, `/schedule`, or
   `/dekspec:orchestrate-coding-session` for a construction run; always a branch, never
   `main`). If the ask has no verifiable stop condition, the skill pushes back and
   helps narrow it rather than drafting a loose contract.
