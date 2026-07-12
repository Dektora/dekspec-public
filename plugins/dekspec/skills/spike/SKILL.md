---
name: spike
description: Pre-Intent feasibility exploration — when the APPROACH is genuinely uncertain (algorithm choice, third-party integration, a performance characteristic), build a focused throwaway experiment that produces VERIFIED knowledge (not an opinion) and a durable spike record (hypothesis → experiment → VALIDATED / REFUTED / INCONCLUSIVE → recommendation) under `dekspec/spikes/<slug>/SPIKE.md`, which the subsequent Intent cites in its Motivation. Use before `/dekspec:write-intent --analyze` to de-risk an approach you cannot yet commit to. Distinct from `/dekspec:prototype` (which explores a design *shape*); spike answers a feasibility *question*.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [--wrap-up <slug>] [hypothesis or question]
related_skills: [prototype, diagnose-bug, write-intent, write-adr]
---

Run a **feasibility spike**: a focused, time-boxed throwaway experiment that
turns an uncertain approach into **verified knowledge** before an Intent commits
to it. The throwaway experiment is disposable; the **spike record** —
hypothesis, experiment, result, recommendation — is the durable deliverable.

A spike answers a **feasibility question** ("can X meet the P99 budget?", "does
this third-party API expose what we need?", "is algorithm A actually faster than
B on our data?"). Without it, engineers either commit an Intent on unvalidated
assumptions or defer indefinitely — both bad.

**Sibling skills — pick the right one:**

- `/dekspec:spike` (this) — *is the approach feasible?* Throwaway experiment →
  VALIDATED/REFUTED knowledge → durable spike record an Intent cites.
- `/dekspec:prototype` — *what is the right design shape?* Throwaway state-model
  / API sketch → findings folded into a WS/IC/AE. (Shape, not feasibility.)
- `/dekspec:diagnose-bug` — *why does this bug happen?* Deterministic repro of a
  defect (post-hoc), not a pre-spec feasibility question.

**No production leak** (shared with `prototype`): spike experiment code is
throwaway — never promoted directly into a real code path. Any production
adoption of a validated approach passes through the normal Intent → WS → IB
lifecycle. What re-enters the governed world is the **spike record's verified
finding**, cited by the Intent's Motivation — never the experiment code.

## Starter Prompt

```prompt
/dekspec:spike Can the PELT changepoint detector segment topics faster than the pragmatic splitter at P99 on our corpus?

Build a minimal throwaway experiment under dekspec/spikes/<slug>/, run it,
and write a SPIKE.md record: the hypothesis, what you built/measured, the
result (VALIDATED / REFUTED / INCONCLUSIVE) with evidence, and a recommendation
the next Intent's Motivation can cite. Don't promote any experiment code.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Spike mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Wrap-up mode** — `--wrap-up <slug>` flag. Load the completed
  `dekspec/spikes/<slug>/SPIKE.md` and route its verified finding into the
  governed lifecycle (see **Wrap-up mode** below).
- **Spike mode** — no flag (default). The positional `$ARGUMENTS` is the
  feasibility question / hypothesis; if empty, ask the engineer for one. Run
  the loop below.

This skill exposes no lifecycle/audit/review flags — it is a pre-spec
exploration loop, not an artifact-lifecycle authoring skill (exempt from the
`_lib/mode_dispatcher.md` universal-mode set, which applies only to `write-*`).

## Spike mode

### Step 1 — frame the hypothesis

State the uncertain approach as ONE falsifiable hypothesis with a concrete
success criterion — what observation would VALIDATE it, what would REFUTE it.
A spike with no falsifiable criterion is exploration, not a spike; sharpen it
first. Choose a short kebab-case `<slug>` for the run.

### Step 2 — build the minimal throwaway experiment

Scaffold `dekspec/spikes/<slug>/` and build the **smallest** runnable
experiment that can decide the hypothesis — on the repo's own runtime (detect
it from the manifest / lockfiles; never invent a runner). Keep it minimal and
disposable: it exists to produce a measurement, not to be hardened. Do not edit
production code (`src/`, `tooling/`, …) to run the experiment.

### Step 3 — run it and decide

Run the experiment and read the actual result (timings, exit codes, API
responses — facts, not recollection). Classify:

- **VALIDATED** — the success criterion was met under the measured conditions.
- **REFUTED** — it was not met; the approach as hypothesized does not hold.
- **INCONCLUSIVE** — the experiment could not decide (state precisely why and
  what a follow-up spike would need).

### Step 4 — write the durable spike record

Write `dekspec/spikes/<slug>/SPIKE.md` (this is the durable deliverable — it is
a knowledge document, NOT one of the parsed IR types; it carries no Status and
does not enter the SpecGraph). Use this shape:

```markdown
# Spike — <slug>

- **Date:** <UTC>
- **Question:** <the feasibility question>

## Hypothesis

<falsifiable claim + the success criterion that would validate/refute it>

## Experiment

<what was built + how it was run (the repro command) + the conditions measured>

## Result: VALIDATED | REFUTED | INCONCLUSIVE

<the observed evidence — numbers, outputs, API behavior — verbatim>

## Recommendation

<what the next Intent should do given this finding; the direction the spike
de-risks, in 1-3 sentences>
```

### Step 5 — hand back

Report the result + the record path. Tell the engineer the finding is ready to
cite in the next Intent's `## Motivation` (via `/dekspec:write-intent`), and
that `/dekspec:spike --wrap-up <slug>` will route a load-bearing finding into an
ADR candidate. The experiment code stays throwaway — it is not promoted.

## Wrap-up mode

`--wrap-up <slug>` converts a completed spike's verified finding into the
governed lifecycle — it does **not** author the artifact itself.

1. Read `dekspec/spikes/<slug>/SPIKE.md`. If Result is INCONCLUSIVE, say so and
   stop — there is no verified finding to promote; recommend a follow-up spike.
2. If the finding is a **load-bearing architectural decision** (chose A over B,
   accepted constraint Z), route it to `/dekspec:write-adr` as an ADR candidate
   — surface the decision/context/consequences drawn from the record; the ADR is
   authored by that skill, not here.
3. If the finding is **reusable mechanism** worth a tool, surface it as a skill
   candidate for the engineer's judgment (name what it would do).
4. Either way, this skill writes nothing beyond the spike record — promotion is
   the engineer's explicit next step through the governed authoring skills.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:spike"
one_line:   "Pre-Intent feasibility spike — a throwaway experiment that produces verified knowledge (hypothesis -> VALIDATED/REFUTED/INCONCLUSIVE -> recommendation) in a durable dekspec/spikes/<slug>/SPIKE.md the next Intent cites. No production leak."
modes:
  - { flag: "",          args: "<hypothesis or question>", description: "Spike mode — frame a falsifiable hypothesis, build a minimal throwaway experiment under dekspec/spikes/<slug>/, run it, and write a SPIKE.md record with the result + recommendation." }
  - { flag: "--wrap-up", args: "<slug>",                   description: "Route a completed spike's verified finding into the governed lifecycle — an ADR candidate via /dekspec:write-adr (or a skill candidate). Authors nothing itself." }
  - { flag: "--help",    args: "",                         description: "Show this help message." }
examples:
  - "/dekspec:spike can PELT segment topics faster than pragmatic at P99?"
  - "/dekspec:spike --wrap-up pelt-vs-pragmatic-p99"
  - "/dekspec:spike --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When to use

- Before `/dekspec:write-intent --analyze`, when the *approach* is genuinely
  uncertain (algorithm selection, third-party integration, a performance or
  scaling characteristic) and committing an Intent would bake in an unvalidated
  assumption.

## When NOT to use

- To explore a design *shape* (state model / API surface) — that is
  `/dekspec:prototype`.
- To reproduce and diagnose a *bug* — that is `/dekspec:diagnose-bug`.
- To author the Intent or ADR itself — spike *produces the verified finding*
  those skills consume; `--wrap-up` routes, it does not author.

## Related

- `/dekspec:prototype` — the design-shape sibling (throwaway shape exploration).
- `/dekspec:diagnose-bug` — the bug-repro sibling (deterministic defect reproduction).
- `/dekspec:write-intent` — cites the spike record's finding in `## Motivation`.
- `/dekspec:write-adr` — `--wrap-up` routes a load-bearing finding here as an ADR candidate.
