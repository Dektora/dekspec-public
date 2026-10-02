---
name: diagnose-session
description: Collect session facts and explain failures without altering the investigated run.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Bash Write
argument-hint: "[request or target]"
---

Run `python3 scripts/evidence.py --at REPO` from this skill directory. It records
repository identity, recent commits, worktrees, status, resolved bead workspace
locations, available session metadata, and a summary of each DekSpec execution
record (IB, Intent and `/implement` run records under `.dekspec/execution/`:
last event, open attempts, live blockers, current completion). Use `--full` only
when the bounded report lacks needed detail. It never mutates the investigated
repo/session, and it needs no DekSpec engine.

Those execution records are the primary construction evidence; consult them
before attributing a stop. Only when the evidence report lists DekSpec execution
records and `dekspec` is on PATH may you also ask the engine for its read-only
view of them: `dekspec ib status IB-NNN` for an IB record and
`dekspec implement status REQUEST` for a run record. Otherwise (no records
listed, or the engine unavailable) read those record files directly instead:
each `.dekspec/execution/<ID>/record.jsonl` is an append-only, hash-chained
JSON Lines log whose events carry `seq`, `type`, `actor`, `ts` and `data`.
Either way the diagnosis
stands on the records; the engine's view is optional enrichment, never a
precondition.

Compare the user's intended outcome with these facts and any supplied logs.
Separate observations from hypotheses. Repeated commits are not proof of a stuck
loop; concurrent worktrees are not proof of collisions. Check timing, branches,
actual errors and shared paths before attributing cause. Do not assume a main
branch or inspect the plugin checkout in place of the requested repository.

Report a short timeline, strongest supported explanation, alternatives, missing
evidence and recovery action. Redact sensitive log excerpts. Do not restart,
kill, reset or edit the investigated run as part of diagnosis.
Examples: “diagnose the abandoned parser worktree”; “why did this session stop?”

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
