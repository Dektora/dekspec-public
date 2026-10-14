---
name: recover-specs
description: Recover specification evidence from code and history with provenance.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Grep Glob Bash
argument-hint: "[request or target]"
---

Read the target code, its tests, governing artifacts and relevant history.
Use `dekspec find-spec-gaps --help` for deterministic glob coverage and
`dekspec archeology scan TARGET --at REPO` for Python AST evidence including
public API, internal state and best-effort import callers. Use installed CLI
commands, not `python -c` imports into the ambient interpreter.

Glob coverage means a file is claimed by a specification; it does not prove its
behavior is specified. The AST scanner supports Python and static imports only;
dynamic callers and other languages need explicit investigation. Record source
locations and commit references. Distinguish observed behavior, tested contracts,
plausible rationale and unresolved intent; history does not prove author motive.

Propose minimal artifacts through core's authoring path. Batch uncertain design
choices rather than requiring row-by-row approval. Recovery must not invent
requirements or declare current bugs to be desired behavior.
Output a provenance-backed gap list and proposed contracts. On unsupported
syntax/input, retain the partial evidence and identify the unassessed scope.
Examples: “recover specs for the undocumented parser”; “find gaps in this package”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
