---
description: Land a delivery — invokes the /land-intent skill. Sequences `dekspec delivery verify` → /dekspec:review-pr (one verdict per IB) → `dekspec ib complete` per IB → `dekspec delivery check` at the exact head → operator-confirmed merge → post-merge `dekspec intent verify` + `dekspec intent complete`. Never auto-merges (ADR-026). The landing-side sibling of /orchestrate-coding-session.
allowed-tools: Skill
argument-hint: [--help] <INT-NNN | IB-NNN | branch | PR-#>
disable-model-invocation: false
---

Invoke the `land-intent` skill to land a delivery.

## Steps

1. Invoke the `land-intent` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill verifies the delivery at its head, has every IB reviewed and completed, runs the `dekspec delivery check` landing gate, and presents the merge for explicit operator confirmation — it never merges on its own (ADR-026).
