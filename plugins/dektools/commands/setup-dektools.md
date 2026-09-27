---
description: Re-runnable à-la-carte selector for the DekTools suite (ADR-047) — invokes the /setup-dektools skill. Shows the tool catalog with each tool's dependency tier and the current selection, adds or removes individual tools, persists the choice as the repo's `dektools.enabled` set, and re-emits the host tree so exactly the enabled tools register. Nothing on by default; removal is non-destructive.
allowed-tools: Skill
argument-hint: "[--help] [--status] [--apply] [--at PATH] [--platform HOST]"
disable-model-invocation: false
---

Invoke the `setup-dektools` skill to choose which DekTools tools are active in
this repo.

## Steps

1. Invoke the `setup-dektools` skill via the Skill tool, forwarding
   `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill renders the DekTools
   catalog with each tool's `dependency_tier` plus a numbered "still remaining"
   list, walks the engineer through what to add or remove, persists the choice
   to `dektools.enabled` in `.dekspec/config.yaml` via `dekspec config set`,
   and re-runs `dekspec install` so the host tree carries exactly the enabled
   subset. Nothing is on by default, re-running both adds and removes, and
   removal is non-destructive — it disables a tool's emitted surface and
   deletes no user data. `--status` is read-only; `--apply` re-emits from the
   already-persisted selection without changing it.
