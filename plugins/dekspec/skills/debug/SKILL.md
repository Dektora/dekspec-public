---
name: debug
description: Resumable post-spec debugging loop for DekSpec — runs Agans' debugging-9-rules protocol on a TESTFAIL symptom and persists investigation state (observation / theory / disproved audit trail) to `dekspec/debug/<slug>.md` so the hunt survives a context reset. `--diagnose` produces a structured Root Cause Report only and applies NO source fix (the only file written is the persisted state log). `continue <slug>` reloads the prior state file rather than restarting from the symptom. On resolution, writes a fix summary back to the Intent's `## TESTFAIL records` table. Use when a previously-locked Intent regresses, an outcome test starts failing, or a debugging session needs to span multiple agent contexts.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [--diagnose] [continue SLUG]
related_skills: [diagnose, write-intent, write-tests]
---

Run the resumable post-spec debugging loop. The **whole point of this skill**
is to apply Agans' nine rules of debugging to a TESTFAIL symptom on a LOCKED
or `IMPLEMENTING` Intent, while keeping the entire investigation audit trail
(observation / theory / disproved) in a single durable file —
`dekspec/debug/<slug>.md` — so a context reset, a paused session, or a handoff
to another agent does not vaporize the hunt.

This skill is the **post-spec** sibling of `/dekspec:diagnose`. Where
`diagnose` builds a deterministic PASS/FAIL repro signal *before* a bug
Intent is captured (pre-spec), `/dekspec:debug` runs the full nine-rules
protocol *after* a TESTFAIL has been recorded against an Intent — it lives
inside the governed lifecycle, not before it.

## Starter Prompt

```prompt
/dekspec:debug --diagnose --at .

A TESTFAIL was recorded on <INT-NNN>: <one-line symptom>. Walk Agans' nine
rules of debugging — Understand the system, Make it fail, Quit thinking and
look, Divide and conquer, Change one thing at a time, Keep an audit trail,
Check the plug, Get a fresh view, If you didn't fix it, it ain't fixed.
Persist every observation, theory, and disproved-theory to
`dekspec/debug/<slug>.md` so the hunt survives a context reset. Produce a
structured Root Cause Report at the end — apply NO source fix in this mode.
```

## Mode Detection

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Diagnose mode** — `--diagnose` flag (or no flag; default). Optional
  `--at PATH` names the repo root (default: current working directory).
  Run the nine-rules loop in `modes/diagnose.md`. Writes ONLY to
  `dekspec/debug/<slug>.md`; modifies no source files. Produces a structured
  Root Cause Report.
- **Continue mode** — `continue <slug>` positional. Reload `dekspec/debug/<slug>.md`,
  re-establish the observation / theory / disproved audit trail, and resume
  the hunt from the last checkpoint per `modes/continue.md`.

This skill exposes no lifecycle/audit/review flags — it is a debugging loop,
not an artifact-lifecycle authoring skill. (It is therefore exempt from the
`_lib/mode_dispatcher.md` universal-mode set, which applies only to the
`write-*` artifact-lifecycle skills.)

### Diagnose mode

See [`modes/diagnose.md`](modes/diagnose.md) for the full debugging-9-rules
protocol body — Agans' nine rules, the observation/theory/disproved audit-trail
discipline, the Root Cause Report output shape, and the write-only-to-state-dir
guarantee.

### Continue mode

See [`modes/continue.md`](modes/continue.md) for the resume-from-persisted-state
semantics — reload `dekspec/debug/<slug>.md`, re-establish the audit trail,
and continue from the last checkpoint rather than restarting from the symptom.

### Resolution writeback

On resolution (the bug is understood and a fix is identified), the final
section of `dekspec/debug/<slug>.md` is summarized back to the Intent's
`## TESTFAIL records` table — a one-line fix summary keyed to the TESTFAIL
row. The persisted state file is NOT deleted; it remains as the durable
audit trail for the resolution.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill — render it and stop:

```yaml
skill_name: "/dekspec:debug"
one_line:   "Post-spec debugging loop — run Agans' nine rules on a TESTFAIL, persist observation/theory/disproved audit trail to dekspec/debug/<slug>.md so the hunt survives a context reset, produce a Root Cause Report (no source fix), resume via `continue <slug>`."
modes:
  - { flag: "--diagnose", args: "[--at PATH]", description: "Default. Walk Agans' nine rules; persist audit trail to dekspec/debug/<slug>.md; produce a Root Cause Report. Modifies no source files." }
  - { flag: "",           args: "continue SLUG", description: "Reload `dekspec/debug/<slug>.md` and resume the hunt from the last checkpoint." }
  - { flag: "--help",     args: "", description: "Show this help message." }
examples:
  - "/dekspec:debug --diagnose --at ."
  - "/dekspec:debug continue payment-flow-regression"
  - "/dekspec:debug --help"
storage: "dekspec/debug/<slug>.md (durable persisted state — observation, theory, disproved, root-cause-report sections; survives context reset)"
```

## When to use

- When a TESTFAIL is recorded on a LOCKED or `IMPLEMENTING` Intent and the
  root cause is not yet understood.
- When a debugging session must span multiple agent contexts — the persisted
  state file is the handoff.
- When you want the audit trail of *what theories were proven wrong* to live
  in a single durable file rather than scattered across chat turns.

## When NOT to use

- To build a pre-spec PASS/FAIL repro signal *before* a bug Intent is
  captured — that is `/dekspec:diagnose` (the pre-spec sibling).
- To apply a fix — `--diagnose` is propose-only; the fix lands via the
  Intent's normal coding-session flow once the Root Cause Report is in hand.
- To author the bug Intent itself — that is `/dekspec:write-intent (type: bug)`.

## Related

- `/dekspec:diagnose` — the pre-spec sibling; builds the deterministic repro
  signal *before* the bug Intent is captured. `/dekspec:debug` runs *after*
  a TESTFAIL has been recorded against an Intent.
- `/dekspec:write-intent` — owns the `## TESTFAIL records` table that the
  resolution writeback updates.
- `/dekspec:write-tests` — the red-first outcome test the bug Intent's first
  bead lands once the Root Cause Report is in hand.
