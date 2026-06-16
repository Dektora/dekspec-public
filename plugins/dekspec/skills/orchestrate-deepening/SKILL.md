---
name: orchestrate-deepening
description: Run ONE end-to-end architecture-deepening pass — analyze with deepen-codebase-architecture, turn the recommendations into atomic br beads with write-beads, implement the Strong and Worth-exploring beads via exec-coding-session (ADR-024 in-process), and land them review-ready through land-intent (ADR-026, never auto-merge). Returns a `{ completed, remaining, dry }` convergence signal. Use when the engineer wants one autonomous deepening cycle implemented and landed review-ready.
mode: lite
# override-reason: latest Opus tier per CLAUDE.md model policy; suite default (claude-opus-4-7) predates 4-8
model: claude-opus-4-8
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Bash Agent
argument-hint: [--help] [--scope PATH]
related_skills: [deepen-codebase-architecture, write-beads, exec-coding-session, land-intent]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/...` reference the consumer-vendored layout. Pip-only installs resolve via `dekspec resource ...`. See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md).

Run **exactly ONE** architecture-deepening pass and return a convergence signal.

This skill is a thin **composer**: it does not analyze, create beads, write code, or merge anything itself. It drives one pass through four sibling surfaces in order —
`deepen-codebase-architecture` → `write-beads` → `exec-coding-session` → `land-intent` —
implements the `Strong` and `Worth exploring` recommendations, lands them **review-ready** (never a direct merge, ADR-026), and emits a `{ completed, remaining, dry }` structured signal.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill dispatches an autonomous deepening pass that implements and lands code. Prior conversation context can bias which deepening candidates the pass anchors on.
>
> First message → proceed. Prior history → ask "context may bias the deepening pass, recommend /clear, continue? (y/n)" + wait.

## Boundary — ONE pass, no internal loop

This skill performs **one pass and stops**. It does NOT loop. There is **no internal loop** here and it **does not loop** internally — the repeat-**until-dry** loop (run passes until `dry: true`, with a safety bound) is owned by the **separate goal-command** (IB-132), which calls this skill once per iteration and reads the `{ completed, remaining, dry }` signal to decide whether to continue. Building that loop into this skill is out of scope and a contract violation.

This skill **composes** the four siblings — it never re-implements them:

- **It opens no beads by hand** — `write-beads` does that.
- **It writes no code inline and runs no `git switch -c` itself** — `exec-coding-session` does that (ADR-024, in-process).
- **It runs no local merge, no base-branch push, and no work-branch delete** — landing is `land-intent` only (ADR-026). The inherited direct-merge-and-push automation from `skills-import/ship-architecture-improvements` is deliberately ABSENT; see **Phase 4**.
- **It never edits or unlocks a LOCKED artifact** — the `land-intent` handoff refuses on the first unmet precondition (ADR-021).

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Deepening-Pass Mode**.

- **Help mode** — `--help` flag. See **Help Mode**.
- **Deepening-pass mode** — default. Optionally takes `--scope <path>` (threaded into the analysis pass). Proceed to **Deepening-Pass Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:orchestrate-deepening"
one_line:   "Run ONE architecture-deepening pass (analyze -> beads -> implement -> land review-ready) and return a convergence signal"
modes:
  - { flag: "", args: "", description: "Deepening-pass mode — run one whole-repo deepening pass and emit the { completed, remaining, dry } signal." }
  - { flag: "--scope", args: "<path-or-module>", description: "Confine the analysis pass to one path / subsystem / module slice; dry is evaluated relative to this active scope." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:orchestrate-deepening"
  - "/dekspec:orchestrate-deepening --scope tooling/dekspec/fidelity_audit"
  - "/dekspec:orchestrate-deepening --help"
extra_sections:
  - heading: "ONE PASS"
    body:
      - "This skill performs exactly one deepening pass and stops. The"
      - "repeat-until-dry loop is the separate goal-command (IB-132), which"
      - "calls this skill once per iteration and reads the convergence signal."
  - heading: "NEVER AUTO-MERGES"
    body:
      - "Landing is delegated to land-intent (ADR-026, RECOMMEND-only). No"
      - "direct git merge / push / branch-delete automation is present."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Deepening-Pass Mode

Run the four phases **in order**, exactly once. Each phase composes a sibling surface; do not hand-roll its work.

### Phase 1 — Analyze (`deepen-codebase-architecture`)

Run the **`deepen-codebase-architecture`** skill as the analysis engine — it surfaces deepening opportunities (shallow modules made deep) and interviews the chosen candidate. It opens no beads and lands nothing; that is this skill's job downstream.

Thread the optional **`--scope`** argument straight through into the analysis pass (it has the same `--scope <path>` shape):

- **Scope absent (default)** → run the analysis across the **whole repo**.
- **Scope present** → **thread** the `--scope <path>` value into the `deepen-codebase-architecture` invocation so the walk is confined to that slice. The objective deepening criteria (deletion test, shallow-interface signal) are unchanged by scope — only *where* it looks changes.

Collect every recommendation with its **strength** — `Strong`, `Worth exploring`, or `Speculative` — title, files/modules, problem, solution, acceptance criteria, and focused tests. The set of `Strong` / `Worth exploring` recommendations surfaced **for the active scope** is what the convergence signal in Phase 5 keys off.

### Phase 2 — Recommendations → beads (`write-beads`)

Run **`write-beads`** to turn the recommendations into atomic `br` beads. Do **not** hand-roll a `br create` loop — `write-beads` owns bead decomposition (atomicity, self-containment, labels, acceptance/test plan). Implementation beads (`Strong` / `Worth exploring`) become the work set for Phase 3; `Speculative` recommendations become review/follow-up beads only and are **not** implemented unless the engineer explicitly promotes them.

### Phase 3 — Implement (`exec-coding-session`)

Run **`exec-coding-session`** on the implementation bead set to autonomously implement the `Strong` and `Worth exploring` beads (ADR-024 — in-process dispatch to fresh-context sub-agents in isolated worktrees). Do **not** run `git switch -c` or write code inline here — `exec-coding-session` owns claim → implement → test → commit on each bead's worktree branch and collects the results.

### Phase 4 — Land review-ready (`land-intent`)

Run **`land-intent`** to drive each implemented IB-aggregate through the two-tier review pipeline to a **review-ready** landed state. Call `land-intent` **directly** for review-and-land (not via `orchestrate-intent --auto`).

`land-intent` **never auto-merges** (ADR-026 — RECOMMEND-only): it presents the squash-merge for explicit operator confirmation. The inherited direct-local-merge-and-push automation from `skills-import/ship-architecture-improvements` (its fast-forward merge of the work branch into the base, the base-branch push, and the work-branch delete + remote-delete) is **deliberately absent** from this skill. Re-introducing any local-merge / base-push / branch-delete landing step is a contract violation — landing is `land-intent` only. Per ADR-021 the handoff refuses on the first unmet precondition and the pass never unlocks a LOCKED artifact.

### Phase 5 — Convergence signal

Emit the pass's structured convergence signal as **in-skill output** (this is in-skill behavior, NOT an Interface Contract):

```text
{ completed: <N>, remaining: <M>, dry: <bool> }
```

- **`completed`** — count of recommendations implemented-and-landed-review-ready this pass.
- **`remaining`** — count of `Strong` / `Worth exploring` beads surfaced for the active scope but not yet landed.
- **`dry`** — `dry: true` **iff** the analysis surfaced **no new `Strong` / `Worth exploring` candidate** for the active scope this pass; otherwise `dry: false`. `dry` is evaluated **relative to** the active scope (the `--scope` slice when supplied, else the whole repo).

The goal-command (IB-132) reads this signal to decide whether to run another pass. This skill returns the signal and **stops** — it does not loop.
