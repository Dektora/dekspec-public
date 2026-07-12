---
name: write-goal-loop-contract
description: Write effective goal contracts for a long-running autonomous Claude Code run — the persistent plan → act → test → review → iterate loop. Use whenever the user wants to kick off a long-running / overnight / self-paced autonomous run, mentions a "goal loop" or "Ralph loop", asks how to write a goal/agent prompt with a stop condition, or wants a one-paragraph goal contract drafted. Turns a fuzzy "go do this" into a verifiable specification with a stop condition.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [task or intent to turn into a goal contract]
related_skills: [orchestrate-coding-session, orchestrate-intent, prototype]
---

Turn a fuzzy "go do this for a while" into a **goal contract** — a verifiable
specification with a stop condition — and drive it as a persistent autonomous
run that loops `plan → act → test → review → iterate` until the stop condition
is met, the engineer interjects, or the budget runs out.

**The shift this skill is about:** stop writing prompts, start writing
**specifications with stop conditions**. Spend the time upfront defining "done";
the run executes the spec. A goal loop is a *contract enforcer with a
verification loop*, not a "run forever" button.

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Goal-Loop mode**.

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Goal-Loop mode** — no flag (default). The positional `$ARGUMENTS` is the task
  or intent to turn into a goal contract (or a question about the loop / a
  fit-check). Run the guidance below.

This skill exposes no lifecycle/audit/review flags — it is a guidance + contract
-drafting helper, not an artifact-lifecycle authoring skill (exempt from the
`_lib/mode_dispatcher.md` universal-mode set, which applies only to `write-*`).

## How a persistent run is realized in Claude Code

There is no single auto-continue command — the contract discipline below is the
portable part, and Claude Code already plans→acts→tests→iterates inside its
agentic loop. Pick the driver that fits the run:

- **`/loop` skill** — `/loop <contract>` runs the goal on a recurring interval,
  or self-paced (omit the interval) where the model sets its own cadence. The
  closest analogue to a self-continuing goal: each firing re-enters the task.
  Best for "keep working until the stop condition holds, check back periodically."
- **Background agent** — dispatch the contract to a background sub-agent; the
  harness re-invokes the main loop when it completes. Best for a long mechanical
  job with a single completion checkpoint.
- **`/schedule` (cron routine)** — for runs that fire on a clock (nightly,
  hourly) rather than continuously.
- **`/dekspec:orchestrate-coding-session`** — when the run IS a dekspec construction
  session (dispatch a ready bead set in isolated worktrees), that skill is the
  native driver; write-goal-loop-contract just sharpens the objective + stop condition feeding it.
- **Plain agentic turn** — for a sub-one-turn job, just give Claude the contract.

## When to use it

Use only when **all three** are true:

1. Task is >30 min of mechanical work.
2. There is a **verifiable stop condition** — tests pass, coverage ≥ X, a build
   goes green, an audit is clean, an eval clears a threshold, a grep returns empty.
3. Repo is agent-ready (working build, a real test/validate command, `CLAUDE.md`
   carrying standing conventions).

Fits: migrations, coverage lifts, TDD feature builds, refactors behind contract
tests, prompt/eval optimization, bug-repro-then-fix, mechanical sweeps across
many files.

Bad fits: exploratory work, vague "improve this / make it better", anything with
no "done" definition, prod credentials, destructive shared-infra ops. When the
ask has no verifiable stop condition, say so and help narrow it to one rather
than draft a loose contract — an open-ended loop burns tokens and compounds an
unreviewable diff.

## The 4-part contract (every goal needs this)

1. **Objective** — one sentence, one concrete outcome.
2. **Constraints** — what must NOT change (public API, files, libraries,
   conventions).
3. **Validation command** — the exact shell command that proves progress
   (`pytest -q`, `pnpm test`, `ruff check .`, `dekspec doctor --at .`, …).
4. **Stop condition** — verifiable: "Stop when X passes" OR "when further
   changes need human/product input."

Plus: name what to read first, and ask for checkpoints with a short progress log
and atomic commits on a branch.

## Writing a goal (the core deliverable)

When the engineer wants a goal instruction, emit a structured markdown block —
one line per contract item, real newlines, not flowing prose. Emit only the
contract body; the engineer pastes it as the prompt (or as the `/loop` argument).
Template:

```
**Objective:** <one-sentence objective>
**Read first:** <files / PLAN.md / issue / CLAUDE.md>
**Constraints:** <what not to change; libs; conventions>
**Validate:** `<exact command>` after each change
**Checkpoints:** work in checkpoints; commit atomically on a branch; log progress briefly
**Stop when:** <verifiable condition>, OR when further changes require human/product input
```

### Example (migration)

```
**Objective:** Migrate this project from Pydantic v1 to v2.
**Read first:** pyproject.toml, src/, tests/, CLAUDE.md
**Constraints:** no public API changes; keep imports backwards-compatible via shims if needed; no new dependencies
**Validate:** `pytest -q` after each change
**Checkpoints:** work in checkpoints; commit atomically; log progress briefly
**Stop when:** the full suite passes with zero deprecation warnings, OR when a change requires architecture decisions
```

### Example (coverage lift)

```
**Objective:** Raise coverage in src/auth/ from ~38% to ≥75%.
**Read first:** src/auth/, tests/auth/, CLAUDE.md
**Constraints:** no new deps; mirror existing test style; do not modify production code unless strictly required for testability
**Validate:** `pytest --cov=src/auth --cov-report=term-missing`
**Checkpoints:** work in checkpoints; log the coverage delta each one
**Stop when:** coverage ≥75% AND all tests pass, OR when uncovered code needs design changes
```

### Writing rules

- **One objective, one stop condition.** Not a backlog.
- **Forbid reward-hacking explicitly:** "Do not delete, skip, weaken, `xfail`,
  or narrow tests to make the goal pass." Otherwise the agent may game the stop
  condition. (Recording a baseline test count first and re-checking it is a cheap
  anti-cheat.)
- **Keep the objective compact.** If it needs lots of detail, put it in a file
  (`PLAN.md` / `GOAL_BRIEF.md`) and have the goal point to it.
- Use **literal strings** for paths, commands, issue numbers — exact.
- Forbid scope creep explicitly: "Do not refactor unrelated code. Do not add
  dependencies."
- Tell Claude when to pause: "If <condition>, stop and ask before proceeding."
- Short, vague goals burn tokens for no extra value over a normal prompt.

### Meta-prompting trick (highest-leverage)

Hand-written goals under-specify. Ask a second session — Claude with the
codebase loaded, or a fresh sub-agent in the same repo — to: (1) inspect the
codebase, (2) surface hidden assumptions / constraints / edge cases, (3) emit a
structured goal block using the 4-part contract. Use that as the run's prompt.
Order-of-magnitude better runs.

### Self-goal setting

Give Claude the high-level intent and let it write its own contract: "Inspect
this repo, then write yourself a goal contract with a verifiable stop condition
and pursue it (drive it with `/loop` if it spans turns)." Still hand it the raw
materials (files to read, constraints, the validation command) so the contract
is grounded. Add: "ask clarifying questions before committing if the intent is
underspecified" — catches ambiguity up front and prevents drift.

## Launching

1. **Branch or worktree first — never `main`.** Long autonomy means a big diff;
   keep it isolated (`git worktree add` or a feature branch).
2. Pick the driver: `/loop <contract>` (cross-turn self-paced) · background agent
   (single long job) · `/schedule` (clock) · `/dekspec:orchestrate-coding-session` (a
   dekspec construction run) · paste-as-prompt (quick).
3. Walk away — but see "Controlling" and **always review the diff**.

## Controlling a running goal

| Action | Effect |
|---|---|
| Type a message mid-run | Interjection — the correction folds in and the run continues; engineer input always wins priority. |
| `Esc` / `Ctrl+C` | Interrupt the current turn. |
| `/loop` management | Adjust interval, or stop the loop. |
| `/schedule` management | List / update / cancel a scheduled routine. |
| Stop a background agent | Cancel the task; partial work stays on its branch. |

Resuming: state lives in git (the branch + commits) and `CLAUDE.md` / `PLAN.md`,
not server-side. To resume, return to the worktree, read the progress log / last
commits, and re-issue the (possibly tightened) contract.

## When a goal drifts

- **Minor drift:** type a correction (it folds in and continues).
- **Loose objective:** stop, read where it got to, then re-issue a *tighter*
  contract. Don't pile instructions on a vague goal.
- **Bad mess:** stop, `git reset --hard HEAD` or `git stash`, rewrite with the
  meta-prompting trick, restart on a clean branch.

Don't let a drifting goal keep running "to see where it goes" — tokens burn and
diffs compound.

## Operational tips

- **Always review the diff** before merging. Long autonomy produces more code to
  validate, not less — oversight becomes *more* critical, not optional.
- Keep tool permissions tight; default Claude Code permission prompts are correct
  for autonomous runs.
- First run: pick a 30-min scoped task so you learn how the stop condition fires
  before trusting it overnight.
- Bake recurring policy into `CLAUDE.md` so every goal inherits it without
  restating: adversarial self-review before declaring done, an extra QA pass even
  when tests pass, the standard validation command, atomic commits on a branch.
- Verify against the *real* environment, not a stale binary — if the project has
  an editable vs installed split, point the validation command at the source.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:write-goal-loop-contract"
one_line:   "Write a verifiable goal contract (Objective / Constraints / Validate / Stop) for a long-running autonomous run, and drive it via /loop, a background agent, /schedule, or orchestrate-coding-session. A spec with a stop condition, not a run-forever button."
modes:
  - { flag: "",       args: "[task or intent]", description: "Draft a 4-part goal contract for the task (or explain the loop / fit-check it); forbid reward-hacking + scope creep; name the right driver. If the ask has no verifiable stop condition, push back and help narrow it." }
  - { flag: "--help", args: "",                 description: "Show this help message." }
examples:
  - "/dekspec:write-goal-loop-contract migrate this service from Flask to FastAPI overnight"
  - "/dekspec:write-goal-loop-contract raise coverage in src/payments from 40% to 80%"
  - "/dekspec:write-goal-loop-contract --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When NOT to use

- For a task with no verifiable "done" definition — narrow it to one first, or it
  is not a write-goal-loop-contract candidate.
- To dispatch a dekspec bead set — that is `/dekspec:orchestrate-coding-session`;
  write-goal-loop-contract only sharpens the objective + stop condition it runs against.

## Related

- `/dekspec:orchestrate-coding-session` — the native driver when the run is a dekspec construction session.
- `/dekspec:orchestrate-intent` — walks one Intent's lifecycle to LOCKED (a governed alternative to a free-form goal loop).
- `/dekspec:prototype` — when the goal is to explore a design shape disposably rather than drive to a verifiable outcome.
