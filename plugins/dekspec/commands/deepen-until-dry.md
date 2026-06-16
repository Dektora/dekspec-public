---
description: AFK repeat-until-dry deepening loop driver — re-invokes the orchestrate-deepening skill with fresh context each pass, consuming its { completed, remaining, dry } signal until consecutive dry passes converge or a max-iterations safety bound trips. Invoke once and walk away.
allowed-tools: Skill, Bash
argument-hint: [--help] [--scope PATH] [--max-iterations N] [--dry-streak N]
disable-model-invocation: false
---

Drive an AFK (operator-walks-away) deepening loop over a repo or a scoped
slice: re-invoke the `orchestrate-deepening` skill pass after pass until the
codebase is dry of new deepening opportunities, then stop. No human-in-the-loop
prompts.

## The loop lives in THIS command

THE LOOP LIVES IN THE COMMAND. This command owns the repeat-until-dry
iteration, the iteration state (pass count, consecutive-dry streak, beads
created across rounds), and the termination decision. It re-invokes the
`orchestrate-deepening` skill with FRESH context each pass — no shared
cross-pass context object is threaded between rounds. The skill does the actual
deepening work; this command decides whether to run it again.

The authoritative termination-control logic — loop bound, consecutive-dry
convergence, and scope threading — is the owned Python helper
`dekspec.deepen_loop.run_until_dry`, which this command drives, exactly as
`/exec-coding-session` drives `dekspec.action_handlers`. The skill-invocation
boundary is the helper's injected `pass_runner`: each pass calls
`pass_runner(scope=<scope>, context=<fresh per-pass context>)`, which (at
runtime) invokes the `orchestrate-deepening` skill and returns its
`{ completed, remaining, dry }` signal.

## `--help` mode

If `$ARGUMENTS` contains `--help`, print this usage and exit without running
any pass:

```
/deepen-until-dry [--scope PATH] [--max-iterations N] [--dry-streak N]
  --scope PATH        Restrict every pass to a repo slice (default: whole repo).
  --max-iterations N  Hard safety bound; always terminates (default: 10).
  --dry-streak N      Consecutive dry passes required to converge (default: 2).
  --help              Show this usage and exit.
```

## Per-pass procedure

For each pass, until termination:

1. Invoke the `orchestrate-deepening` skill via the Skill tool with FRESH
   context, threading the SAME `--scope` value passed to this command (omit it
   for a whole-repo pass).
2. Read back the skill's `{ completed, remaining, dry }` convergence signal.
3. Update iteration state: add `completed` to the beads-created total; if `dry`
   is `true` increment the consecutive-dry streak, otherwise reset the streak
   to 0.
4. Apply the termination rules below.

## Convergence exit

Terminate with `exit_reason = convergence` when consecutive passes report
`dry: true` for the active scope. The default streak target is **2** consecutive
dry passes (override with `--dry-streak N`). A single dry pass does NOT
terminate — an intervening non-dry pass resets the streak. Beads already created
in a prior round do not re-count as new work; the skill's `dry` signal already
keys off NEW Strong / Worth-exploring candidates, so a converged scope reports
`dry: true` even though earlier rounds created beads.

## Safety bound

A hard `--max-iterations` cap (default **10**) ALWAYS terminates the loop even
if convergence is never reached — the loop never runs forever. On a bound trip,
report exactly **stopped at bound, not converged** with `exit_reason =
safety_bound`. This is the AFK safety guarantee: an operator who started the
loop and left will find it stopped, not spinning.

## Scope threading

The optional `--scope PATH` threads the SAME slice into EVERY pass; `dry` is
evaluated relative to that active scope. Unset `--scope` means the whole repo is
the scope. The slice never changes mid-run.

## AFK / no-HITL

There are NO human-in-the-loop prompts between or within passes. The operator
invokes the command once and walks away; `prompts_issued` is always 0. Do not
pause to confirm a pass, a streak, or a termination — drive to the exit
condition autonomously.

## No merge path (ADR-026)

This command introduces no local merge, base-branch push, or branch-delete
step. Landing remains the skill's own `land-intent` handoff per ADR-026; the
deepening loop only creates and implements deepening beads up to the skill's
land boundary — it never advances a branch into the base.

## Result report

On termination, report:

- **Active scope** — whole-repo or the threaded slice.
- **Total passes** driven.
- **Beads created** across all rounds (the sum of per-pass `completed`).
- **Items implemented** and any landed / review-ready results surfaced by the
  passes.
- **Exit reason** — convergence (consecutive dry passes) vs safety bound
  (`stopped at bound, not converged`).

The `report` string from `dekspec.deepen_loop.run_until_dry` is the canonical
summary; relay it plus the per-pass detail to the operator.
