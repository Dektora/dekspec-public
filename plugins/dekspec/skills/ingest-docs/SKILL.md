---
name: ingest-docs
description: Turn existing Markdown into reviewable provisional DekSpec artifacts.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash
argument-hint: "[request or target]"
---

Use `dekspec ingest --help`, then run `dekspec ingest SOURCE` with its supported
output option pointing to an incubation directory. The deterministic importer
classifies headings/keywords; it cannot prove the source's truth or intent.
Keep source path, section and conversion provenance with each proposed artifact.
Never overwrite the live corpus with an unreviewed import.

Review classification, dropped material, ambiguity and conflicts with existing
specifications. Batch uncertain choices for review; do not demand approval of
every correctly classified row. Clearly distinguish quotations/observations
from inferred rationale. After review, use core authoring to promote the useful
artifacts; don't automatically lock or implement imported text.

State input limitations: the importer accepts Markdown, not arbitrary binary
files. On unsupported inputs, preserve originals and describe conversion needs.
Examples: “ingest docs/legacy-design.md”; “review the pending import”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
