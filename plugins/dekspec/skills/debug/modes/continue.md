# /dekspec:debug — Continue mode

Resume a prior debugging session. The whole point of the persisted state
file at `dekspec/debug/<slug>.md` is that the hunt survives a context
reset — `continue <slug>` reloads that state and picks up where the prior
agent stopped, rather than restarting the nine-rules walk from the symptom.

## Pre-conditions

- A state file already exists at `dekspec/debug/<slug>.md` from a prior
  `/dekspec:debug --diagnose` run. (If no such file exists, this mode
  refuses with a one-line message instructing the operator to start a
  fresh diagnose run.)

## Resume protocol

1. **Reload the state file.** Read `dekspec/debug/<slug>.md` and parse the
   four audit-trail sections — `## Observation`, `## Theory`,
   `## Disproved`, `## Root Cause Report` (if partially filled). The state
   file is the audit trail; treat its contents as authoritative over your
   own (empty) recollection.
2. **Re-establish context.** Restore the working set in your head:
   - **Observation** — what has been observed directly (facts, errors,
     command outputs, file contents from the prior session).
   - **Theory** — the current open hypothesis (if any). State the
     falsifiable claim the prior agent was testing.
   - **Disproved** — the dead branches. Do NOT re-litigate them; the
     audit trail exists specifically to prevent re-walking these.
3. **Identify the last checkpoint.** Find the most recent rule the prior
   session completed (Rule 1–9 from `modes/diagnose.md`). The state file's
   final `Theory` or final `Observation` entry indicates where the hunt
   was paused.
4. **Resume from there.** Continue the nine-rules walk from the last
   checkpoint — not from Rule 1, not from the symptom. If the prior
   session was mid-bisection (Rule 4), pick up the next bisection step.
   If it was mid-fresh-view (Rule 8), come back with the fresh view.
5. **Continue persisting.** Every new observation, theory, and disproved
   theory writes back to `dekspec/debug/<slug>.md` as you work — the
   audit-trail discipline is identical to `--diagnose`.
6. **Same output guarantees.** `continue` writes ONLY to
   `dekspec/debug/<slug>.md`. No source files modified. Produces the same
   Root Cause Report shape on convergence.

## Why this exists

Long debugging hunts routinely outlast a single agent context — a tricky
bug can span hours or days, multiple bisections, and dozens of disproved
theories. Without persistent state, every context reset means re-walking
dead branches from scratch. The `dekspec/debug/<slug>.md` file is the
solution: it is the durable record of *what has been observed* and *what
theories have been killed* so the next agent starts where the prior one
stopped.

The audit trail (especially the `## Disproved` section) is the
load-bearing artifact: it prevents the next session from re-litigating
theories the prior session already killed.

## Resolution writeback

When the resume converges on a Root Cause Report (per Rule 9 in
`modes/diagnose.md`), the same resolution-writeback step applies: a
one-line fix summary lands on the Intent's `## TESTFAIL records` table,
and the state file at `dekspec/debug/<slug>.md` is retained as the
durable audit trail.
