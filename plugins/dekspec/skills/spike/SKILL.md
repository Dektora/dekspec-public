---
name: spike
description: Test a falsifiable feasibility question with a bounded experiment.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Write Edit Bash
argument-hint: "[request or target]"
---

Formulate the claim, measurement and pass/fail criterion before experimenting.
Read prior spike records and existing implementation evidence. Use the requested
budget or a proportionate bounded experiment; do not expand into production work.
Place disposable code/results in an isolated scratch/worktree area and keep
runtime data external. Never commit secrets or replace production behavior.

Run the smallest useful experiment, record environment, exact commands, results,
limits and what the result does/does not establish. A failed hypothesis is a useful
outcome. Stop at the budget; distinguish inconclusive from infeasible. Preserve
findings without forcing immediate spec authoring. If implementation is requested,
prepare the approved core contract rather than shipping scratch code.
Examples: “can this parser meet the latency budget?”; “test whether this API works”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
