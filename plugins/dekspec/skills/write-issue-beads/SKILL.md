---
name: write-issue-beads
description: Ingest an arbitrary report, request, or note and triage it into the non-coding `br` backlog — vertical-slice decompose into issue beads, tag HITL/AFK, quiz-and-iterate, product-gate escalation to /write-intent, and groom the standing backlog. Use for bugs/tasks/issues/chores; NOT for IB-derived coding beads (that is /write-code-beads).
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--groom | --help] [path-or-text-or-bead-id]
related_skills: [write-code-beads, send-issue, diagnose, write-intent]
---

Ingest arbitrary input and triage it into the non-coding `br` backlog.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill ingests free-form input and decomposes it into issue beads. Prior conversation context can leak assumptions into bead constraints that aren't in the source input.
>
> First message → proceed. Prior history → ask "context may affect triage quality, recommend /clear, continue? (y/n)" + wait.

## Boundary — what this skill is, and is NOT

`write-issue-beads` owns the **non-coding bead lifecycle**: ingest an arbitrary report / request / note → triage → groom a standing `br` backlog of `bug`/`task`/`issue`/`chore` items. It is the counterpart to `write-code-beads`.

- **`write-code-beads`** decomposes a LOCKED Implementation Brief into self-contained single-PR **coding beads** that `exec-coding-session` *dispatches*. Coding-pure, IB-derived, never triaged. **Do not duplicate it here.**
- **`write-ibs`** decomposes a finalized Working Spec into Implementation Briefs. **Do not duplicate it here.**
- **`send-issue`** files the *upstream* GitHub issue against `Dektora/dekspec`. `write-issue-beads` operates only on the *local* `br` backlog. The two stay distinct.

**Bead-model note (ADR-025 distinction):** ADR-025 defines the *coding* bead as a commit-cluster and the IB as a PR. This skill operates a **distinct non-coding bead lifecycle** (ingest → triage → groom) that *coexists with* and does **not change** that model — the IB-derived coding-bead path dispatched by `exec-coding-session` is untouched. No new ADR governs this skill; the distinction lives in this prose.

## Starter Prompt

```prompt
/dekspec:write-issue-beads "Audit found three doc-honesty gaps and a dead onboarding skill.
Quick-start URL 404s; README lists a deprecated alias; no smallest-path recipe."

Triage this into the backlog: vertical-slice decompose, tag HITL/AFK, quiz me on
priorities and the product-vs-utility split, then create the `br` beads.
```

## Mode Detection

Parse `$ARGUMENTS` for flags. If `--help` is present, skip to **Help Mode**. If `--groom` is present, strip it and skip to **Groom Mode**. Otherwise the remaining argument is the *input source* (a path, free text, command output, a prior assistant response, a plan, or an existing `BEAD-NNN` / `ds-xxxx` id) — proceed with **Triage Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-issue-beads"
one_line:   "Triage arbitrary input into the non-coding br backlog; groom the standing queue"
modes:
  - { flag: "", args: "<path|text|bead-id>", description: "Triage Mode — ingest input, vertical-slice decompose, tag HITL/AFK, quiz-and-iterate, product-gate escalation, then author typed br beads." }
  - { flag: "--groom", args: "[label|query]", description: "Groom Mode — default read-only report over the standing backlog: re-derived priority, categorization, duplicate/stale flags, needs-info, close/discard recommendations. Mutations only on explicit engineer-confirmed apply." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-issue-beads dekspec/.scratch/audit-report.md"
  - "/write-issue-beads \"three bugs in the install flow plus a refactor idea\""
  - "/write-issue-beads --groom"
  - "/write-issue-beads --groom div-handoff"
  - "/write-issue-beads --help"
extra_sections:
  - heading: "WORKFLOW"
    body:
      - "1. Ingest:       feed a report / request / note / plan / existing bead"
      - "2. Decompose:    vertical-slice (tracer-bullet) into independently-grabbable items"
      - "3. Tag:          HITL (needs the human) vs AFK (agent can run unattended)"
      - "4. Quiz:         quiz-and-iterate — confirm priorities, types, product-vs-utility, deps"
      - "5. Gate:         product+substantial → recommend /write-intent; else direct issue bead"
      - "6. Author:       typed br beads (bug/task/issue/chore) + labels + blocks deps"
      - "7. Groom:        /write-issue-beads --groom over the standing backlog (read-only first)"
```

## Triage Mode

The non-coding triage lifecycle. Run the stages in order; never create a bead before the quiz confirms it.

### 1. Ingest

Accept any of: a report or audit output, raw command output, a prior assistant response, a plan or design note, free text, or an existing `BEAD-NNN` / `ds-xxxx` id to re-triage. Read the source (Read for a path; treat inline text as-is). Extract the candidate work items — do not yet decide type, priority, or escalation.

### 2. Vertical-slice (tracer-bullet) decompose

Split the input into **independently-grabbable** work items, each a thin end-to-end slice that delivers observable value on its own (tracer-bullet: a working slice through the whole stack, not a horizontal layer). Avoid horizontal-layer or "do all the X first" splits. Each slice becomes one candidate bead.

### 3. Tag HITL vs AFK

For each candidate, tag:

- **HITL** (human-in-the-loop) — needs a human decision, a design call, credentials, a one-way door, or a judgment the agent can't make unattended.
- **AFK** (away-from-keyboard) — a self-contained slice an agent can grab and run to completion unattended.

The tag becomes a `br` label (`hitl` / `afk`).

### 4. Quiz-and-iterate confirmation

Before creating anything, present the candidate set as a table (proposed title · type · priority · HITL/AFK · escalation verdict · deps) and **quiz the engineer**: confirm or correct each field, surface ambiguities, and ask for the product-vs-utility override where the gate (stage 5) is uncertain. Iterate until the engineer signs off. **No bead is written until this confirmation completes.**

### 5. Product-gated escalation

For each candidate, classify on two axes and route:

- **Product-related?** — does it touch a surface the system **IS** (per `dekspec/system-vision.md` and the Constitution *Boundaries* article), versus a utility / helper / tooling / quick-coded surface the system **is NOT**?
- **Substantial?** — multi-IB / multi-component / new-contract scope, versus small / mechanical.

Routing:

| Product-related? | Substantial? | Route |
| ---------------- | ------------ | ----- |
| Yes | Yes | **Recommend `/write-intent`** — a big product feature is never free-beaded. |
| Yes | No | **Direct issue bead** — the sanctioned bead-as-spec path (small/mechanical product work). |
| No (utility) | any size | **Direct issue bead, no spec** — utility/helper/tooling/quick-coded work. |

The classification is a **recommendation** surfaced in the stage-4 quiz; the **engineer override** is an explicit quiz answer that can re-route any item either way.

### 6. Author typed `br` beads

For each confirmed item that stays a bead (i.e. not escalated to `/write-intent`), author a typed `br` bead — `bug` / `task` / `issue` / `chore` — with priority, labels (including the `hitl` / `afk` tag and any category labels), and `blocks` dependency-ordering between items. Use the standard `br` bead emitter / `br create` path; wire `br dep add` for the `blocks` edges; `br sync` when done. Report the created ids and the dependency graph.

## Groom Mode

Grooms the **standing** `br` backlog. **Default read-only** — produce a report plus recommendations; mutate nothing.

For the in-scope beads (all open, or filtered by an optional label/query argument), the report covers:

- **Re-derived suggested priority** from structural signals: unblock-count (how many beads this one unblocks) + parent-Intent priority + age.
- **Categorization / labels** — propose missing category labels.
- **Duplicate flags** — beads that appear to cover the same work.
- **Stale flags** — long-idle open beads.
- **Needs-info** — beads under-specified to grab.
- **Close / discard recommendations** — with a reason.

**Apply is engineer-confirmed:** mutations (label edits, priority changes, closes) run only after the engineer explicitly confirms an apply over the report. The **only reject-memory is `br close --reason "<why>"`** — a discarded item is closed with its reason recorded in `br`; there is no separate `.out-of-scope` file. A future groom pass sees the closed bead + reason and does not re-surface it.

## Common Pitfalls

- **Conflating lifecycles.** Do not decompose an Implementation Brief here (that is `write-code-beads`) and do not file the upstream GitHub issue here (that is `send-issue`). This skill is the *local non-coding backlog* only.
- **Free-beading a product feature.** If an item is product-related *and* substantial, recommend `/write-intent` — do not silently create a bead that bypasses the spec layer.
- **Mutating in Groom Mode by default.** Groom is read-only first; never apply changes without an explicit engineer-confirmed apply.
- **Horizontal decomposition.** Slices must be tracer-bullet vertical, each independently grabbable — not "do all the schema work, then all the UI work".

## Verification Checklist

- [ ] Every created bead is typed (`bug`/`task`/`issue`/`chore`), has a priority, carries its `hitl`/`afk` label, and any `blocks` deps are wired.
- [ ] No item that should have escalated to `/write-intent` was free-beaded.
- [ ] Groom Mode produced a read-only report; any mutation was engineer-confirmed and any discard used `br close --reason`.
- [ ] `br sync` ran after authoring/grooming.
