---
name: implement
description: Implement ready, approved work end to end — `/implement INT-041`, `/implement int-041 and int-042`, `/implement the authentication feature`. Resolves the request to approved Intents or IBs, checks readiness, then drives construction, tests, independent review, repairs, integration and verification to completion without asking the engineer to drive, dispatching fresh-context builder and reviewer sub-agents from the core driver's `dekspec implement next` decisions. Use only to carry out an explicit implementation request; to explain how implementation would work, answer directly instead.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Bash Agent
argument-hint: [--help] <INT-NNN | IB-NNN | several ids | feature description> [budget]
related_skills: [spec-intent, write-ibs, review-pr, land-intent, orchestrate-coding-session]
---

**An explicit `/implement` request is the authorization (ADR-059).** It covers construction, tests, independent review, repair within scope and integration of the requested work — and nothing more. Do not ask the engineer to confirm, continue, dispatch or merge on this path. Do not create or approve specifications, weaken an acceptance condition, edit a protected acceptance test, bypass branch protection, deploy, or touch production. The core driver records the authorization and hands every worker the same statement.

**You do not decide the process; the driver does.** `dekspec implement next` is deterministic core code over durable records, git and the forge. It performs every mechanical step itself: preparing the delivery worktree, starting IB runs, verification, completion, updating from the base, integration. It returns the one step only an agent can take. You carry out that step, acknowledge it, and ask again. Never run `dekspec ib complete`, merge, commit or edit files yourself on this path.

## Mode Detection

- **Help mode** — `--help`. See **Help Mode**.
- **Implement** — anything else: the whole argument is the request. There are no mode flags.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md). Manifest:

```yaml
skill_name: "/dekspec:implement"
one_line:   "Implement ready work all the way through: construct, test, review, repair, integrate, verify, complete."
modes:
  - { flag: "", args: "<INT-NNN | IB-NNN | ids | feature description> [budget]", description: "Resolve the request, check readiness, and drive it to integrated, verified completion." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:implement INT-041"
  - "/dekspec:implement int-041 and int-042"
  - "/dekspec:implement the authentication feature"
  - "/dekspec:implement INT-041 — stop after 30 minutes"
extra_sections:
  - heading: "READY"
    body:
      - "Readiness is `dekspec implement ready <request>` — an ACCEPTED Intent (autonomy medium or high) with an outcome"
      - "and executable verification, authorized IBs whose obligations resolve, satisfiable dependencies, and an"
      - "environment that can run the checks and integrate. Not ready → the exact missing preparation."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## The loop

Let `REQ` be the whole argument (for example `INT-041 and INT-042`), minus any budget phrase. Run in the repository (any checkout of it):

```bash
dekspec implement next "REQ" --json
```

Act on the returned `action`, then call `next` again with the same `REQ`. Repeat until the action is `done`, `blocked` or `not-ready`.

| `action` | What you do |
|---|---|
| `dispatch` | Launch **one fresh-context sub-agent** (the Agent tool, general-purpose) whose prompt is `prompt`, **verbatim**, with nothing added or removed. When it returns, run `dekspec implement ack "REQ" --dispatch <id> --summary "<its final report>"`. Then call `next`. The `role` tells you who it is: `builder`, `reviewer`, `resolver` (merge conflicts) or `intent-reviewer`. The driver composed the prompt from that role's Agent Role Specification (`implementer`, `code-reviewer`, `implementer`, `verifier` — ADR-061) and recorded which revision; you never choose, swap or add a role. Do not do their work yourself, and never answer a worker's question by granting more than the authorization. |
| `wait` | The forge is still running required checks. Wait `seconds` using the host's timer (in Claude Code, a background `sleep`), then call `next`. |
| `done` | Report the result (below) and stop. |
| `blocked` | Report every blocker with its evidence and what would resolve it (below), and stop. Independent work has already continued; the driver only reports `blocked` when nothing authorized is left to do. |
| `not-ready` | Report the missing preparation exactly as returned — each item's detail and fix — and stop. Never author, accept or approve anything to make the request ready, and never implement a draft. |

**Recovery is the driver's job, not a reason to stop.** A failing test, a failed review, a failing required forge check, a merge conflict or a lost worker all come back as the next `dispatch`. Repeated failure without progress gets at most two recorded strategy changes per IB, then a genuine blocker.

**Continuation.** Your position lives in the records, not in this conversation. After a context compaction, just call `next` again. If this session ends, the engineer re-runs `/dekspec:implement` with the same request and it resumes; a worker that was running is reissued once. Repeating a finished request returns its result without doing anything again.

**Budgets.** If the engineer gave a budget ("stop after 30 minutes", "at most three workers"), stop at the first step boundary past it. Run `dekspec implement status "REQ"` and report where the run stands and that repeating the request resumes it. There is no other reason to stop early.

## Reporting

- **Done** — for each target: its outcome, the integrated revision (`integration.revision`) and method, and that the integrated content is the verified content. Also each IB's completion, and the workers dispatched (roles, and how many repairs or reviews it took).
- **Blocked** — per target, `complete` or `blocked`. Targets the request could not start are listed under `not_ready`, each with its missing item and fix (for example `completion-not-current`: a completion that no longer holds and needs the named review or repair; `no-integration-base`: the integration base does not resolve here, so a completion that fails the current rules cannot be told apart from history — fetch or correct the base first). Report them as not done. A `review-not-recorded` blocker means independent reviews (or Intent attestations) kept returning without a verdict: say so, and that it clears once an independent reviewer records one (`dekspec ib review` / `dekspec intent review`) and the request is repeated. Give each blocker's `kind` and `detail`, and what decision or change it needs (an IB amendment, an acceptance-condition amendment by an independent reviewer, a prerequisite, a forge permission, a remote that refuses the push). State plainly that nothing was weakened to get past it.
- **Not ready** — the list of missing preparation. Point to `/dekspec:spec-intent` or `/dekspec:write-ibs` where the fix is specification work. Missing acceptance tests (`acceptance-tests-missing`) or an unreviewed floor (`acceptance-floor-unreviewed`) are specification work in the one authoring order (ADR-062): write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/dekspec:write-tests` → `/dekspec:review-ib` → `dekspec ib accept` — or, for an IB already ACCEPTED and not started, `dekspec ib baseline` after that review. Acceptance tests are mandatory before authorization; this run never writes them, and its builders never create a missing one.

"Pull request opened", "tests pass in a worktree", "review ready" and "someone merged the branch" are progress, never completion. Report completion only when the driver returns `done`.

## Common Pitfalls

- Don't paraphrase or trim a worker prompt: it carries the authorization, the worker's role definition and the generated execution context, and a second copy drifts (ADR-056, ADR-061).
- Don't pass a builder's report to a reviewer. The driver gives the reviewer the recorded facts; the builder's account stays in the record.
- Don't call `next` while a dispatched worker is still running. A dispatch still open when `next` runs is treated as lost and reissued.
- Don't mark anything complete or merge by hand, and don't retry a refused merge with administrator rights. Report the blocker instead.
- Don't turn "explain how you would implement X" into a run. That question gets a direct answer.
- Don't write, fix or re-baseline an acceptance test to make a request ready. Acceptance assets are fixed for this run; their `Basis:` lines and declared fixtures included.
