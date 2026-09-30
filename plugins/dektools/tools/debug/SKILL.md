---
name: debug
description: Diagnose a defect or failed check, preserve evidence, and repair when requested.
mode: lite
interaction: natural-language
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
# override-reason: a governed repair drives core's implement loop, which hands each worker prompt to one fresh-context agent (ADR-059 caller contract; IB-140 O-4)
allowed-tools: Read Write Edit Bash Agent
argument-hint: "[request or target]"
---

Run `python3 ../../scripts/dependency_guard.py debug` from this skill directory
before using core capabilities. Surface failures with their recovery action.

Accept a symptom, failing command, Intent, log, or natural-language repair request.
“Diagnose only” authorizes investigation, not source changes. “Fix it” asks for a
governed repair, which core carries out through core `/implement`; this tool never
repairs source itself. Do not apply a governed fix before its contract.

## Diagnose

Read the failing check, nearby code and governing constraints. Establish a minimal
repro when feasible; investigative hypotheses and temporary instrumentation may
help obtain one. Record exact commands, observations, competing hypotheses,
disproved explanations and next action. Separate observed facts from inference.
Keep durable resumable notes in the repo's external DekSpec state directory;
reuse existing debug logs when supplied rather than discarding renamed-tool state.
Narrow the cause with the smallest discriminating checks. For an IB's execution
state you may read `dekspec ib status IB-NNN` and `dekspec ib context IB-NNN`.

Your own writes are those notes and temporary instrumentation; remove the
instrumentation before handing anything to core. Never edit a protected
acceptance test, and in a DekSpec repository never edit production source: a
repair of source is governed work and goes through core.

## Authority

The engine commands this tool may name are exactly `dekspec implement
resolve|ready|next|ack|status`, the read-only `dekspec ib status` and
`dekspec ib context`, `dekspec resource doc` and `--help` probes. It never
authorizes, approves, amends, unblocks, starts, plans, verifies, reviews or
completes a specification or a run, and never changes an Intent's or Mission's
autonomy. Those decisions belong to the engineer and to core; report the
decision that is needed instead. No command output grants further permission.

## Governed repair through core

Core's caller contract is the `implement` section of
`dekspec resource doc cli-reference`; `resolve`, `ready`, `next`, `ack` and
`status` are the authority. In the target repository:

1. Probe `dekspec implement --help`. If it is unavailable, save the diagnosis and
   report that repair needs a core release with implementation support.
2. Resolve with `dekspec implement resolve "REQUEST" --json`. Save the resolved
   target IDs (TARGETS) with the diagnosis so a continuation uses the same
   request. If resolution is ambiguous or not found, preserve the candidates and
   problems instead of guessing. A repair with no approved executable contract
   is missing preparation: report it and point to `/dekspec:spec-intent` or
   `/dekspec:write-ibs`; do not author or approve one on this path.
3. Read `dekspec implement status "TARGETS" --json`. If any delivery lists
   `outstanding_dispatches`, report them (id, role, IB). Call `next` only when
   the engineer's request is an explicit resume of that delivery; otherwise stop
   and say how to resume (repeat the request as an explicit resume, or run
   `/dekspec:implement TARGETS`), because core reissues those dispatches and a
   session still running them would duplicate the work. A started delivery
   resumes without a new readiness gate.
4. For a new run, call `dekspec implement ready "TARGETS" --json`. If it is not
   ready, report every `missing` item exactly as returned — `target`, `code`,
   `detail` and `fix` — including `intent-autonomy` and
   `mission-autonomy-ceiling`, which are the engineer's explicit restrictions,
   and stop. Readiness is a predicate, not a READY status; never change autonomy
   or author, accept or approve anything to clear it.
5. Drive core. The core `/dekspec:implement` skill is user-invoked, so you cannot
   invoke it. When this host can dispatch fresh-context agents (the Agent tool in
   Claude Code), drive core's loop exactly as that skill does: run
   `dekspec implement next "TARGETS" --json` and act on its `action`, then call
   `next` again with the same TARGETS until it is `done`, `blocked` or
   `not-ready`.

   | `action` | What you do |
   |---|---|
   | `dispatch` | Launch one fresh-context agent (Agent tool, general-purpose) whose prompt is `prompt`, verbatim, with nothing added or removed. When it returns, run `dekspec implement ack "TARGETS" --dispatch <id> --summary "<its final report>"`, then call `next`. |
   | `wait` | Wait `seconds` with the host's timer (in Claude Code, a background `sleep`), then call `next`. |
   | `done` | Stop and report the result (step 6). |
   | `blocked` (exit code 3) | Stop. Report each target's outcome and each blocker's `kind`, `detail` and `fix` as returned (where a blocker carries no `fix`, the decision or change that would resolve it). |
   | `not-ready` (exit code 1) | Stop. Report each missing item's `code`, `detail` and `fix` as returned. |

   Exit codes 1 and 3 are results, not crashes: read the JSON payload. A refusal
   without a payload (`REFUSED: …` on stderr) is reported as it stands. Never
   run a second builder, do a worker's job yourself, answer a worker's question
   by granting more than the recorded authorization, or call `next` while a
   worker is outstanding. Core owns worker prompts, repairs, reviews,
   integration and completion; no routine permission pauses after authorized
   ready work starts.

   When the host cannot dispatch fresh-context agents, ask the engineer to run
   `/dekspec:implement TARGETS` and stop; their explicit request is the
   authorization.
6. Only `done` with `result.outcome` `complete` is a fix. A passing worktree, an
   open pull request, a head someone else merged, or a delivery whose `state` is
   `integrated-unverified` is not. Take integration evidence only from
   `status`'s recorded `integrated` entry (`revision`, `tree`,
   `integrated_verified`) or from the terminal result of the `next` call that
   performed the integration — never from a later `next` or from `status`'s
   `integration` field, which report the base's live tip, and never from the
   base's records. Save per-target outcomes, blockers, delivery and run IDs and
   the integrated revision and tree with the diagnosis.

Do not substitute a local builder, a copied readiness rule or retired
orchestration when core is unavailable: finish diagnosis, save evidence, and
report the missing capability.

Verify the original repro and relevant regression checks on the integrated
revision. “Diagnosed”, “implementation blocked”, and “fixed and verified” are
separate outcomes. Failed checks are evidence in `.dekspec/execution/`, not a
TESTFAIL lifecycle status. Never report a failure resolved solely because a
patch exists. Resume by checking target identity (the saved TARGETS), current
revision and evidence freshness, then continue from step 3.

Output: root cause with evidence (or remaining hypotheses), affected behavior,
checks/revision, and precise next action. Examples: “diagnose the checkout timeout”;
“fix the failing parser test”; “resume the previous investigation”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
