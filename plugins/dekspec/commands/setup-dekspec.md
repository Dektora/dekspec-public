---
description: Initial-configuration front-end for DekSpec — invokes the /setup-dekspec skill. Interactively walks the per-repo `.dekspec/config.yaml` choices (issue tracker, ephemeral-scratch location, triage-label vocabulary, glossary path, methodology profile), persisting each via `dekspec config set` so it round-trips through `dekspec config get`. Writes agent-config pointers and optionally hands off to the quality/guardrail hook install. Called by `using-dekspec`'s onboarding walkthrough for the configuration step.
allowed-tools: Skill
argument-hint: [--help] [--at PATH]
disable-model-invocation: false
---

Invoke the `setup-dekspec` skill to run the per-repo DekSpec
initial-configuration walkthrough — front-ending `.dekspec/config.yaml` so the
engineer configures the issue tracker, ephemeral-scratch location, triage-label
vocabulary, glossary path, and methodology profile, each persisted via
`dekspec config set`.

## Steps

1. Invoke the `setup-dekspec` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill walks each config field one question at a time (recommending a sensible default per question), persists each answer with `dekspec config set <key> <value>` and confirms it reads back via `dekspec config get`, surfaces agent-config pointers (tracker / glossary / catalog) for consumer agents, and optionally hands off to the sibling Intent `quality-and-guardrail-hooks` hook-install flow. Domain-term clarifications route to `/dekspec:write-ggc`.
