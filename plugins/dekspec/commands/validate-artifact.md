---
description: Single-artifact schema validation via `dekspec validate`. **Use when:** you've just edited one artifact and want a fast schema check. **Narrower than:** `/dekspec:doctor` (which covers graph linkage + per-artifact schema + drift across the whole tree).
allowed-tools: Bash(dekspec validate:*), Bash(dekspec check:*)
argument-hint: PATH [--kind ic|ae|ws|adr|ib|intent|mission|sp|vision|glossary|constitution] [--json]
disable-model-invocation: false
---

Validate a single DekSpec artifact against its schema.

## Steps

1. Require a path argument. If `$ARGUMENTS` is empty, show usage and stop.
2. Run `dekspec validate $ARGUMENTS` via Bash.
3. On exit `0` → "✓ Artifact valid against schema." Show the artifact kind + name.
4. On non-zero → surface validation errors verbatim, anchored to the file path with line numbers if the CLI provides them.
5. Suggest `/dekspec:doctor` for graph-level checks after the per-artifact validation passes.
