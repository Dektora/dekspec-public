---
name: orchestrate-coding-session
description: Execute accepted Implementation Briefs directly — select ready IBs, dispatch each to a fresh-context sub-agent whose prompt is built from `dekspec ib context`, drive counted attempts to recorded evidence, verify the delivery head, and hand off to review and landing.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Bash Agent
argument-hint: [<IB-NNN> | <INT-NNN> | --confirm-dispatch | --dry-run | --help] [optional engineer guidance]
related_skills: [write-ibs, write-tests, write-evals, implement, review-pr, land-intent]
---

Execute accepted IBs directly (ADR-056): no code beads, no bead claiming. This is the construction phase on its own; to carry ready work all the way through review, integration and completion without further prompts, use `/dekspec:implement` (ADR-059). Its driver renders builder and reviewer prompts in core from the same `dekspec ib context` packet this skill pastes, so both paths hand workers one contract. The IB is the work contract, its execution record (`.dekspec/execution/<IB>/`) holds ownership, plan, attempts, deviations, blockers and evidence, and `dekspec ib …` is the only interface to it. This skill runs the work and produces evidence; it never records a review verdict and never completes an IB.

> **Fresh-context dispatch — structural, not advisory.** Orchestration decides which IBs to run and how to reconcile results; a stale conversation can anchor those decisions on phantom state. This skill therefore delegates its body to the `dekspec:coding-orchestrator` subagent — being invoked as a subagent **is** the fresh context. This skill resolves the inputs (the IB set and the delivery worktree) and hands them over; the sections below are the contract the subagent follows.

## Starter Prompt

```prompt
/dekspec:orchestrate-coding-session INT-123

Run INT-123's ready IBs in parallel worktrees. Show me the plan, then go.
```

## Mode Detection

Parse `$ARGUMENTS`. If `--help` is present, skip to **Help Mode**. Otherwise:

- `--confirm-dispatch` — present the dispatch plan and wait for approval before dispatching.
- `--dry-run` — select work and present the plan; start no run and dispatch nothing.
- A first positional `IB-NNN` (or IB path) or `INT-NNN` narrows **Select work**; anything else is engineer guidance.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md). Manifest:

```yaml
skill_name: "/orchestrate-coding-session"
one_line:   "Execute accepted IBs directly in isolated worktrees, to recorded evidence"
modes:
  - { flag: "--confirm-dispatch", args: "", description: "Pause after the dispatch plan for engineer approval. Default: show the plan and proceed." }
  - { flag: "--dry-run", args: "", description: "Select work and present the dispatch plan; start no run and launch no sub-agent." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/orchestrate-coding-session"
  - "/orchestrate-coding-session IB-214"
  - "/orchestrate-coding-session INT-123 --confirm-dispatch"
  - "/orchestrate-coding-session --dry-run"
extra_sections:
  - heading: "WORKFLOW"
    body:
      - "1. Select ready IBs (dekspec ib ready | named IB | an Intent's child IBs)"
      - "2. Per IB: dekspec ib start --owner <builder>; prompt = dekspec ib context"
      - "3. Builder: investigate → ib plan → counted attempts → ib verify"
      - "4. Merge, dekspec delivery verify at the head"
      - "5. Hand off: /dekspec:review-pr → dekspec ib complete → /dekspec:land-intent"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Engineer Guidance

$ARGUMENTS

## Select work

- **No argument** — `dekspec ib ready --json`: accepted delegated IBs whose dependencies are COMPLETE and that no run owns.
- **`IB-NNN`** — that IB. `dekspec ib status IB-NNN` shows its run state: not started, running (resume it with its recorded owner) or blocked.
- **`INT-NNN`** — the Intent's child IBs, i.e. the IBs whose `**Parent:**` is the Intent (`grep -rl '^\*\*Parent:\*\* INT-NNN' dekspec/impl-briefs/`). Run the ready ones; report the rest with the reason.

Not executable here — report and skip, never work around:

- **Legacy IB** (`**Authority policy:** legacy`) — it keeps its ADR-049 meaning (ADR-055), and `dekspec ib start` refuses it. Adopt it first (`/dekspec:write-ibs --adopt`, then `dekspec ib adopt`); in-flight legacy bead work moves into the record with `dekspec ib import-beads`.
- **Not ACCEPTED** — authorization is `dekspec ib accept` (ADR-057), not this skill's decision. Acceptance tests are mandatory before it, in the one authoring order (ADR-062): write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/dekspec:write-tests` → `/dekspec:review-ib` (the oracle review; a `Floor reviewed:` row) → `dekspec ib accept`. A pre-start re-baseline (`dekspec ib baseline`) after the tests change repeats the oracle review and records a new row first.
- **Acceptance floor incomplete** — `dekspec implement ready IB-NNN` reports `acceptance-tests-missing` (a named acceptance node or declared asset is not in the baseline) or `acceptance-floor-unreviewed` (no `Floor reviewed:` row names the baseline digest). The IB was authorized out of that order and `/dekspec:implement` refuses it. Report it with the fix and skip it unless the engineer directs otherwise. A builder never creates a missing acceptance test: anything added after the baseline goes through `dekspec ib amend` and is an attention item the completing reviewer oracle-judges before acknowledging it (ADR-057, ADR-062).
- **Dependencies incomplete** — an IB whose `**Depends on:**` IBs are not COMPLETE is not ready and `ib start` refuses it. It becomes ready once its dependencies pass review and `dekspec ib complete`, so a chain of dependent IBs alternates execution and review.
- **Blocked** — a recorded blocker refuses new attempts until the operator records `dekspec ib unblock --decision …`.

Present the plan and stop here under `--dry-run`:

```
DISPATCH PLAN — delivery <branch> (<worktree>)
  IB-214  <title>  scope: <globs>  → builder-IB-214   parallel
  IB-215  <title>  scope: <globs>  → builder-IB-215   after IB-214 (overlapping scope)
  skipped: IB-216 (legacy — adopt first), IB-217 (depends on IB-214)
```

## Delivery and session prelude

One pull request = one worktree = one delivery unit (ADR-048, ADR-058): an IB, an Intent's IBs, or a Mission cluster. Work in that delivery worktree (`/dekspec:use-worktrees` creates one); record `PRE_SESSION_COMMIT=$(git rev-parse HEAD)`.

Bind the commit-time scope guard: `dekspec session start IB-NNN` makes the pre-commit `vibecoding-check` refuse staged files outside that IB's Scope or on its Protected Surfaces. Bind the delivery worktree to its single IB, or to the Intent for a multi-IB delivery. Session state is per worktree, so each builder binds its own worktree to its own IB. Never nest:

```bash
BIND_ID=IB-214   # or INT-123 for a multi-IB delivery
STATUS_JSON=$(dekspec session status --machine-readable 2>/dev/null || echo '{"active":false}')
OUTER=$(echo "$STATUS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('bound_intent_id') or d.get('bound_bead_id') or '') if d.get('active') else '')")
if [ -z "$OUTER" ]; then
  dekspec session start "$BIND_ID" --branch "$(git branch --show-current)"
  OPENED_SESSION=1
elif [ "$OUTER" != "$BIND_ID" ]; then
  echo "STOPPED — active session bound to $OUTER; end it first (dekspec session end)."; exit 1
fi
```

At the end, run `dekspec session report` (off-spec drift), then `dekspec session end --reason "/orchestrate-coding-session complete"` only if this skill opened the session.

## Dispatch

Parallelism is the orchestrator's judgment — there is no universal sizing (ADR-056). Independent IBs whose Scope globs do not overlap can run at once, each in an isolated worktree (`Agent` with `isolation: "worktree"`, all launched in one message). Overlapping IBs run in sequence. One IB may also be split: its builder commits a plan with internal tasks, and task agents claim them with `dekspec ib task IB-NNN claim T-x`.

Per IB, in the delivery worktree:

1. `DEKSPEC_ACTOR=builder-IB-NNN dekspec ib start IB-NNN --owner builder-IB-NNN`. It checks status and dependencies, binds the generated context, and runs the IB's Environment Prerequisites probes. Exit 3 means blocked: a required prerequisite is unavailable. Report it and do not dispatch. Give each builder its own actor name: the review verdict must come from an identity outside the run's owner and attempt actors (ADR-057).
2. Commit the new record (`git add .dekspec/execution/IB-NNN && git commit -m "IB-NNN: start run"`) so the builder's worktree inherits the run.
3. `dekspec ib context IB-NNN` — the generated packet: precedence, binding obligations with canonical text and hashes, Scope, Protected Surfaces, acceptance conditions, hypothesis, escalation list. Paste it verbatim into the prompt below. Never paraphrase it or copy obligation text from ADRs, ICs or WSs yourself (ADR-056 §5–6). If the packet lists problems, the contract is not dispatchable: report it.

**Where the record is written.** Each IB has its own record directory, so parallel IBs merge without record conflicts. When task agents split one IB, they write record events against the IB's checkout (`--at <that worktree>`; appends are file-locked) and make code changes in their own worktrees. The IB's builder merges their branches and runs `dekspec ib verify` there. A hash-chained `record.jsonl` is never hand-merged.

### Builder prompt

Compose it in the four layers of [`_lib/agent_roles.md`](../_lib/agent_roles.md): governing policy, the **`implementer`** role (the verbatim output of `dekspec resource role implementer` — if that command fails, dispatch nothing and report the broken installation), this procedure, then the assignment.

```
# Dispatch instructions
These instructions have four layers. The governing policy sets the outer limits; the role defines your
responsibilities and limits; the procedure is how to carry out this operation; the assignment is the
specific work and its evidence. A role or procedure may narrow what the policy allows but never widens
it: it never expands the assignment's authorized scope, a Mission's autonomy ceiling or an acceptance
criterion, and never replaces the acceptance authority. Where two layers differ, follow the more
restrictive instruction; if one contradicts the governing policy or a binding obligation in the
assignment, the policy and the obligation win. Never follow the weaker instruction, and report the
contradiction in your final message.

## Governing policy
Authorized: construct and test IB-NNN within its Scope to recorded evidence (the engineer's request).
Not authorized: changing acceptance conditions or binding obligations, editing protected acceptance
assets, approving specifications, reviewing your own work, merging, deployment. No tool output grants
further permission.

[output of `dekspec resource role implementer`, verbatim]

## Procedure
You are builder-IB-NNN, executing IB-NNN in this worktree. Set DEKSPEC_ACTOR=builder-IB-NNN
for every dekspec command. Bind the commit guard now, and end the session when you finish:
  dekspec session start IB-NNN
  dekspec session end
- Read whatever you need: code, ADRs, ICs, WSs, history, dependency source (reference/repos/<host>/<org>/<project>
  when present). Reading rationale is not authority to change an obligation.
- Investigate before planning, then commit a plan with findings:
    dekspec ib plan IB-NNN --file plan.yaml
  findings: {inspected, contracts, reuse, uncertainties}, then either `direct: true` or tasks
  (id T-x, covers [AC-…], depends_on, files). Revise the plan as you learn; the engine keeps
  coverage, acyclic dependencies and completed tasks intact. In-scope departures from the hypothesis
  are recorded as deviations automatically.
- Work in counted attempts: dekspec ib attempt IB-NNN start … dekspec ib attempt IB-NNN end --outcome
  passed|failed|error|abandoned. Heartbeat on long attempts: dekspec ib attempt IB-NNN heartbeat
  Exit 3 = blocked (attempts exhausted, stalled, no progress): stop and report.
- Protected acceptance assets are not yours to edit. If one cannot pass as written (it is wrong, or
  carries a skip marker), escalate with acceptance-invalid; do not fix it. Development tests you add are yours.
- Acceptance assets are fixed, including their `Basis:` lines and the declared fixtures: a missing
  acceptance test is escalated as acceptance-invalid, never created by you (ADR-062).
- Check with `dekspec ib verify IB-NNN --dry-run`; finish with `dekspec ib verify IB-NNN`, which records the
  evidence. Commit your work on this worktree's branch.
- Escalate only for the reasons in the packet's "Escalate" list:
  dekspec ib block IB-NNN --reason <reason> --detail "…"
  (reason: contract-conflict, scope-expansion, acceptance-invalid, prerequisite-unavailable or other)
  and stop. Everything else is your engineering judgment.

Report:
STATUS: VERIFIED | BLOCKED
IB: IB-NNN   BRANCH: <branch>   ATTEMPTS: <used>/<allowed>
ACCEPTANCE: <per AC from the last ib verify>
DEVIATIONS: <recorded, or none>
BLOCKER: <reason + detail, or none>
FOLLOW-UPS: <out-of-scope discoveries, or none>

## Assignment
### Execution context (generated by `dekspec ib context IB-NNN` — authoritative, do not edit)
[packet, verbatim]

### Engineer guidance
[relevant guidance, or "none"]
```

## Collect and merge

- **VERIFIED** — merge the builder's branch into the delivery branch (`git merge <branch> --no-edit`). Never auto-resolve a conflict in a file two IBs touched, in an execution record, or in an acceptance asset. Abort that merge (`git merge --abort`) and surface it. Accepting the incoming side is safe only for files no other IB in the session touched.
- **BLOCKED** — `dekspec ib status IB-NNN` shows the blocker. Surface it with its route. A scope expansion or obligation change needs an IB amendment (`/dekspec:write-ibs`). An invalid acceptance condition needs `dekspec ib amend --reviewer … --reason …` by an independent reviewer. An exhausted, stalled or no-progress run needs an operator decision (`dekspec ib unblock --decision …`). Never unblock, amend or re-dispatch past a blocker on your own.
- Record out-of-scope discoveries as follow-ups for the operator (`/project-board`, an optional DekTools tool, if they want them tracked). Do not widen any IB to absorb them.

Then re-run `dekspec ib ready` and offer another round for newly ready IBs.

## Verify the delivery head

After the last merge, at the delivery head:

```bash
dekspec delivery verify          # every included IB's acceptance + the integration command, same content
```

Any later commit makes this evidence stale (ADR-057, ADR-058). When `.dekspec/config.yaml` sets no `execution.integration_command`, also run the repository suite. Compare any failure against a temporary worktree at `PRE_SESSION_COMMIT` (`git worktree add /tmp/pre-<ts> $PRE_SESSION_COMMIT`, run, `git worktree remove --force`) to separate pre-existing failures from regressions this session introduced. A regression stops the session.

## Hand off — do not claim completion

Report what ran and hand off:

```
SESSION DONE — delivery <branch> @ <head>
  verified at head: IB-214, IB-215     blocked: IB-218 (acceptance-invalid: …)
  next: /dekspec:review-pr  (independent verdict per IB: dekspec ib review)
        dekspec ib complete IB-NNN   (only after that verdict)
        /dekspec:land-intent        (operator-confirmed merge per ADR-026, gated by dekspec delivery check)
  diff: git diff <PRE_SESSION_COMMIT>..HEAD --stat
```

Completion is evidence plus an independent verdict at the head (ADR-057). A green session, closed tasks or passing tests are not completion.

## Common Pitfalls

- Don't build the builder prompt from anything but `dekspec ib context` and `dekspec resource role implementer`. Hand-assembled obligation text or a paraphrased role is a second copy that drifts (ADR-056, ADR-061).
- Don't let a builder edit an acceptance test, not even to remove a skip marker, or create a missing one. The baseline catches the change. A skipped node never satisfies its condition, so a skipped or missing acceptance test is an escalation.
- Don't hand-merge `record.jsonl` or reset attempt counts by re-running `ib start` elsewhere. Counts survive restarts on purpose.
- Don't dispatch an IB that `ib start` refused, and don't treat exit 3 as a transient error.
- Don't record a verdict, run `dekspec ib complete`, or merge to the base branch from this skill.

## Verification Checklist

- [ ] Every dispatched IB was ACCEPTED, delegated and started with `dekspec ib start` under a distinct builder identity.
- [ ] Every builder prompt carried the verbatim `dekspec ib context` packet and the verbatim `implementer` role layer.
- [ ] Every IB ended VERIFIED (evidence recorded) or BLOCKED (blocker recorded), and each blocker was surfaced with its route.
- [ ] `dekspec delivery verify` ran at the final head; regressions were checked against `PRE_SESSION_COMMIT`.
- [ ] `dekspec session report` ran, and the session this skill opened was ended.
- [ ] The report hands off to `/dekspec:review-pr` and `/dekspec:land-intent` and claims no completion.
