---
name: audit-codebase
description: Assess architecture and module depth with concrete, ranked evidence.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash Agent
argument-hint: "[request or target]"
---

Scope to the requested area or changed production code; walk the entire repo
only when asked. Read `references/architecture_principles.md` before analyzing
interfaces, information hiding, leaked policy, change locality, error complexity,
and test seams. Compare callers and implementations, not file size alone.

The optional `scripts/depth_classify.py` helper provides quantitative observations.
Read its help before use. Depth bands and interface/LOC ratios are diagnostics,
not quality objectives, automatic refactors, or proof of good architecture.
Identify behavior that a deeper module could hide behind a simpler interface;
name consequences at callers and the checks that would protect behavior.

Rank findings by impact and strength of evidence: location, observed problem,
consequence, alternative, uncertainty, and next action. Name each finding's family
code from `references/architecture_principles.md` (e.g. `IH-LEAKED-INVARIANT`);
when no listed code fits, form one from the family prefix and a short uppercase
slug. Separate findings from proposed improvements. Default output is a concise report in chat; write a report
or HTML only when requested. Do not mutate audited source during analysis.
This is a workflow instruction, not an enforced sandbox: Bash can write files.

For requested deepening, hand the bounded evidence to the operator for the
optional `/deepen` step, which they start as `/dekspec:deepen`. Do not silently
repair or require that tool for this audit. Spec linkage
checks remain core's audit responsibility. If a helper cannot parse a language,
state that limitation and inspect the relevant interfaces directly.
Examples: “audit the parser architecture”; “review this diff for shallow modules”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
