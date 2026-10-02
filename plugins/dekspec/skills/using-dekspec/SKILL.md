---
name: using-dekspec
description: Onboarding entry point for DekSpec — scaffold the artifact tree, toggle the No Specless Edits guardrail, and discover the skill catalog from a single skill. Merges the legacy `spec-mode`, `dekspec-skills`, and `dekspec-init` surfaces (INT-096).
mode: lite
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--init [--at PATH] [--force] [--methodology full|team]] [--spec-mode --on|--off|--status] [--catalog] [--help]
---

A single onboarding skill that walks an engineer through getting DekSpec live in a repo: scaffold the artifact tree, decide whether to enable the "No Specless Edits" guardrail, and discover the full skill catalog.

> **Replaces three legacy surfaces (INT-096):** `/dekspec:spec-mode`, `/dekspec:skills`, and `/dekspec:init` are merged into this single entry point. Existing functionality is preserved verbatim via the `--init`, `--spec-mode`, and `--catalog` modes below.

## Mode Detection

Default mode: **Walkthrough Mode** (no flag — guided tour of all three sub-surfaces).

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Init mode** — `--init` flag. Skip to **Init Mode**.
- **Spec-mode mode** — `--spec-mode` flag (paired with `--on`, `--off`, or `--status`). Skip to **Spec-Mode Mode**.
- **Catalog mode** — `--catalog` flag. Skip to **Catalog Mode**.
- **Walkthrough mode** — no flag. Proceed to **Walkthrough Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Render the manifest below and stop.

```yaml
skill_name: "/dekspec:using-dekspec"
one_line:   "Onboarding entry point — init + spec-mode + catalog merged into one skill (INT-096)"
modes:
  - { flag: "",             args: "",                       description: "Walkthrough: scaffold + guardrail decision + catalog summary, in that order. (Default)" }
  - { flag: "--init",       args: "[--at PATH] [--force]",  description: "Run `dekspec init` — scaffold the artifact tree (adrs/, architecture-elements/, working-specs/, ...). Forwards remaining args to the CLI verb." }
  - { flag: "--spec-mode",  args: "--on|--off|--status",    description: "Enable, disable, or check the 'No Specless Edits' guardrail in CLAUDE.md. (Status is the default if no on/off/status given.)" }
  - { flag: "--catalog",    args: "",                       description: "Print the full DekSpec skill catalog grouped by category, with one-line purpose + how to trigger for each skill." }
  - { flag: "--help",       args: "",                       description: "Show this help message." }
examples:
  - "/dekspec:using-dekspec                       # default — guided walkthrough"
  - "/dekspec:using-dekspec --init --at ."
  - "/dekspec:using-dekspec --spec-mode --on"
  - "/dekspec:using-dekspec --catalog"
```

## Walkthrough Mode

Guided tour for an engineer adopting DekSpec in a fresh repo. Touches all three sub-surfaces in the order an operator usually needs them:

0. **Engine check.** Run `command -v dekspec`. If the `dekspec` CLI is not on PATH, the plugin's surfaces have no engine to drive — surface the pip-from-git install line and continue:
   ```bash
   pipx install "git+https://github.com/Dektora/dekspec-public.git@main"
   ```
   (`@main` → latest; pin a release with `@vX.Y.Z`. Engine is acquired from the curated public mirror, ADR-034). Re-run this walkthrough once the CLI resolves.
1. **Scaffold check.** Run `ls dekspec/ 2>/dev/null`. If the tree exists, report "DekSpec artifact tree present — skipping scaffold." Else, ask: "Run `dekspec init` here? [Y/n]" and, on yes, run Init Mode against the cwd. On no, surface the manual command and continue.
2. **Spec-mode decision.** Run the Status sub-flow from Spec-Mode Mode. If `NOT INSTALLED` or `DISABLED`, ask: "Enable the 'No Specless Edits' guardrail in CLAUDE.md? [Y/n] (recommended for repos with active spec work)". On yes, run the On sub-flow. On no, leave as-is and continue.
3. **Configuration.** `using-dekspec` does not own per-repo config — it *calls* `setup-dekspec` for it. Ask: "Configure the per-repo `.dekspec/config.yaml` choices now (issue tracker, scratch dir, triage labels, glossary path, methodology profile)? [Y/n]". On yes, invoke `/dekspec:setup-dekspec --at .` (the configuration front-end); on no, surface the command and continue.
4. **Catalog summary.** Render the **Quick reference** subset from Catalog Mode (categories + the single most-used skill per category, not the full table). End with one-liner: "Run `/dekspec:using-dekspec --catalog` for the full table; ask in natural language to trigger any skill."

Close with a one-line "Next step" recommendation matched to the engineer's state: if the scaffold was fresh, point at the **Shortest path** — `/write-intent "<change>"` to capture the first governed change — or, for vision-first work, `/write-ae` for the first Architecture Element. (A fresh scaffold has no AE yet, so don't pin a new user to `/write-ae` by default.) If spec-mode was just enabled, remind that future code-changing requests will be gated on a spec artifact existing.

**End of Walkthrough Mode.**

## Init Mode

Scaffold the DekSpec artifact directory layout in the current directory (or `--at <path>`). Wraps the `dekspec init` CLI verb.

1. Confirm the user wants to scaffold in the current directory (run `pwd` and show the path). If `--at <path>` is supplied, use that path.
2. Run `dekspec init $ARGUMENTS` via Bash (forwarding all flags after `--init` to the CLI verb — `--at`, `--dekspec-root`, `--force`, `--methodology`).
3. Report which subdirs were created and which already existed.
4. Hint at the governed loop — `/write-intent "<change>"` → `/orchestrate-coding-session` → `/land-intent`; or `/write-ae` for the first Architecture Element when the work is vision-first. (A fresh scaffold has no AE yet.) After authoring, `/dekspec:doctor` will surface a baseline of findings to triage.

**End of Init Mode.**

## Spec-Mode Mode

Enable, disable, or check the "No Specless Edits" guardrail in the repo-root `CLAUDE.md`. Behavior preserved verbatim from the legacy `spec-mode` skill (INT-091 / INT-096).

### Status sub-flow (default when no `--on` / `--off` given)

1. Read `CLAUDE.md` in the repo root. If it does not exist, report status as `NOT INSTALLED` and stop.
2. Scan for the **No Specless Edits** pattern:
   - Present + uncommented → report **ENABLED**.
   - Present + enclosed in `<!-- ... -->` → report **DISABLED**.
   - Not found → report **NOT INSTALLED**.
3. Display the status in a clean, high-visibility format:
   ```
   Spec Mode Status: ENABLED
   ```

### On sub-flow (`--on`)

1. Read `CLAUDE.md` in the repo root. If absent, create it with a default structure.
2. Locate the `## Guardrails` or `## Rules` section. If neither exists, append a new `## Guardrails` section at the end (or after the project description).
3. Check the **No Specless Edits** spec-mode line:
   - Present + active → no-op.
   - Commented out (`<!-- ... -->`) → uncomment to activate.
   - Missing → insert under the `## Guardrails` / `## Rules` heading.

   The exact text of the active spec mode MUST be:
   ```markdown
    - **No Specless Edits**: You have wide latitude to determine when a user request suggests, implies, or directly asks for new capabilities, features, refactoring, codebase modifications, or updates to code/spec artifacts. In any such case, before proceeding with the request, you must immediately halt, make the engineer aware, and inquire whether a corresponding specification artifact (such as an Intent, Mission, ADR, or active Implementation Brief under `dekspec/`) should be created or updated. To assist the engineer, you must provide 1 to 3 context-aware suggestions (formatted as clear choices) of what specific actions or new/modified artifacts would be appropriate for the task. Prompt the user clearly with your inquiry and suggestions. Do not make source code edits until this specification context is established or explicitly deferred by the engineer.
   ```
4. Write the modified content back to `CLAUDE.md`.
5. Display a clean success message indicating spec mode is now **ENABLED**.
6. **Provisional-first reminder.** After the success message, ALWAYS emit the following authoring-discipline reminder block verbatim. This is the R1 augmentation from INT-091 — spec-mode catches code edits without a spec, but does NOT catch a spec being authored in the wrong place. The reminder closes that gap so engineers don't author new Intents/Missions directly in the canonical `dekspec/intents/` or `dekspec/missions/` tree (which collides on canonical ID allocation when multiple authors draft concurrently) and instead use the provisional → hand-promote workflow:

   ```
   --- Authoring discipline reminder ---
   NEW Intents (INT-NNN) and NEW Missions (MSN-NNN) ALWAYS start under
   `dekspec/provisional/<slug>/` via `dekspec library cow-stage <slug>` (or by
   hand-creating the directory + `INT-provisional-<slug>.md` skeleton).
   Canonical IDs (INT-NNN / MSN-NNN) are allocated only at hand-promote time,
   not at draft time. Walk DRAFT -> analyze -> PROPOSED -> ACCEPTED in
   provisional; promote via:
       dekspec.promote.plan_promotion(incubation_dir, dekspec_dir)
       dekspec.promote.apply_promotion(steps, incubation_dir, repo_root)
   when the family is ACCEPTED. This rule prevents canonical-ID collisions
   when multiple authors draft concurrently and keeps the canonical tree
   free of half-baked drafts.
   ```

   Emit the reminder unconditionally on every `--on` invocation. If the engineer's next user request authors a NEW Intent/Mission (heuristic: the request mentions "draft an Intent / draft a Mission / new INT-NNN / new MSN-NNN / author an Intent / author a Mission" and there is no current provisional dir matching the topic), additionally call the rule out inline in the assistant's response and recommend the provisional path explicitly rather than silently complying with a canonical-tree create.

### Off sub-flow (`--off`)

1. Read `CLAUDE.md` in the repo root. If absent, there is nothing to disable — report and stop.
2. Locate the **No Specless Edits** spec-mode line under the `## Guardrails` or `## Rules` section.
3. Check its current state:
   - Already commented out or missing → no-op.
   - Present + active → enclose in HTML comment tags so it is not parsed as an active rule:
     ```markdown
      <!-- - **No Specless Edits**: You have wide latitude to determine when a user request suggests, implies, or directly asks for new capabilities, features, refactoring, codebase modifications, or updates to code/spec artifacts. In any such case, before proceeding with the request, you must immediately halt, make the engineer aware, and inquire whether a corresponding specification artifact (such as an Intent, Mission, ADR, or active Implementation Brief under `dekspec/`) should be created or updated. To assist the engineer, you must provide 1 to 3 context-aware suggestions (formatted as clear choices) of what specific actions or new/modified artifacts would be appropriate for the task. Prompt the user clearly with your inquiry and suggestions. Do not make source code edits until this specification context is established or explicitly deferred by the engineer. -->
     ```
4. Write the modified content back to `CLAUDE.md`.
5. Display a clean confirmation message indicating spec mode is now **DISABLED**.

**End of Spec-Mode Mode.**

## Catalog Mode

Render the full DekSpec skill catalog. Behavior preserved verbatim from the legacy `skills` command (INT-096).

1. Print a beautifully formatted, premium markdown table of all available DekSpec skills grouped by category.
2. For each skill, include the purpose and how to trigger it in conversation.
3. Suggest the IB-direct flow for a bounded change (`/write-ibs`, then `dekspec ib propose` / `accept`), or — when the outcome spans several IBs — `/dekspec:spec-intent <INT-NNN>` to drive an Intent through specification. Once work is ready, `/dekspec:implement <INT-NNN | IB-NNN>` carries it through construction, review, integration and completion without further prompts.

---

# DekSpec Skills Catalog 🧭

Welcome to the DekSpec Spec-Driven Development skills catalog. Since authoring skills are designed to be run through interactive AI reasoning, they are not registered as raw shell commands. Instead, you can trigger them simply by asking me in natural language!

> Entries prefixed `/` are deterministic CLI-wrapper commands — they invoke a `dekspec` CLI verb directly with no agentic reasoning. Everything else is a full skill, triggered by natural language — except the ten user-only operator tools, whose trigger column reads "run `/dekspec:<tool>`": you start those yourself with the slash command, because I cannot start them for you (ADR-064).

Use the table below as a quick reference sheet:

### 1. Spec Authoring Skills (L0–L2 Artifacts)
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`write-sv`** | System Vision (L0 Singleton) | *"Let's write/edit the System Vision"* |
| **`write-constitution`**| Project Constitution (L0 Singleton) | *"Review or amend the Constitution"* |
| **`write-glossary`** | Domain Glossary (L0 Singleton) | *"Add a glossary term"* / *"Extract term candidates"* |
| **`write-corrections`** | Terminology Corrections (L0 Singleton) | *"Log a correction"* / *"Review open corrections"* |
| **`write-ae`** | Architecture Element (AE) | *"Create a new Architecture Element for [component]"* |
| **`write-adr`** | Architectural Decision Record (ADR) | *"Let's author an ADR choosing X over Y"* |
| **`write-sp`** | Security Profile (SP) | *"Capture the security posture for [context]"* |
| **`write-intent`** | Intent (INT-NNN) | *"Let's draft a new Intent for [feature]"* |
| **`write-mission`** | Mission (MSN-NNN) | *"Create a long-horizon Mission for [goal]"* |
| **`write-ic`** | Interface Contract | *"Create an Interface Contract for [boundary]"* |
| **`write-ws`** | Working Spec | *"Write a Working Spec for [subsystem]"* |
| **`write-ibs`** | Implementation Brief (IB) — the directly executable work contract; a bounded change is one IB, with or without a parent (ADR-056) | *"Write an IB for [change]"* / *"Decompose [WS or Intent] into IBs"* |

### 2. Lifecycle & Orchestration Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`spec-intent`** | Specification phase-executor (DRAFT → READY; ends with `dekspec implement ready`) | *"Spec out INT-NNN"* |
| **`implement`** | Implement ready work end to end — construct, test, independent review, repair, integrate, verify, complete (ADR-059) | `/dekspec:implement INT-NNN` · `/dekspec:implement the <feature>` |
| **`orchestrate-coding-session`** | Execute ready IBs (`dekspec ib ready`) in isolated worktrees — investigate, plan, verify, complete | *"Run the coding session for IB-NNN / INT-NNN"* |
| **`land-intent`** | Land a delivery: `dekspec delivery check` at the head, then the operator-confirmed merge (ADR-058) | *"Land INT-NNN"* / *"Land this branch"* |
| **`pr-branch`** | Strip spec-authoring churn from a branch into a clean, code-review-ready PR | *"Prep a clean PR branch for review"* |

### 3. Review Skills (two-tier, non-sycophantic)
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`review-ib`** | Pre-execution review of an IB contract, before `dekspec ib accept` | *"Review IB-NNN before coding"* |
| **`review-pr`** | Post-implementation review of the delivery diff; records one verdict per IB (`dekspec ib review`) | *"Review this PR against its IBs"* |

### 4. Verification & Quality Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`/doctor`** | Full health check — schema + linkage + drift + T/D/L fidelity (Stage 1 CLI doctor, Stage 2 inlined fidelity body) | *"Run /doctor"* or *"Audit our specs"* |
| **`/validate-artifact`** | Single-artifact schema validation (narrower than `/doctor`) | *"Validate dekspec/intents/INT-105-foo.md"* |
| **`write-tests`** | Author an IB's acceptance tests before execution (protected by the acceptance baseline) | *"Write acceptance tests for IB-NNN"* |
| **`write-evals`** | Probabilistic behavior evals, wired as IB acceptance conditions | *"Write evals for IB-NNN"* |
| **`debug`** | Evidence-driven diagnosis; authorized governed repair through core implementation | Run `/dekspec:debug <symptom or failing check>` |

### 5. Pre-Spec Exploration Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`interview-me`** | Docs-anchored one-question-at-a-time interview that sharpens fuzzy input into resolved decisions (composed default-on by the high-judgment authoring skills) | *"Interview me on this fuzzy idea"* / *"Grill me on this design"* |
| **`prototype`** | Pre-spec throwaway-exploration loop — explore a state model (`logic`) or request/response shape (`api`) in disposable `dekspec/.scratch/prototypes/` code, then route the durable findings into `/write-ws` / `/write-ic` / `/write-ae`; no production leak | Run `/dekspec:prototype <design question>` |
| **`spike`** | Pre-Intent feasibility exploration — a focused throwaway experiment that produces VERIFIED knowledge (VALIDATED / REFUTED / INCONCLUSIVE) before committing to an approach | Run `/dekspec:spike <hypothesis>` |

### 6. Codebase Architecture & Quality Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`audit-codebase`** | Audit source-code architecture quality — deep vs. shallow modules, information hiding, folderization fit (APOSD-grounded) | Run `/dekspec:audit-codebase <target>` |
| **`deepen`** | Multi-pass architectural deepening with retained learning and verified benefits | Run `/dekspec:deepen <module>` |
| **`security-review`** | Scoped security review with a small supported detector set; uses a Security Profile when one exists | Run `/dekspec:security-review <target>` |

### 7. Onboarding & Config Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`using-dekspec`** | This skill — onboarding + spec-mode + catalog | *"Get me started with DekSpec"* |
| **`setup-dekspec`** | Per-repo config front-end — interactively set issue tracker, scratch dir, triage labels, glossary path, methodology profile (round-trips through `dekspec config`) | *"Configure DekSpec for this repo"* / *"Set up the .dekspec config"* |
| **`/migrate`** | Upgrade pipeline (vendored drift → IR → artifacts) | *"Migrate our DekSpec artifacts"* |

### 8. Utility & Helper Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`write-goal-loop-contract`** | Turn a fuzzy "go do this" into a verifiable goal contract and drive a persistent plan→act→test→review→iterate autonomous run | *"Write a goal contract for this overnight run"* |
| **`handoff`** | Prepare/resume external-state continuity evidence with freshness checks | Run `/dekspec:handoff` / `/dekspec:handoff resume the parser work` |
| **`diagnose-session`** | Read-only post-mortem for stuck, failed, or anomalous sessions — collects evidence, detects known failure fingerprints, recommends recovery commands | Run `/dekspec:diagnose-session <session or run>` |
| **`recover-specs`** | Brownfield spec-gap recovery — code → ratifiable Intent | *"Recover the spec gaps in this repo"* |
| **`ingest-docs`** | Classify inherited markdown prose into DekSpec artifact slots | Run `/dekspec:ingest-docs <path>` |
| **`project-board`** | Boards, issue intake, duplicate detection and snapshots | Run `/dekspec:project-board <request>` |

---

> **One plugin.** Every skill in this catalog — the authoring / orchestration / review machine and the
> helper tools — ships in the **`dekspec`** plugin (ADR-064). `interview-me` and `recover-specs` are
> composed by the authoring skills; the other ten tools are user-only, so start them with `/dekspec:<tool>`.

### Pro-Tip 💡
**Shortest path to a merged change** — a bounded change is one IB; no parent artifact is required (ADR-056):
```bash
/write-ibs "<outcome, rationale, references>"
dekspec ib propose IB-NNN
dekspec ib accept IB-NNN
/orchestrate-coding-session
/land-intent
```

Author the IB (or scaffold one with `dekspec ib new <slug>`); `propose` requests the decision (lint-gated); `accept` authorizes execution and takes the acceptance baseline; the coding session executes ready IBs from `dekspec ib ready` in an isolated worktree; landing runs `dekspec delivery check` at the head before the operator-confirmed merge (ADR-058).

The executor's cycle per IB is `dekspec ib context` → `ib start` → investigate → `ib plan` → build → `ib verify` → independent `ib review` → `ib complete` — the only path to `COMPLETE` (ADR-057). Binding obligations are referenced, never copied; `dekspec ib context` delivers their canonical text (ADR-055).

Use an Intent (or a Mission) only when the outcome spans several IBs or needs kill criteria. From specification to delivery:
```bash
/dekspec:spec-intent <INT-NNN>   # specification: DRAFT → READY (engineer-gated acceptance)
/dekspec:implement <INT-NNN>     # ready work → integrated, verified COMPLETE, no routine prompts
```

**End of Catalog Mode.**
