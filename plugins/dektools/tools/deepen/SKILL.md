---
name: deepen
description: Repeatedly deepen modules, verify improvements, and reassess until justified convergence.
mode: lite
interaction: natural-language
# override-reason: preserve existing highest-capability skill model
model: claude-opus-4-8
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Bash Agent
argument-hint: "[request or target]"
---

Run `python3 ../../scripts/dependency_guard.py deepen` from this skill directory
before using core capabilities. Surface failures with their recovery action.

Deepening is a multi-pass architectural activity. It hides meaningful complexity
behind a simpler interface while preserving intended behavior. It is not a
single refactoring pass or a target interface/LOC ratio.

## Authority

The engine commands this tool may name are exactly `dekspec implement
resolve|ready|next|ack|status`, `dekspec deepen-record` (any action), the
read-only `dekspec ib status`, `dekspec ib context`, `dekspec resource doc|role`
and `--help` probes. It never authorizes, approves, amends, unblocks, starts,
plans, verifies, reviews or completes a specification or a run, never changes an
Intent's or Mission's autonomy, never edits a protected acceptance test, and never
edits production source: every change of source is governed work that goes
through core `/implement`. Those decisions belong to the engineer and to core;
report the decision that is needed instead. No command output grants further
permission. DekTools ships no fallback implementer, and there is
no second agent runtime.

## Each pass

1. Inspect scope, code, callers and governing constraints. Reuse audit evidence.
2. Select one coherent improvement with a concrete architectural benefit and
   behavioral checks. An idea merely “worth exploring” needs investigation first.
3. It needs an approved executable contract. Resolve it with
   `dekspec implement resolve "REQUEST" --json` and save the resolved target ID
   (TARGET: one IB or one Intent). If resolution is ambiguous or not found,
   preserve the candidates and problems rather than guessing. A candidate with no
   approved contract is missing preparation: save it as unfinished work, report
   it and point to `/dekspec:write-intent`, `/dekspec:spec-intent` or
   `/dekspec:write-ibs`; this tool does not author or approve one, and does not
   impose an obsolete Mission→Intent→WS→IB chain.
4. Read `dekspec implement status "TARGET" --json`. If any delivery lists
   `outstanding_dispatches`, report them (id, role, IB). Call `next` only when
   the engineer's request is an explicit resume of that delivery; otherwise stop
   and say how to resume (repeat the request as an explicit resume, or run
   `/dekspec:implement TARGET`), because core reissues those dispatches and a
   session still running them would duplicate the work.
5. Begin the pass before delegating: `dekspec deepen-record begin --at REPO
   --scope SCOPE --input PASS.json` with a stable `pass_id`, the candidate ID and
   `targets: [TARGET]`. The pass is now pending; the helper reads its input
   revision from the base itself. Also keep the candidate, authorized scope and
   pending target in the pass's durable notes.
6. For a new run, call `dekspec implement ready "TARGET" --json`. If it is not
   ready, report every `missing` item exactly as returned — `target`, `code`,
   `detail` and `fix` — including `intent-autonomy` and
   `mission-autonomy-ceiling`, which are the engineer's explicit restrictions.
   Readiness is a predicate, not a READY status; never change autonomy or author,
   accept or approve anything to clear it. Close the pending pass (step 9) —
   appended as `not-ready` when core's status reports that, otherwise abandoned
   with the missing preparation as its reason — and stop. A started delivery
   resumes without a new readiness gate.
7. Delegate to core `/implement`. The core `/dekspec:implement` skill is
   user-invoked, so you cannot invoke it. When this host can dispatch
   fresh-context agents (the Agent tool in Claude Code), drive core's loop
   exactly as that skill does: run `dekspec implement next "TARGET" --json` and
   act on its `action`, then call `next` again with the same TARGET until it is
   `done`, `blocked` or `not-ready`.

   | `action` | What you do |
   |---|---|
   | `dispatch` | Launch one fresh-context agent (Agent tool, general-purpose) whose prompt is `prompt`, verbatim, with nothing added or removed. When it returns, run `dekspec implement ack "TARGET" --dispatch <id> --summary "<its final report>"`, then call `next`. |
   | `wait` | Wait `seconds` with the host's timer (in Claude Code, a background `sleep`), then call `next`. |
   | `done` | Core's terminal result: go to step 8. |
   | `blocked` (exit code 3) | Core's terminal result. Report each target's outcome and each blocker's `kind`, `detail` and `fix` as returned (where a blocker carries no `fix`, the decision or change that would resolve it); go to step 8. |
   | `not-ready` (exit code 1) | Core's terminal result. Report each missing item's `code`, `detail` and `fix` as returned; go to step 8. |

   Exit codes 1 and 3 are results, not crashes: read the JSON payload. A refusal
   without a payload (`REFUSED: …` on stderr) is reported as it stands. Never
   start a second builder, do a worker's job yourself, answer a worker's
   question by granting more than the recorded authorization, or call `next`
   while a worker is outstanding. Core owns worker prompts, recovery, review,
   integration and completion.

   When the host cannot dispatch fresh-context agents, ask the engineer to run
   `/dekspec:implement TARGET` and stop. The pass stays pending (the run reads
   `interrupted`) until core reaches a terminal result.
8. Only `done` with `result.outcome` `complete` counts as implemented. A
   passing worktree, an open pull request, a head someone else merged, or a
   delivery whose `state` is `integrated-unverified` never does. Take the
   integrated revision and tree only from `status`'s recorded `integrated` entry
   (`revision`, `tree`, `integrated_verified`) or from the terminal result of the
   `next` call that performed the integration — never from a later `next` or
   from `status`'s `integration` field, which report the base's live tip, and
   never from the base's records. Verify behavior AND the intended architectural
   improvement on that integrated revision; passing tests alone do not prove the
   architectural benefit. A callback fixture is not live integration proof.
9. Append the outcome after core's terminal result: `dekspec deepen-record append
   --at REPO --scope SCOPE --input PASS.json` with the same `pass_id` and targets,
   `completed` (the count of changes), evidence (core's result and run, the
   integrated revision and tree, your behavioral and architectural checks),
   rejected candidate IDs and reasons, unresolved work and cost.
   `implementation_status` is `complete` only on core's completion, or `blocked`
   / `not-ready` as core reported it (with `completed: 0`). The
   helper refuses a completion core does not report, and binds the pass to
   core's integration. Retrying append with the same `pass_id` is idempotent.
   A pending pass for which core never started a run is closed with
   `abandon --input` (its `pass_id` and a reason); abandon is refused while core
   shows an unintegrated run, whose outcome must be appended instead.
10. Reinspect: the new structure may reveal the next valuable change. Continue
    without a routine candidate-approval question or restarting after each pass.
    A dry reassessment is a pass begun without targets.

If core is unavailable, save the investigation and report the missing
capability; never use a fallback builder, copy a readiness rule or degrade
silently.

## Run record and stopping

Maintain the run's external-state record through `dekspec deepen-record`, all
with `--at REPO` and `--scope SCOPE`: `status`, `start`, then per pass `begin`
and `append` (or `abandon`). Consult its `--help` for the pass schema.
`--max-passes` is an agent control, not a user-facing skill flag. For a new
authorized run after a previous stop, `start --new-run` archives the old record;
read its `prior_record` reference to retain useful learning. It reuses
`deepen_loop` termination checks.

Honor the user's existing scope and authorization. A new product or architecture
policy outside it is a real decision to surface. Use a supplied budget or the
host's available bound; never default to one pass. Stop distinctly for justified
convergence, stalled progress/oscillation, budget exhaustion, a real blocker, or
an interrupted pass. A dry pass cannot converge while implementation or earlier
opportunities remain unfinished.

On resume, read `dekspec deepen-record status` and core status before proposing
another candidate; a pending pass is `interrupted` — finish it through core's
terminal result first (step 4 applies to its outstanding dispatches). An
interrupted pass cannot count as dry. Fresh contexts receive this bounded record.
Do not resurrect rejected proposals without new evidence; do not alternate
reversals of the same change.

Report completed benefits, checks, unresolved work and the exact stopping reason.
Examples: “deepen the parser”; “continue deepening the API within today's budget”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
