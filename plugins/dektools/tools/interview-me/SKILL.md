---
name: interview-me
description: Resolve decision-relevant uncertainty before authoring or implementing work.
mode: lite
interaction: natural-language
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: "[request or target]"
---

Read the request and discoverable code/spec answers first. Identify the few
uncertainties that materially change the outcome. Ask concise questions in
batches when independent; follow up only when an answer changes the next branch.
Offer concrete tradeoffs, not an exhaustive questionnaire. Respect settled user
preferences and say when available evidence already answers a question.

Stop when the intended artifact can be authored reliably. Summarize decisions,
remaining uncertainty and the next authoring action. Do not create speculative
artifact chains merely to keep interviewing. If the user asks to proceed, act
within the available authorization and current core methodology.
Examples: “interview me about this design choice”; “help clarify checkout behavior”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
