---
description: Cheapest-shape, pre-spec throwaway-exploration loop for DekSpec — invokes the /prototype skill. Feel out a state model (logic) or a request/response shape (api) BEFORE committing to an Intent or Working Spec; all throwaway code lands ONLY in the gitignored `dekspec/.scratch/prototypes/<run>/` ephemeral zone and is never production code, while the durable FINDINGS route into the governed authoring skills (/write-ws, /write-ic, /write-ae). A no-production-leak discipline holds throughout.
allowed-tools: Skill
argument-hint: [--help] [--shape logic|api] [--at PATH]
disable-model-invocation: false
---

Invoke the `prototype` skill to run the governed pre-spec throwaway-exploration
loop — scaffolding a disposable artifact under `dekspec/.scratch/prototypes/<run>/`
ONLY (never a tracked path), exploring a state model (`--shape logic`) or a
request/response shape (`--shape api`), then capturing the durable findings and
routing them into `/dekspec:write-ws` / `/dekspec:write-ic` / `/dekspec:write-ae`.

## Steps

1. Invoke the `prototype` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill scaffolds the throwaway exploration under `dekspec/.scratch/prototypes/<run>/` (the gitignored ephemeral zone, INT-165 / ADR-040 — never committed), explores disposably, then captures findings (decision reached, approaches rejected, risks surfaced, suggested next governed artifact) and routes them into `/dekspec:write-ws` / `/dekspec:write-ic` / `/dekspec:write-ae`. The no-production-leak discipline holds: any production adoption passes through the normal Intent → WS → IB lifecycle (`/dekspec:write-intent`); the scratch code is never promoted directly. The `UI` (switchable-variants) shape is a deferred follow-up.
