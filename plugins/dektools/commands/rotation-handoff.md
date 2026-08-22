---
description: Native DekSpec session continuity — invokes the /rotation-handoff skill. Emits or reads a structured, secret-redacted handoff record (objective, artifacts touched, decisions, open questions, commands run, test status, files changed, next safest action) under `dekspec/.scratch/rotation-handoff/`, so a rotated or compacted session resumes from a DekSpec-authored record with zero runtime dependency on `claude-mem`. Artifacts referenced by path, never copied.
allowed-tools: Skill
argument-hint: [--help] [--write | --read] [--at PATH]
disable-model-invocation: false
---

Invoke the `rotation-handoff` skill to emit or resume a structured session
handoff — the native DekSpec continuity surface (INT-176 / κ). The skill
front-ends `dekspec.rotation_handoff`, the same engine the session-lifecycle
hooks drive on `Stop` / `SessionEnd` / `PreCompact` / `SessionStart`. Zero
runtime dependency on `claude-mem`.

## Steps

1. Invoke the `rotation-handoff` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. In `--write` mode the skill assembles the eight-field structured record (objective / artifacts touched / decisions / open questions / commands run / test status / files changed / next safest action), applies secret-redaction, references artifacts by path, and persists to `dekspec/.scratch/rotation-handoff/` (newest N=10 retained). In `--read` mode it reads the most recent record back and surfaces the prior objective + next-safest-action to resume.
