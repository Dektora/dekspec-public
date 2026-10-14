---
description: Run `dekspec compile` — parse LOCKED DekSpec artifacts and emit the typed IR JSON for downstream audit/enforcement.
allowed-tools: Bash(dekspec compile:*), Bash(dekspec check:*)
argument-hint: PATH [--emit ir|contract-test|ci-gate|agents-md] [--output PATH] [--treat-as-locked] [--affected-paths PATH1,PATH2,...] [--resolve-aes]
disable-model-invocation: false
---

Compile DekSpec artifacts into IR JSON.

## Steps

1. Run `dekspec compile $ARGUMENTS` via Bash.
2. On exit `0` → confirm what was compiled (artifact kinds and counts from the output) and where the IR landed.
3. On non-zero → surface the parser errors verbatim. The compiler errors are precise enough that paraphrasing loses information.
4. If the compile produced new IR JSON, suggest `/dekspec:doctor` as the next step to audit the recompiled tree.
