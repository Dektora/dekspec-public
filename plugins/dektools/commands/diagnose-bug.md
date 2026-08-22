---
description: Governed pre-spec debugging loop for DekSpec — invokes the /diagnose skill. Builds a fast, deterministic, agent-runnable PASS/FAIL repro signal FIRST (before any hypothesizing), logs the working diagnosis to the gitignored `dekspec/.scratch/diagnostics/` zone, then minimizes → hypothesizes → instruments → fixes → regression-tests, and promotes the durable repro into a bug Intent's `### bug — Reproduction` section (via /write-intent (type: bug)) and seeds /write-tests as a red-first outcome test.
allowed-tools: Skill
argument-hint: [--help] [--at PATH]
disable-model-invocation: false
---

Invoke the `diagnose` skill to run the governed pre-spec debugging loop —
building a deterministic PASS/FAIL repro signal *before* any hypothesizing,
logging to `dekspec/.scratch/diagnostics/`, then running
minimize → hypothesize → instrument → fix → regression-test and promoting the
durable repro into a bug Intent.

## Steps

1. Invoke the `diagnose` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill builds the deterministic repro signal first (a single agent-runnable command whose exit code is the signal, on the consumer repo's own test/run harness), proves it flips red, logs to `dekspec/.scratch/diagnostics/`, then runs the rest of the loop and promotes the durable repro into a bug Intent via `/dekspec:write-intent (type: bug)` (Reproduction or Non-Reproducible Waiver section) and seeds `/dekspec:write-tests` as the red-first outcome test. Domain-term clarifications route to `/dekspec:write-ggc`.
