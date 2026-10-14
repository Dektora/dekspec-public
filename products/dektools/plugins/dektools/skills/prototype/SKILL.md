---
name: prototype
description: Explore a design or interaction shape using explicitly disposable code.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Write Edit Bash
argument-hint: "[request or target]"
---

Identify the design uncertainty and what the user needs to see or try. Reuse
existing examples and choose a small, bounded demonstration. Keep disposable
implementation in an isolated scratch/worktree area, away from production code;
preserve existing prototype records. State shortcuts and unsupported behaviors.

Build and exercise enough of the shape to answer the design question. Record
feedback, alternatives, costs and limitations. A demo is not production readiness
or evidence of meeting untested nonfunctional requirements. Stop at the supplied
or proportionate budget. Retain useful findings without mandatory artifact creation.
If the user elects to ship the design, prepare core's approved executable contract
and implement it through core; do not silently promote the throwaway code.
Examples: “prototype the proposed API shape”; “show how this interaction would work”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
