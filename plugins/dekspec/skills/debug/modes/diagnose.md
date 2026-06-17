# /dekspec:debug — Diagnose mode

Walk Agans' nine rules of debugging on a TESTFAIL symptom. Every observation,
every hypothesis, and every disproved theory is recorded in
`dekspec/debug/<slug>.md` so the audit trail survives a context reset. The
output is a structured **Root Cause Report** — `--diagnose` applies NO source
fix; the only file written is `dekspec/debug/<slug>.md`.

## Pre-conditions

- A TESTFAIL symptom is recorded (or recordable) against an Intent — an
  outcome test is failing, a regression has been observed, or a previously
  green check is now red.
- The state-file slug is chosen — a short kebab-case identifier (e.g.
  `payment-flow-regression`). If a state file already exists at
  `dekspec/debug/<slug>.md`, prefer `continue <slug>` (see
  [`continue.md`](continue.md)) over starting fresh.

## Output guarantees (load-bearing)

1. **Writes only `dekspec/debug/<slug>.md`.** No source files modified. No
   test files modified. No spec artifacts modified. The Root Cause Report
   names the source line believed-buggy but does NOT touch it. Applying the
   fix is a separate, governed step (the Intent's normal coding-session flow)
   that lands once the report is in hand.
2. **Creates the state-file directory if absent.** `dekspec/debug/` is
   created on first use. The directory is committed to git so the audit
   trail is durable.
3. **Persists every cycle.** Every iteration of the nine-rules loop writes
   back to `dekspec/debug/<slug>.md` *before* moving to the next rule. A
   crashed agent context can be resumed by `continue <slug>` because the
   state file is always current to the last completed step.

## Agans' nine rules — the protocol

Walk these in order. Each rule is a checkpoint; persist your work back to
`dekspec/debug/<slug>.md` after each rule before moving on.

### Rule 1 — Understand the system

Read the spec, the code surface, and the data shape *before* forming any
hypothesis. The bug lives in *this* system, not in the abstract system in
your head. Record under `## Observation` in the state file:

- The Intent (`INT-NNN`) and TESTFAIL row this hunt belongs to.
- The code surface in scope (file paths + line ranges).
- The data shape the symptom involves.
- The control flow you *expected* vs. the control flow that produced the symptom.

### Rule 2 — Make it fail

If the symptom cannot be reproduced on demand, you are debugging a ghost.
Build (or borrow from the Intent's outcome test) a deterministic command
whose exit code is the signal — `0` = PASS, non-zero = FAIL. Run it; watch
it flip red. Record the repro command under `## Observation` and the
failure mode under the same heading.

### Rule 3 — Quit thinking and look

Stop guessing from the test name. Read the actual failure: the stack trace,
the assertion that fired, the printed values, the log lines, the diff
between expected and actual. The bug is in the *data*, not in your
recollection of the code. Record the observed evidence (verbatim — copy the
error, not your paraphrase) under `## Observation`.

### Rule 4 — Divide and conquer

Bisect the failure: which half of the call chain is at fault? Which commit
introduced the regression (`git bisect`)? Which input bit flips the
outcome? Record each bisection step under `## Theory` (the hypothesis you
are testing) and the result under either `## Observation` (if confirmed) or
`## Disproved` (if killed).

### Rule 5 — Change one thing at a time

Vary one variable per probe. If you flip two things and the symptom
changes, you have learned nothing. Record each single-variable probe under
`## Theory` and its outcome under the appropriate audit-trail section.

### Rule 6 — Keep an audit trail

This is the rule the skill is built around. Every observation, every
theory, every disproved theory goes in `dekspec/debug/<slug>.md` *as you
work*. The state file is the audit trail. It is also the resume point if
the agent context is reset before the hunt is done.

The audit-trail discipline is:

- **`## Observation`** — what you have observed directly. Stack traces,
  error messages, command outputs, file contents, control-flow notes.
  Facts only.
- **`## Theory`** — your current hypothesis. State it as a falsifiable
  claim ("the bug is that X returns Y when it should return Z"). Pair it
  with the probe that will confirm or kill it.
- **`## Disproved`** — every theory you have killed. Theory + the evidence
  that killed it. Disproved theories are the most valuable section: they
  prevent re-litigating dead branches after a context reset.

### Rule 7 — Check the plug

Before chasing exotic causes, check the boring ones: is the code on the
branch you think it's on? Is the test running the build you think it's
running? Is the env var set? Is the file path correct? Is the import
resolving to the package you think it is? Record each "plug check" under
`## Observation`.

### Rule 8 — Get a fresh view

If you have spun on a theory for more than two cycles, you have stared
yourself blind. Re-read the spec, ask a peer (or in DekSpec's agent world:
spawn a sub-agent with the audit trail as context and ask for an
independent read), or rubber-duck the problem out loud. Record the fresh
view under `## Observation` and any new theory under `## Theory`.

### Rule 9 — If you didn't fix it, it ain't fixed

When the symptom goes away, do NOT declare victory. Confirm the fix
actually fixes the bug: re-run the deterministic repro from Rule 2 and
watch it flip green. If the symptom returns under load, under a different
input, or after a restart — the bug is not fixed. Record the green-flip
under `## Root Cause Report` only after it is observed.

## Root Cause Report — the output shape

When the nine-rules walk converges on a single root cause that survives
Rule 9, the final section of `dekspec/debug/<slug>.md` is the Root Cause
Report. It is the structured output `--diagnose` produces:

```
## Root Cause Report

- Intent: INT-NNN (the TESTFAIL row this resolves)
- Symptom: <one-line — the failing observable behavior>
- Reproduction: <command that flips the bug red, copied from Rule 2>
- Root cause: <one-paragraph technical explanation — the buggy line(s),
  the wrong assumption, the missing case>
- Believed-buggy location: <file:line — read-only reference; --diagnose
  does NOT touch this file>
- Disproved theories: <bulleted list — every theory killed during the
  hunt, with the evidence that killed it>
- Recommended fix shape: <one-paragraph — the *direction* of the fix; the
  actual code change lands via the Intent's normal coding-session flow,
  not in this mode>
- Regression-test seed: <the deterministic repro from Rule 2, which
  becomes the red-first outcome test the Intent's next bead lands>
```

The Root Cause Report is the deliverable. It does NOT contain a code
patch. `--diagnose` writes only `dekspec/debug/<slug>.md` and modifies no
source files.

## Resolution writeback

Once the Root Cause Report is complete and the operator has confirmed the
fix direction, write a one-line fix summary back to the Intent's
`## TESTFAIL records` table:

```
| <date> | <slug> | RESOLVED — <one-line root-cause summary>; see dekspec/debug/<slug>.md |
```

The persisted state file at `dekspec/debug/<slug>.md` is NOT deleted; it
remains as the durable audit trail.
