---
description: Run `dekspec graph export` — emit the DekSpec artifact dependency graph as text / JSON / DOT / Mermaid for visualization or external tooling.
allowed-tools: Bash(dekspec graph:*), Bash(dekspec dev:*)
argument-hint: [--at PATH] [--dekspec-root DIR] [--output FILE] [--include INCLUDE] [--pretty] [--format text|json|mermaid|dot]
disable-model-invocation: false
---

Export the DekSpec artifact graph.

## Steps

1. Default to `--format mermaid` if no format is supplied — easiest to glance at in a Claude session.
2. Default `--include ALL` if no filter is supplied.
3. Run `dekspec graph export $ARGUMENTS` via Bash.
4. On success:
   - If `--output` was set, confirm the file path and show line count.
   - Otherwise, print the graph output inline in a fenced code block (annotate the language: ```mermaid / ```json / ```dot). For a large `--include ALL` graph, prefer `--output` + a summary over dumping every node inline.
5. On error, surface the message verbatim.
