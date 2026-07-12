---
name: diagnose-bug
description: Governed pre-spec debugging loop for DekSpec — when a bug is observed, build a fast, deterministic, agent-runnable PASS/FAIL repro signal FIRST (before any hypothesizing), then minimize → hypothesize → instrument → fix → regression-test. The working diagnosis log lands in the gitignored `dekspec/.scratch/diagnostics/` zone and never enters the committed tree; the durable repro promotes into a bug Intent's `### bug — Reproduction` section (via /write-intent (type: bug)) and seeds /write-tests as a red-first outcome test. Use when a bug needs reproducing-before-fixing, when asked to debug or diagnose a failure, or before capturing a bug Intent.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [--at PATH]
related_skills: [write-intent, write-tests, write-ggc]
---

Run the governed pre-spec debugging loop. The **whole point of this skill** —
its PHASE 1 — is to build a fast, deterministic, agent-runnable **PASS/FAIL
repro signal before any hypothesizing**. A repro that has been *proven to flip
red* is the durable artifact every downstream step rests on: it gates the fix,
it seeds the red-first outcome test `/write-tests` needs, and it becomes the
`### bug — Reproduction` section of the bug Intent. No repro, no hypothesis.

This skill is the **debugging half** of the DekSpec lifecycle (INT-169 / ε).
It runs in a distinct pre-spec context and owns one distinct output — the
deterministic repro — which two downstream skills (`write-intent (type: bug)`,
`write-tests`) consume. It writes a working diagnosis log to the *gitignored*
ephemeral zone `dekspec/.scratch/diagnostics/` (landed by INT-165 / α) and never
commits it.

## Starter Prompt

```prompt
/dekspec:diagnose-bug --at .

A bug was observed: <one-line symptom>. Build a deterministic PASS/FAIL repro
signal FIRST — a single agent-runnable command whose exit code is the signal —
on this repo's own test/run harness. Log to dekspec/.scratch/diagnostics/. Only
once the repro flips red, proceed to minimize → hypothesize → instrument → fix →
regression-test, then promote the durable repro into a bug Intent.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Diagnose Mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Diagnose mode** — no flag (default). Optional `--at PATH` names the repo root (default: current working directory). Run the loop below.

This skill exposes no lifecycle/audit/review flags of its own — it is a pre-spec
debugging loop, not an artifact-lifecycle authoring skill. (It is therefore
exempt from the `_lib/mode_dispatcher.md` universal-mode set, which applies only
to the `write-*` artifact-lifecycle skills.)

## Diagnose Mode

### PHASE 1 — build the deterministic repro signal (this is the skill)

Before forming a single hypothesis, build a repro you can run on demand:

1. **Name the symptom** in one observable line — what is wrong, where it is
   seen, what the user expected instead.
2. **Express the repro as one agent-runnable command whose exit code is the
   signal** — `0` = PASS (bug absent), non-zero = FAIL (bug reproduced). Build
   it on the **consumer repo's own test/run harness** — detect it from the
   repo's manifest / lockfiles. Never invent a runner:
   wrap the repo's pytest / go test / npm test / cargo test / shell entrypoint.
   This keeps PHASE 1 **language-agnostic by delegation**.
3. **Prove it flips red.** Run the command against the buggy state and confirm
   it FAILS (non-zero) for the right reason. A repro you have not watched flip
   red is not a repro.
4. **Log it** to `dekspec/.scratch/diagnostics/<slug>.md` (the gitignored
   ephemeral zone — create the dir if absent). Capture the command, the
   observed failure, and the repro's red output. This log is disposable working
   memory, never committed.

If — and only if — a deterministic repro genuinely cannot be built (a Heisenbug,
an environment-bound failure on a since-deleted runner, a data-dependent crash
with no reproducible input), record a **Non-Reproducible Waiver** instead: state
plainly *why* no repro could be constructed and what evidence the fix will rest
on. The waiver is the explicit escape hatch the `T-BUG-REPRO-GATE` audit rule
accepts in place of a Reproduction — not a silent omission.

### PHASE 2 — minimize → hypothesize → instrument → fix → regression-test

Only after PHASE 1 yields a red repro (or a waiver):

5. **Minimize** the repro to the smallest input/command that still flips red.
6. **Hypothesize** a root cause; instrument (logging / a probe) to confirm or
   kill the hypothesis against the repro signal — never against memory.
7. **Fix**, then re-run the repro to confirm it now PASSES (flips green).
8. **Regression-test**: the red repro becomes the bug Intent's ADR-029 red-first
   outcome test.

### PHASE 3 — promote into the governed lifecycle

9. **Promote the durable repro** into a bug Intent via
   `/dekspec:write-intent (type: bug)` — the repro command + its red output
   populate the `### bug — Reproduction` section (or, if PHASE 1 produced a
   waiver, the `### bug — Non-Reproducible Waiver` section). A `≥ACCEPTED` bug
   Intent carrying neither draws a `T-BUG-REPRO-GATE` P3 advisory.
10. **Seed the outcome test** via `/dekspec:write-tests`: the red repro is the
    red-first outcome test the bug Intent's first bead lands.

Domain-term clarifications that surface during diagnosis route to
`/dekspec:write-ggc` rather than being defined inline.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:diagnose-bug"
one_line:   "Pre-spec debugging loop — build a deterministic PASS/FAIL repro signal FIRST, log to dekspec/.scratch/diagnostics/, then minimize→hypothesize→instrument→fix→regression-test and promote the repro into a bug Intent"
modes:
  - { flag: "", args: "[--at PATH]", description: "Diagnose mode — build the deterministic repro signal first, then run the full loop and promote the durable repro into a bug Intent via /write-intent (type: bug) + /write-tests." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:diagnose-bug --at ."
  - "/dekspec:diagnose-bug"
  - "/dekspec:diagnose-bug --help"
storage: "dekspec/.scratch/diagnostics/ (gitignored ephemeral working log; the durable repro promotes into a bug Intent's Reproduction section)"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When to use

- When a bug is observed and must be reproduced *before* a fix is hypothesized — to produce the deterministic, agent-runnable repro signal the governed lifecycle consumes.
- Before capturing a bug Intent — so the `### bug — Reproduction` section is filled from a proven-red signal rather than from memory or a copy-pasted log.

## When NOT to use

- To author the bug Intent itself — that is `/dekspec:write-intent (type: bug)`; `diagnose` *produces* the repro it consumes.
- To write the red-first outcome test — that is `/dekspec:write-tests`; `diagnose` seeds it.

## Related

- `/dekspec:write-intent` — consumes the durable repro into a bug Intent's `### bug — Reproduction` (or `### bug — Non-Reproducible Waiver`) section.
- `/dekspec:write-tests` — seeds the red-first outcome test from the proven-red repro.
- `/dekspec:write-ggc` — domain-term clarifications surfaced during diagnosis route here.
- AE-006 (Skills Library) — the AE this skill registers under; AE-003 (Fidelity Audit Engine) — owns the `T-BUG-REPRO-GATE` P3 advisory this loop's output satisfies.
